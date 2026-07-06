"""LlmReasoningStage - the shared base agent every pipeline stage is built on.

Every stage does exactly the same thing: gather facts deterministically,
send them + this stage's rules (its own agents.md file) to the configured
LLM endpoint, and write back whatever JSON object comes back. Each specific
agent (Patient Data, Safety/Consent, Blood Bank, ...) is just this base
agent configured with a different instruction file and a different
facts/fallback pair - there is no per-agent subclassing of behavior.
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Callable, Dict

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from src.adk_pipeline.llm_client import LlmCallError, call_llm_json

logger = logging.getLogger(__name__)

FactsBuilder = Callable[[Dict[str, Any]], Dict[str, Any]]
FallbackBuilder = Callable[[Dict[str, Any], str], Dict[str, Any]]


class LlmReasoningStage(BaseAgent):
    """One ADK pipeline stage backed by a single call to the configured LLM endpoint.

    Args (as pydantic fields, set via the constructor):
        instruction: this stage's rules, loaded from its agents.md file.
        output_state_key: session state key the parsed JSON result is written to.
        facts_builder: pulls this stage's ground-truth inputs from session state
            (reading prior stages' outputs and/or querying the mock data layer).
        fallback_builder: produces a safe result if the LLM call fails or
            returns unparseable output, so the pipeline never crashes and the
            failure is visible in the report instead of silent.
        max_tokens: generation limit for this stage's response.
    """

    instruction: str
    output_state_key: str
    facts_builder: FactsBuilder
    fallback_builder: FallbackBuilder
    max_tokens: int = 800

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        facts = self.facts_builder(state)
        user_content = "Facts:\n" + json.dumps(facts, indent=2, default=str)

        try:
            # call_llm_json is blocking (requests + backoff sleeps); run it off
            # the event loop so ParallelAgent's sub-agents actually run concurrently.
            result = await asyncio.to_thread(
                call_llm_json, self.instruction, user_content, max_tokens=self.max_tokens
            )
        except LlmCallError as e:
            logger.warning("[%s] LLM call failed, using fallback: %s", self.name, e)
            result = self.fallback_builder(facts, str(e))

        yield Event(author=self.name, actions=EventActions(state_delta={self.output_state_key: result}))
