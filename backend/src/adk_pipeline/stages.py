"""Deterministic ADK BaseAgent stages wrapping the domain agents in src.agents.

Each stage reads its inputs from session state, calls the corresponding
deterministic Python agent (no LLM involved), and commits its outputs back to
session state via an Event's `state_delta`. Keeping these deterministic is a
safety requirement: consent, compatibility, and blocker decisions in a
clinical decision-support tool must never depend on LLM judgment.
"""

import json
from datetime import datetime
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from src.agents.patient_data_agent import PatientDataAgent
from src.agents.safety_consent_agent import SafetyConsentAgent
from src.agents.blood_bank_agent import BloodBankAgent
from src.agents.organ_agent import OrganAgent
from src.agents.equipment_agent import EquipmentAgent
from src.agents.validation_agent import ValidationAgent
from src.agents.logistics_agent import LogisticsAgent
from src.models.report import Blocker, BlockerSeverity, ResourceStatus
from src.models.surgery import SurgeryRequest
from src.adk_pipeline import state_keys as K
from src.adk_pipeline.coordinator import build_coordinator_input_summary


def _blocker(category: str, message: str, severity: BlockerSeverity = BlockerSeverity.CRITICAL) -> dict:
    return Blocker(category=category, severity=severity, message=message).model_dump(mode="json")


class PatientDataStage(BaseAgent):
    """Wraps PatientDataAgent.extract_patient_data."""

    patient_agent: PatientDataAgent


    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        surgery_dict = ctx.session.state[K.SURGERY_DICT]
        surgery_id = ctx.session.state[K.SURGERY_ID]
        surgery_request = SurgeryRequest(**surgery_dict)

        result = self.patient_agent.extract_patient_data(surgery_request, surgery_id)

        delta = {
            K.PATIENT_EXTRACTION_OK: result.extraction_successful,
            K.PATIENT_DATA: result.extracted_data.model_dump(mode="json") if result.extracted_data else None,
            K.PATIENT_MISSING_FIELDS: result.missing_fields,
            K.PATIENT_WARNINGS: result.warnings,
        }
        yield Event(author=self.name, actions=EventActions(state_delta=delta))


class SafetyConsentStage(BaseAgent):
    """Wraps SafetyConsentAgent.check_safety_and_consent."""

    safety_agent: SafetyConsentAgent


    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        from src.models.patient import PatientData

        state = ctx.session.state
        surgery_id = state[K.SURGERY_ID]

        if not state.get(K.PATIENT_EXTRACTION_OK):
            yield Event(author=self.name, actions=EventActions(state_delta={
                K.SAFETY_PASSED: False,
                K.SAFETY_BLOCKERS: [_blocker("PATIENT_DATA", "Patient data extraction failed; safety checks skipped")],
                K.SAFETY_WARNINGS: [],
            }))
            return

        patient_data = PatientData(**state[K.PATIENT_DATA])
        surgery_dict = state[K.SURGERY_DICT]

        passed, blockers, warnings = self.safety_agent.check_safety_and_consent(
            patient_data, surgery_id, surgery_dict['surgery_type']
        )

        delta = {
            K.SAFETY_PASSED: passed,
            K.SAFETY_BLOCKERS: [b.model_dump(mode="json") for b in blockers],
            K.SAFETY_WARNINGS: warnings,
        }
        yield Event(author=self.name, actions=EventActions(state_delta=delta))


class BloodBankStage(BaseAgent):
    """Wraps BloodBankAgent.check_blood_availability."""

    blood_agent: BloodBankAgent


    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        surgery_dict = state[K.SURGERY_DICT]
        surgery_id = state[K.SURGERY_ID]

        available, status, blockers = self.blood_agent.check_blood_availability(
            surgery_dict['required_blood_type'],
            surgery_dict['required_blood_units'],
            surgery_id,
            surgery_dict['patient_id'],
        )

        delta = {
            K.BLOOD_AVAILABLE: available,
            K.BLOOD_STATUS: status.model_dump(mode="json"),
            K.BLOOD_BLOCKERS: [b.model_dump(mode="json") for b in blockers],
        }
        yield Event(author=self.name, actions=EventActions(state_delta=delta))


class OrganStage(BaseAgent):
    """Wraps OrganAgent.check_organ_availability."""

    organ_agent: OrganAgent


    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        surgery_dict = state[K.SURGERY_DICT]
        surgery_id = state[K.SURGERY_ID]

        available, status, blockers = self.organ_agent.check_organ_availability(
            surgery_dict.get('organ_type'),
            surgery_dict['patient_id'],
            surgery_id,
        )

        delta = {
            K.ORGAN_AVAILABLE: available,
            K.ORGAN_STATUS: status.model_dump(mode="json") if status else None,
            K.ORGAN_BLOCKERS: [b.model_dump(mode="json") for b in blockers],
        }
        yield Event(author=self.name, actions=EventActions(state_delta=delta))


class EquipmentStage(BaseAgent):
    """Wraps EquipmentAgent.check_equipment_availability."""

    equipment_agent: EquipmentAgent


    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        surgery_dict = state[K.SURGERY_DICT]
        surgery_id = state[K.SURGERY_ID]

        available, status, blockers = self.equipment_agent.check_equipment_availability(
            surgery_dict.get('equipment_list', []),
            surgery_id,
        )

        delta = {
            K.EQUIPMENT_AVAILABLE: available,
            K.EQUIPMENT_STATUS: status.model_dump(mode="json"),
            K.EQUIPMENT_BLOCKERS: [b.model_dump(mode="json") for b in blockers],
        }
        yield Event(author=self.name, actions=EventActions(state_delta=delta))


