"""ADK-orchestrated readiness pipeline.

Wires the agents in `src.agents` together with Google ADK's `SequentialAgent`
and `ParallelAgent` workflow primitives, matching the pipeline described in
the project README:

    Patient Data -> Safety/Consent -> [Blood | Organ | Equipment] (parallel)
    -> Validation -> Logistics -> Coordinator -> human review

All clinical/safety logic (consents, compatibility, blockers) runs in
deterministic Python agents - never inside an LLM - so the readiness verdict
can never be hallucinated. The one LLM step (the coordinator) only turns the
already-decided structured result into a human-readable narrative.
"""
