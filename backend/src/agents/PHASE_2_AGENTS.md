"""Phase 2 agents - implemented."""

# Organ, Equipment, Validation, and Logistics agents are implemented in
# organ_agent.py, equipment_agent.py, validation_agent.py, and
# logistics_agent.py respectively. The Coordinator Agent's deterministic
# aggregation lives in src/adk_pipeline/stages.py (AggregatorStage); its
# optional LLM narrative step lives in src/adk_pipeline/coordinator.py.
#
# All eight agents are wired together as a Google ADK orchestration pipeline
# in src/adk_pipeline/pipeline.py, exposed via POST /check-readiness/pipeline.