class ValidationStage(BaseAgent):
    """Wraps ValidationAgent.validate. Runs after the parallel resource checks."""

    validation_agent: ValidationAgent


    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        surgery_dict = state[K.SURGERY_DICT]
        surgery_id = state[K.SURGERY_ID]
        requested_at = state.get(K.REQUESTED_AT)
        requested_at = datetime.fromisoformat(requested_at) if isinstance(requested_at, str) else requested_at

        blood_status = ResourceStatus(**state[K.BLOOD_STATUS])
        organ_status = ResourceStatus(**state[K.ORGAN_STATUS]) if state.get(K.ORGAN_STATUS) else None
        equipment_status = ResourceStatus(**state[K.EQUIPMENT_STATUS])

        passed, blockers, warnings = self.validation_agent.validate(
            surgery_dict, blood_status, organ_status, equipment_status, requested_at, surgery_id
        )

        delta = {
            K.VALIDATION_PASSED: passed,
            K.VALIDATION_BLOCKERS: [b.model_dump(mode="json") for b in blockers],
            K.VALIDATION_WARNINGS: warnings,
        }
        yield Event(author=self.name, actions=EventActions(state_delta=delta))


class LogisticsStage(BaseAgent):
    """Wraps LogisticsAgent.estimate_logistics."""

    logistics_agent: LogisticsAgent


    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        surgery_dict = state[K.SURGERY_DICT]
        surgery_id = state[K.SURGERY_ID]

        blood_status = ResourceStatus(**state[K.BLOOD_STATUS])
        organ_status = ResourceStatus(**state[K.ORGAN_STATUS]) if state.get(K.ORGAN_STATUS) else None
        equipment_status = ResourceStatus(**state[K.EQUIPMENT_STATUS])

        logistics, warnings = self.logistics_agent.estimate_logistics(
            surgery_dict, blood_status, organ_status, equipment_status, surgery_id
        )

        delta = {
            K.LOGISTICS: logistics,
            K.LOGISTICS_WARNINGS: warnings,
        }
        yield Event(author=self.name, actions=EventActions(state_delta=delta))


class AggregatorStage(BaseAgent):
    """Deterministically aggregates all prior stages into the final readiness verdict.

    This is the safety-critical decision point: READY/BLOCKED must be pure
    logic over the collected blockers, never an LLM's opinion.
    """

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state

        if not state.get(K.PATIENT_EXTRACTION_OK):
            all_blockers = [_blocker("PATIENT_DATA", "Patient data extraction failed")]
            all_warnings = list(state.get(K.PATIENT_WARNINGS) or [])
            final_status = "BLOCKED"
        else:
            all_blockers = (
                list(state.get(K.SAFETY_BLOCKERS) or [])
                + list(state.get(K.BLOOD_BLOCKERS) or [])
                + list(state.get(K.ORGAN_BLOCKERS) or [])
                + list(state.get(K.EQUIPMENT_BLOCKERS) or [])
                + list(state.get(K.VALIDATION_BLOCKERS) or [])
            )
            all_warnings = (
                list(state.get(K.PATIENT_WARNINGS) or [])
                + list(state.get(K.SAFETY_WARNINGS) or [])
                + list(state.get(K.VALIDATION_WARNINGS) or [])
                + list(state.get(K.LOGISTICS_WARNINGS) or [])
            )

            all_ready = (
                state.get(K.SAFETY_PASSED, False)
                and state.get(K.BLOOD_AVAILABLE, False)
                and state.get(K.ORGAN_AVAILABLE, True)
                and state.get(K.EQUIPMENT_AVAILABLE, False)
                and state.get(K.VALIDATION_PASSED, False)
            )
            final_status = "READY" if all_ready else "BLOCKED"

        checklist = self._build_checklist(state, all_blockers)
        surgery_id = state[K.SURGERY_ID]

        summary = build_coordinator_input_summary(
            surgery_id, final_status, all_blockers, all_warnings, checklist, state
        )

        delta = {
            K.FINAL_STATUS: final_status,
            K.ALL_BLOCKERS: all_blockers,
            K.ALL_WARNINGS: all_warnings,
            K.PREOP_CHECKLIST: checklist,
            "coordinator_input_summary": json.dumps(summary, indent=2, default=str),
        }
        yield Event(author=self.name, actions=EventActions(state_delta=delta))

    @staticmethod
    def _build_checklist(state, all_blockers) -> list:
        items = [
            {"item": "Patient identity and blood type confirmed", "completed": bool(state.get(K.PATIENT_EXTRACTION_OK))},
            {"item": "Required consents verified and unexpired", "completed": bool(state.get(K.SAFETY_PASSED))},
            {"item": "Blood units reserved and crossmatched", "completed": bool(state.get(K.BLOOD_AVAILABLE))},
            {"item": "Equipment available, sterile, and within maintenance schedule", "completed": bool(state.get(K.EQUIPMENT_AVAILABLE))},
        ]
        if state.get(K.ORGAN_STATUS) is not None:
            items.append({"item": "Organ availability, compatibility, and viability confirmed", "completed": bool(state.get(K.ORGAN_AVAILABLE))})
        items.append({"item": "Cross-resource validation and timing checks passed", "completed": bool(state.get(K.VALIDATION_PASSED))})
        items.append({"item": "All blockers resolved", "completed": len(all_blockers) == 0})
        return items
