"""Factory functions building each pipeline stage as a LlmReasoningStage.

Every stage follows the same shape: deterministically gather ground-truth
facts from the mock data layer (repository / MCP servers) or from prior
stages' JSON results already in session state, then hand those facts + this
stage's own agents.md rules file to the shared LLM base agent. No stage
re-implements judgment in Python - that now lives entirely in the prompt
files under `prompts/`.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from src.adk_pipeline import state_keys as K
from src.adk_pipeline.llm_reasoning_stage import LlmReasoningStage
from src.data.repository import DataRepository
from src.mcp_servers.blood_bank_mcp import BloodBankMCPServer
from src.mcp_servers.equipment_inventory_mcp import EquipmentInventoryMCPServer
from src.mcp_servers.organ_registry_mcp import OrganRegistryMCPServer
from src.mcp_servers.regional_fallback_mcp import RegionalFallbackMCPServer
from src.models.blood import BloodBankQuery, BloodType
from src.models.organ import OrganRegistryQuery, OrganType

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def build_patient_data_stage(repository: DataRepository) -> LlmReasoningStage:
    def facts_builder(state: Dict[str, Any]) -> Dict[str, Any]:
        surgery_dict = state[K.SURGERY_DICT]
        patient = repository.get_patient(surgery_dict["patient_id"])
        return {
            "patient_record": patient,
            "required_blood_type": surgery_dict.get("required_blood_type"),
        }

    def fallback_builder(facts: Dict[str, Any], error: str) -> Dict[str, Any]:
        return {
            "extraction_successful": False,
            "missing_fields": ["llm_error"],
            "warnings": [f"Patient Data agent failed: {error}"],
        }

    return LlmReasoningStage(
        name="patient_data_llm_stage",
        instruction=_load_prompt("patient_data.md"),
        output_state_key=K.PATIENT_LLM_RESULT,
        facts_builder=facts_builder,
        fallback_builder=fallback_builder,
    )


def build_safety_consent_stage(repository: DataRepository) -> LlmReasoningStage:
    def facts_builder(state: Dict[str, Any]) -> Dict[str, Any]:
        surgery_dict = state[K.SURGERY_DICT]
        patient = repository.get_patient(surgery_dict["patient_id"]) or {}
        return {
            "surgery_type": surgery_dict.get("surgery_type"),
            "now": datetime.utcnow().isoformat(),
            "consents": patient.get("consents", []),
            "allergies": patient.get("allergies", []),
            "contraindications": patient.get("contraindications", []),
            "medications": patient.get("medications", []),
        }

    def fallback_builder(facts: Dict[str, Any], error: str) -> Dict[str, Any]:
        return {
            "passed": False,
            "blockers": [{
                "category": "SAFETY_CONSENT",
                "severity": "CRITICAL",
                "message": f"Safety/Consent agent failed: {error}",
                "suggested_action": "Manual clinical review required",
            }],
            "warnings": [],
        }

    return LlmReasoningStage(
        name="safety_consent_llm_stage",
        instruction=_load_prompt("safety_consent.md"),
        output_state_key=K.SAFETY_LLM_RESULT,
        facts_builder=facts_builder,
        fallback_builder=fallback_builder,
    )


def build_blood_bank_stage(
    repository: DataRepository, fallback_server: RegionalFallbackMCPServer
) -> LlmReasoningStage:
    blood_server = BloodBankMCPServer(repository, fallback_server)

    def facts_builder(state: Dict[str, Any]) -> Dict[str, Any]:
        surgery_dict = state[K.SURGERY_DICT]
        query = BloodBankQuery(
            blood_type=BloodType(surgery_dict["required_blood_type"]),
            units_needed=surgery_dict["required_blood_units"],
            patient_id=surgery_dict["patient_id"],
        )
        response = blood_server.query_blood_availability(query)
        hours_to_exp = None
        if response.earliest_expiration:
            hours_to_exp = (response.earliest_expiration - datetime.utcnow()).total_seconds() / 3600
        return {
            "blood_type": surgery_dict["required_blood_type"],
            "units_needed": surgery_dict["required_blood_units"],
            "units_available": response.units_available,
            "units_pending_crossmatch": response.units_pending_crossmatch,
            "earliest_expiration_hours_away": hours_to_exp,
            "fallback_available": response.fallback_available,
        }

    def fallback_builder(facts: Dict[str, Any], error: str) -> Dict[str, Any]:
        return {
            "available": False,
            "status": "BLOCKED",
            "details": f"Blood Bank agent failed: {error}",
            "units_pending_crossmatch": facts.get("units_pending_crossmatch", 0),
            "fallback_required": True,
            "blockers": [{
                "category": "BLOOD",
                "severity": "HIGH",
                "message": f"Error checking blood availability: {error}",
                "suggested_action": "Contact blood bank for manual check",
            }],
        }

    return LlmReasoningStage(
        name="blood_bank_llm_stage",
        instruction=_load_prompt("blood_bank.md"),
        output_state_key=K.BLOOD_LLM_RESULT,
        facts_builder=facts_builder,
        fallback_builder=fallback_builder,
    )


def build_organ_stage(
    repository: DataRepository, fallback_server: RegionalFallbackMCPServer
) -> LlmReasoningStage:
    organ_server = OrganRegistryMCPServer(repository, fallback_server)

    def facts_builder(state: Dict[str, Any]) -> Dict[str, Any]:
        surgery_dict = state[K.SURGERY_DICT]
        organ_type = surgery_dict.get("organ_type")
        if not organ_type:
            return {"organ_required": False}

        query = OrganRegistryQuery(
            organ_type=OrganType(organ_type),
            recipient_patient_id=surgery_dict["patient_id"],
        )
        response = organ_server.query_organ_availability(query)
        facts: Dict[str, Any] = {
            "organ_required": True,
            "organ_type": organ_type,
            "found_local_match": response.available,
            "viability_risk_level": response.viability_risk_level,
            "fallback_available": fallback_server.has_organ(organ_type),
        }
        if response.best_match:
            compat = organ_server.check_donor_compatibility(
                response.best_match.organ_id, surgery_dict["patient_id"]
            )
            facts.update({
                "organ_id": response.best_match.organ_id,
                "donor_blood_type": response.best_match.donor_blood_type,
                "donor_compatible": compat.get("compatible", False),
            })
        return facts

    def fallback_builder(facts: Dict[str, Any], error: str) -> Dict[str, Any]:
        if not facts.get("organ_required", False):
            return {
                "applicable": False,
                "available": True,
                "status": "OK",
                "details": "No organ required for this surgery",
                "viability_risk_level": "NONE",
                "needs_transfer": False,
                "blockers": [],
            }
        return {
            "applicable": True,
            "available": False,
            "status": "BLOCKED",
            "details": f"Organ agent failed: {error}",
            "viability_risk_level": facts.get("viability_risk_level", "HIGH"),
            "needs_transfer": not facts.get("found_local_match", False),
            "blockers": [{
                "category": "ORGAN",
                "severity": "HIGH",
                "message": f"Error checking organ availability: {error}",
                "suggested_action": "Contact organ registry for manual check",
            }],
        }

    return LlmReasoningStage(
        name="organ_llm_stage",
        instruction=_load_prompt("organ.md"),
        output_state_key=K.ORGAN_LLM_RESULT,
        facts_builder=facts_builder,
        fallback_builder=fallback_builder,
    )


def build_equipment_stage(repository: DataRepository) -> LlmReasoningStage:
    def facts_builder(state: Dict[str, Any]) -> Dict[str, Any]:
        surgery_dict = state[K.SURGERY_DICT]
        equipment_list = surgery_dict.get("equipment_list", [])
        details = {name: repository.get_equipment_by_name(name) for name in equipment_list}
        return {
            "requested_equipment": equipment_list,
            "equipment_details": details,
            "now": datetime.utcnow().isoformat(),
        }

    def fallback_builder(facts: Dict[str, Any], error: str) -> Dict[str, Any]:
        requested = facts.get("requested_equipment", [])
        return {
            "all_available": len(requested) == 0,
            "status": "BLOCKED" if requested else "OK",
            "details": f"Equipment agent failed: {error}" if requested else "No equipment required",
            "unavailable": requested,
            "maintenance_concerns": [],
            "blockers": ([{
                "category": "EQUIPMENT",
                "severity": "HIGH",
                "message": f"Error checking equipment availability: {error}",
                "suggested_action": "Contact supply admin for manual equipment check",
            }] if requested else []),
        }

    return LlmReasoningStage(
        name="equipment_llm_stage",
        instruction=_load_prompt("equipment.md"),
        output_state_key=K.EQUIPMENT_LLM_RESULT,
        facts_builder=facts_builder,
        fallback_builder=fallback_builder,
    )


def build_validation_stage() -> LlmReasoningStage:
    def facts_builder(state: Dict[str, Any]) -> Dict[str, Any]:
        surgery_dict = state[K.SURGERY_DICT]
        return {
            "scheduled_time": surgery_dict.get("scheduled_time"),
            "requested_at": state.get(K.REQUESTED_AT),
            "blood_result": state.get(K.BLOOD_LLM_RESULT),
            "organ_result": state.get(K.ORGAN_LLM_RESULT),
            "equipment_result": state.get(K.EQUIPMENT_LLM_RESULT),
        }

    def fallback_builder(facts: Dict[str, Any], error: str) -> Dict[str, Any]:
        return {
            "passed": False,
            "blockers": [{
                "category": "VALIDATION",
                "severity": "HIGH",
                "message": f"Validation agent failed: {error}",
                "suggested_action": "Manual cross-resource check required",
            }],
            "warnings": [],
        }

    return LlmReasoningStage(
        name="validation_llm_stage",
        instruction=_load_prompt("validation.md"),
        output_state_key=K.VALIDATION_LLM_RESULT,
        facts_builder=facts_builder,
        fallback_builder=fallback_builder,
    )


def build_logistics_stage() -> LlmReasoningStage:
    def facts_builder(state: Dict[str, Any]) -> Dict[str, Any]:
        surgery_dict = state[K.SURGERY_DICT]
        return {
            "estimated_duration_minutes": surgery_dict.get("estimated_duration_minutes", 0),
            "blood_result": state.get(K.BLOOD_LLM_RESULT),
            "organ_result": state.get(K.ORGAN_LLM_RESULT),
        }

    def fallback_builder(facts: Dict[str, Any], error: str) -> Dict[str, Any]:
        return {
            "estimated_duration_minutes": facts.get("estimated_duration_minutes", 0),
            "transport_time_hours": 0.0,
            "total_timeline_minutes": facts.get("estimated_duration_minutes", 0),
            "time_critical": False,
            "notes": [],
            "warnings": [f"Logistics agent failed: {error}"],
        }

    return LlmReasoningStage(
        name="logistics_llm_stage",
        instruction=_load_prompt("logistics.md"),
        output_state_key=K.LOGISTICS_LLM_RESULT,
        facts_builder=facts_builder,
        fallback_builder=fallback_builder,
    )


def build_coordinator_stage() -> LlmReasoningStage:
    def facts_builder(state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "surgery_id": state.get(K.SURGERY_ID),
            "patient_result": state.get(K.PATIENT_LLM_RESULT),
            "safety_result": state.get(K.SAFETY_LLM_RESULT),
            "blood_result": state.get(K.BLOOD_LLM_RESULT),
            "organ_result": state.get(K.ORGAN_LLM_RESULT),
            "equipment_result": state.get(K.EQUIPMENT_LLM_RESULT),
            "validation_result": state.get(K.VALIDATION_LLM_RESULT),
            "logistics_result": state.get(K.LOGISTICS_LLM_RESULT),
        }

    def fallback_builder(facts: Dict[str, Any], error: str) -> Dict[str, Any]:
        return {
            "final_status": "BLOCKED",
            "all_blockers": [{
                "category": "COORDINATOR",
                "severity": "CRITICAL",
                "message": f"Coordinator agent failed: {error}",
                "suggested_action": "Manual review of all agent outputs required",
            }],
            "all_warnings": [],
            "preop_checklist": [],
            "human_readable_report": (
                "The coordinator could not generate a briefing due to an internal "
                "error. Treat this surgery as BLOCKED pending manual review of all "
                "individual agent results."
            ),
        }

    return LlmReasoningStage(
        name="coordinator_llm_stage",
        instruction=_load_prompt("coordinator.md"),
        output_state_key=K.COORDINATOR_LLM_RESULT,
        facts_builder=facts_builder,
        fallback_builder=fallback_builder,
        max_tokens=1500,
    )
