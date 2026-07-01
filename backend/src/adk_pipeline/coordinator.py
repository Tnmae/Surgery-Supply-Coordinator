"""Coordinator narrator - the single LLM step in the pipeline.

Every readiness decision (READY/BLOCKED, blockers, checklist) is already
finalized by `AggregatorStage` using deterministic Python before this agent
ever runs. This agent's only job is to turn that already-decided structured
result into a short, human-readable clinical briefing. It cannot change the
status, and its instruction explicitly forbids inventing facts.
"""

import copy
from typing import Any, Dict

from google.adk.agents import Agent

from src.adk_pipeline import state_keys as K
from src.security.pii_redaction import PIIRedactor

DEFAULT_MODEL = "gemini-flash-latest"

COORDINATOR_INSTRUCTION = """You are a clinical decision-support briefing writer for an OR coordinator.

The readiness decision below was already made by deterministic, rule-based
checks (blood bank, safety/consent, organ, equipment, and cross-validation
agents) - not by you. You must not change, second-guess, or re-derive the
status. Your only job is to turn the structured findings into a short,
clear, professional briefing.

Structured findings (already finalized, patient identifiers redacted):
{coordinator_input_summary}

Write a briefing of 4-8 sentences that:
1. States the final readiness status plainly in the first sentence.
2. Explains the key blockers (if any) in plain clinical language, grouped by category.
3. Notes any warnings or time-critical logistics constraints worth flagging.
4. Closes with a reminder that this is decision-support only and requires review and approval by qualified clinical personnel before any action is taken.

Do not invent statuses, resource counts, or facts beyond what is given above.
"""


def create_coordinator_narrator_agent(model: str = DEFAULT_MODEL) -> Agent:
    """Factory for the coordinator LLM agent. Call this fresh for each pipeline build."""
    return Agent(
        name="coordinator_narrator",
        model=model,
        instruction=COORDINATOR_INSTRUCTION,
        description="Turns the finalized readiness verdict into a human-readable clinical briefing.",
        output_key=K.COORDINATOR_NARRATIVE,
    )


def build_coordinator_input_summary(
    surgery_id: str,
    final_status: str,
    all_blockers: list,
    all_warnings: list,
    preop_checklist: list,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the PII-redacted summary the coordinator LLM is allowed to see.

    Sent to an external LLM API, so patient/donor identifiers are redacted
    even though the API's own JSON response does not redact them for the
    OR coordinator's direct use.
    """
    summary = {
        "surgery_id": surgery_id,
        "final_status": final_status,
        "blockers": all_blockers,
        "warnings": all_warnings,
        "preop_checklist": preop_checklist,
        "logistics": state.get(K.LOGISTICS),
        "resource_status": {
            "blood": state.get(K.BLOOD_STATUS),
            "organ": state.get(K.ORGAN_STATUS),
            "equipment": state.get(K.EQUIPMENT_STATUS),
        },
    }
    return PIIRedactor.redact_dict(copy.deepcopy(summary))


def build_fallback_narrative(state: Dict[str, Any]) -> str:
    """Deterministic template used when no LLM is configured (no GOOGLE_API_KEY)."""
    status = state.get(K.FINAL_STATUS, "UNKNOWN")
    blockers = state.get(K.ALL_BLOCKERS, [])
    warnings = state.get(K.ALL_WARNINGS, [])

    lines = [f"Readiness status: {status}."]
    if blockers:
        lines.append("Blockers:")
        for b in blockers:
            lines.append(f"  - [{b.get('severity')}] {b.get('category')}: {b.get('message')}")
    if warnings:
        lines.append("Warnings:")
        for w in warnings:
            lines.append(f"  - {w}")
    lines.append(
        "This is decision-support only. All findings must be reviewed and "
        "approved by qualified clinical personnel before any action is taken."
    )
    return "\n".join(lines)
