"""Assembles and runs the ADK-orchestrated surgery readiness pipeline.

Topology (matches the README architecture diagram):

    SequentialAgent(
        PatientDataStage,
        SafetyConsentStage,
        ParallelAgent(BloodBankStage, OrganStage, EquipmentStage),
        ValidationStage,
        LogisticsStage,
        AggregatorStage,
        [coordinator_narrator]   # LLM step, only if GOOGLE_API_KEY is configured
    )
"""

import os
from datetime import datetime
from typing import Optional, Tuple

from google.adk.agents import ParallelAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from src.agents.patient_data_agent import PatientDataAgent
from src.agents.safety_consent_agent import SafetyConsentAgent
from src.agents.blood_bank_agent import BloodBankAgent
from src.agents.organ_agent import OrganAgent
from src.agents.equipment_agent import EquipmentAgent
from src.agents.validation_agent import ValidationAgent
from src.agents.logistics_agent import LogisticsAgent
from src.data.repository import DataRepository
from src.mcp_servers.regional_fallback_mcp import RegionalFallbackMCPServer
from src.security.audit_logger import AuditLogger

from src.adk_pipeline import state_keys as K
from src.adk_pipeline.coordinator import DEFAULT_MODEL, build_fallback_narrative, create_coordinator_narrator_agent
from src.adk_pipeline.stages import (
    AggregatorStage,
    BloodBankStage,
    EquipmentStage,
    LogisticsStage,
    OrganStage,
    PatientDataStage,
    SafetyConsentStage,
    ValidationStage,
)

APP_NAME = "surgery_supply_coordinator"


def llm_coordinator_available() -> bool:
    """Whether credentials are present to run the coordinator's LLM step."""
    return bool(
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true"
    )


def build_pipeline(
    repository: DataRepository,
    audit_logger: AuditLogger,
    use_llm_coordinator: Optional[bool] = None,
) -> Tuple[SequentialAgent, bool]:
    """Build the SequentialAgent pipeline. Returns (root_agent, used_llm_coordinator)."""
    fallback = RegionalFallbackMCPServer()

    stages = [
        PatientDataStage(
            name="patient_data_stage",
            patient_agent=PatientDataAgent(repository, audit_logger),
        ),
        SafetyConsentStage(
            name="safety_consent_stage",
            safety_agent=SafetyConsentAgent(repository, audit_logger),
        ),
        ParallelAgent(
            name="resource_checks",
            sub_agents=[
                BloodBankStage(
                    name="blood_bank_stage",
                    blood_agent=BloodBankAgent(repository, fallback_server=fallback, audit_logger=audit_logger),
                ),
                OrganStage(
                    name="organ_stage",
                    organ_agent=OrganAgent(repository, fallback_server=fallback, audit_logger=audit_logger),
                ),
                EquipmentStage(
                    name="equipment_stage",
                    equipment_agent=EquipmentAgent(repository, audit_logger=audit_logger),
                ),
            ],
        ),
        ValidationStage(
            name="validation_stage",
            validation_agent=ValidationAgent(audit_logger=audit_logger),
        ),
        LogisticsStage(
            name="logistics_stage",
            logistics_agent=LogisticsAgent(audit_logger=audit_logger),
        ),
        AggregatorStage(name="aggregator_stage"),
    ]

    use_llm = llm_coordinator_available() if use_llm_coordinator is None else use_llm_coordinator
    if use_llm:
        stages.append(create_coordinator_narrator_agent(model=DEFAULT_MODEL))

    root_agent = SequentialAgent(name="surgery_readiness_pipeline", sub_agents=stages)
    return root_agent, use_llm


async def run_readiness_pipeline(
    surgery_id: str,
    user_role: str,
    repository: DataRepository,
    audit_logger: AuditLogger,
) -> dict:
    """Run the full ADK readiness pipeline for a surgery and return the report dict."""
    surgery_dict = repository.get_surgery(surgery_id)
    if not surgery_dict:
        return {"success": False, "message": f"Surgery {surgery_id} not found"}

    root_agent, used_llm = build_pipeline(repository, audit_logger)

    session_service = InMemorySessionService()
    session_id = f"session-{surgery_id}-{datetime.utcnow().timestamp()}"
    requested_at = datetime.utcnow()

    initial_state = {
        K.SURGERY_ID: surgery_id,
        K.USER_ROLE: user_role,
        K.REQUESTED_AT: requested_at.isoformat(),
        K.SURGERY_DICT: surgery_dict,
    }

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_role,
        session_id=session_id,
        state=initial_state,
    )

    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

    try:
        async for _event in runner.run_async(
            user_id=user_role,
            session_id=session_id,
            new_message=genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text=f"Run readiness check for surgery {surgery_id}.")],
            ),
        ):
            pass
    except Exception as e:
        audit_logger.log_action(
            action="ADK_PIPELINE_ERROR",
            actor_role=user_role,
            entity_type="SURGERY",
            entity_id=surgery_id,
            error=str(e),
            result="FAILURE",
        )
        return {"success": False, "message": "ADK pipeline execution failed", "error": str(e)}

    session = await session_service.get_session(app_name=APP_NAME, user_id=user_role, session_id=session_id)
    state = session.state

    narrative = state.get(K.COORDINATOR_NARRATIVE)
    if not narrative:
        narrative = build_fallback_narrative(state)

    report = {
        "success": True,
        "message": f"Readiness check completed - Status: {state.get(K.FINAL_STATUS)}",
        "readiness_status": state.get(K.FINAL_STATUS),
        "surgery_id": surgery_id,
        "patient_id": surgery_dict["patient_id"],
        "scheduled_time": surgery_dict["scheduled_time"],
        "blockers": state.get(K.ALL_BLOCKERS, []),
        "warnings": state.get(K.ALL_WARNINGS, []),
        "preop_checklist": state.get(K.PREOP_CHECKLIST, []),
        "resource_status": {
            "blood": state.get(K.BLOOD_STATUS),
            "organ": state.get(K.ORGAN_STATUS),
            "equipment": state.get(K.EQUIPMENT_STATUS),
        },
        "logistics": state.get(K.LOGISTICS),
        "human_readable_report": narrative,
        "coordinator_used_llm": used_llm,
        "timestamp": datetime.utcnow().isoformat(),
        "review_required": True,
    }

    audit_logger.log_action(
        action="ADK_CHECK_READINESS_COMPLETED",
        actor_role=user_role,
        entity_type="SURGERY",
        entity_id=surgery_id,
        details={"status": state.get(K.FINAL_STATUS), "used_llm_coordinator": used_llm},
        result="SUCCESS",
    )

    return report
