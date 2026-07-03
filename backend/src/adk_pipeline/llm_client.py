"""Thin OpenAI-compatible chat completions client.

Currently configured for OpenRouter serving gpt-oss-120b, but any
OpenAI-compatible `/chat/completions` endpoint works - base URL, API key,
and model are all environment variables (see backend/.env.example), never
hardcoded.

Each pipeline stage pre-fetches its ground-truth facts deterministically and
asks the model, via plain instruction, to return one JSON object matching a
documented schema, rather than relying on the provider's native tool-calling
support (which varies and isn't needed here - the orchestration layer
already knows what data each stage needs).
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60
RATE_LIMIT_BACKOFF_SECONDS = (3, 8, 20, 45)  # per retry attempt, on HTTP 429
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class LlmCallError(Exception):
    """Raised when the LLM endpoint cannot be reached or returns unusable output."""


def _api_base() -> str:
    base = os.environ.get("OPENROUTER_API_BASE")
    if not base:
        raise LlmCallError(
            "OPENROUTER_API_BASE is not set. Add it to backend/.env (see backend/.env.example)."
        )
    return base.rstrip("/")


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise LlmCallError(
            "OPENROUTER_API_KEY is not set. Add it to backend/.env (see backend/.env.example)."
        )
    return key


def _model() -> str:
    model = os.environ.get("LLM_MODEL")
    if not model:
        raise LlmCallError(
            "LLM_MODEL is not set. Add it to backend/.env (see backend/.env.example)."
        )
    return model


def _extract_json(text: str) -> Dict[str, Any]:
    """Parse the model's raw text as JSON, tolerating markdown code fences."""
    cleaned = _FENCE_RE.sub("", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Some models trail explanatory text after the JSON object; try to
        # isolate the first balanced {...} block.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise LlmCallError(f"Model did not return valid JSON: {text[:500]!r}")


def call_llm_json(
    system_prompt: str,
    user_content: str,
    model: Optional[str] = None,
    max_tokens: int = 800,
    temperature: float = 0.0,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_attempts: int = len(RATE_LIMIT_BACKOFF_SECONDS) + 1,
) -> Dict[str, Any]:
    """Call the configured LLM endpoint and parse the response as a single JSON object.

    Retries with backoff on HTTP 429 (the free-tier model is commonly
    rate-limited), since these bursts are expected when the parallel
    resource-check stages fire concurrently.

    Raises LlmCallError if the endpoint is unreachable/unconfigured or the
    model's response cannot be parsed as JSON after retries. This function
    is blocking (uses `requests` + `time.sleep`) - callers on an asyncio
    event loop should run it via `asyncio.to_thread`.
    """
    base = _api_base()
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or _model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(
                f"{base}/chat/completions", json=payload, headers=headers, timeout=timeout_seconds
            )
            if response.status_code == 429:
                raise requests.HTTPError(f"429 rate-limited: {response.text[:300]}", response=response)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return _extract_json(content)
        except (requests.RequestException, KeyError, IndexError, LlmCallError) as e:
            last_error = e
            is_rate_limited = isinstance(e, requests.HTTPError) and "429" in str(e)
            logger.warning("LLM call attempt %d/%d failed: %s", attempt, max_attempts, e)
            if attempt < max_attempts and is_rate_limited:
                delay = RATE_LIMIT_BACKOFF_SECONDS[min(attempt - 1, len(RATE_LIMIT_BACKOFF_SECONDS) - 1)]
                logger.info("Rate limited, backing off %ss before retry", delay)
                time.sleep(delay)

    raise LlmCallError(f"LLM call failed after {max_attempts} attempts: {last_error}")
