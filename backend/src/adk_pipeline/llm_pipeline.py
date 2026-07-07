"""Assembles and runs the LLM-per-agent surgery readiness pipeline.

Every agent below is the same `LlmReasoningStage` base agent (see
`llm_reasoning_stage.py`), configured with its own rules file
(`prompts/*.md`) and its own facts. The only thing that differs between
"Blood Bank Agent" and "Organ Agent" is which prompt file and which facts
it's given - the underlying mechanism (call the LLM endpoint, parse JSON,
write state) is identical. Orchestration is real ADK `SequentialAgent` /
`ParallelAgent`, matching the same topology as the deterministic pipeline in
`pipeline.py`.

Model: gpt-oss-120b via OpenRouter (OPENROUTER_API_BASE / OPENROUTER_API_KEY
/ LLM_MODEL in backend/.env) - any OpenAI-compatible endpoint works, see
`llm_client.py`.
"""

from datetime import datetime
import logging

from google.adk.agents import ParallelAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from src.adk_pipeline import state_keys as K
from src.adk_pipeline.llm_stages import (
    build_blood_bank_stage,
    build_coordinator_stage,
    build_equipment_stage,
    build_logistics_stage,
    build_organ_stage,
    build_patient_data_stage,
    build_safety_consent_stage,
    build_validation_stage,
)
from src.data.repository import DataRepository
from src.mcp_servers.regional_fallback_mcp import RegionalFallbackMCPServer
from src.security.audit_logger import AuditLogger

APP_NAME = "surgery_supply_coordinator_llm"
logger = logging.getLogger(__name__)


def build_llm_pipeline(repository: DataRepository) -> SequentialAgent:
    """Build the 8-agent, all-LLM SequentialAgent pipeline."""
    fallback = RegionalFallbackMCPServer()

    return SequentialAgent(
        name="surgery_readiness_llm_pipeline",
        sub_agents=[
            build_patient_data_stage(repository),
            build_safety_consent_stage(repository),
            ParallelAgent(
                name="resource_checks_llm",
                sub_agents=[
                    build_blood_bank_stage(repository, fallback),
                    build_organ_stage(repository, fallback),
                    build_equipment_stage(repository),
                ],
            ),
            build_validation_stage(),
            build_logistics_stage(),
            build_coordinator_stage(),
        ],
    )


async def run_llm_readiness_pipeline(
    surgery_id: str,
    user_role: str,
    repository: DataRepository,
    audit_logger: AuditLogger,
) -> dict:
    """Run the LLM-per-agent readiness pipeline for a surgery and return the report dict."""
    surgery_dict = repository.get_surgery(surgery_id)
    if not surgery_dict:
        return {"success": False, "message": f"Surgery {surgery_id} not found"}

    root_agent = build_llm_pipeline(repository)

    session_service = InMemorySessionService()
    session_id = f"llm-session-{surgery_id}-{datetime.utcnow().timestamp()}"
    requested_at = datetime.utcnow()

    initial_state = {
        K.SURGERY_ID: surgery_id,
        K.USER_ROLE: user_role,
        K.REQUESTED_AT: requested_at.isoformat(),
        K.SURGERY_DICT: surgery_dict,
    }

    await session_service.create_session(
        app_name=APP_NAME, user_id=user_role, session_id=session_id, state=initial_state
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
        import traceback
        tb = traceback.format_exc()
        logger.error("LLM pipeline error for %s:\n%s", surgery_id, tb)
        audit_logger.log_action(
            action="LLM_PIPELINE_ERROR",
            actor_role=user_role,
            entity_type="SURGERY",
            entity_id=surgery_id,
            error=str(e),
            result="FAILURE",
        )
        return {
            "success": False,
            "message": "LLM pipeline execution failed",
            "error": str(e),
            "error_type": type(e).__name__,
        }

    session = await session_service.get_session(app_name=APP_NAME, user_id=user_role, session_id=session_id)
    state = session.state

    coordinator_result = state.get(K.COORDINATOR_LLM_RESULT, {})

    report = {
        "success": True,
        "message": f"Readiness check completed - Status: {coordinator_result.get('final_status')}",
        "readiness_status": coordinator_result.get("final_status"),
        "surgery_id": surgery_id,
        "patient_id": surgery_dict["patient_id"],
        "scheduled_time": surgery_dict["scheduled_time"],
        "blockers": coordinator_result.get("all_blockers", []),
        "warnings": coordinator_result.get("all_warnings", []),
        "preop_checklist": coordinator_result.get("preop_checklist", []),
        "agent_results": {
            "patient_data": state.get(K.PATIENT_LLM_RESULT),
            "safety_consent": state.get(K.SAFETY_LLM_RESULT),
            "blood": state.get(K.BLOOD_LLM_RESULT),
            "organ": state.get(K.ORGAN_LLM_RESULT),
            "equipment": state.get(K.EQUIPMENT_LLM_RESULT),
            "validation": state.get(K.VALIDATION_LLM_RESULT),
            "logistics": state.get(K.LOGISTICS_LLM_RESULT),
        },
        "human_readable_report": coordinator_result.get("human_readable_report"),
        "timestamp": datetime.utcnow().isoformat(),
        "review_required": True,
    }

    audit_logger.log_action(
        action="LLM_CHECK_READINESS_COMPLETED",
        actor_role=user_role,
        entity_type="SURGERY",
        entity_id=surgery_id,
        details={"status": coordinator_result.get("final_status")},
        result="SUCCESS",
    )

    return report
