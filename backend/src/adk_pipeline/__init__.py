"""ADK-orchestrated readiness pipeline.

Wires eight `LlmReasoningStage` agents (see `llm_reasoning_stage.py` and
`llm_stages.py`) together with Google ADK's `SequentialAgent` and
`ParallelAgent` workflow primitives, matching the pipeline described in the
project README:

    Patient Data -> Safety/Consent -> [Blood | Organ | Equipment] (parallel)
    -> Validation -> Logistics -> Coordinator -> human review

Agents fire automatically in this sequence - ADK orchestration decides that,
not an LLM - but every stage's own judgment is an LLM call against its
prompt file under `prompts/`. Because none of the clinical/safety logic is
deterministic Python, the resulting report is decision-support only and
always requires human review before any action is taken.
"""
