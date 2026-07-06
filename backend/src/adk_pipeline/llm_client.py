"""Thin LLM client for the readiness pipeline.

Supports OpenRouter/OpenAI-compatible chat completions, Google AI Studio
(Gemini), or a local Ollama server through the provider selected in
environment variables. The base URL, API key, provider, and model are all
environment variables (see backend/.env.example), never hardcoded.

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


def _provider() -> str:
    provider = os.environ.get("LLM_PROVIDER")
    if provider:
        return provider.strip().lower()

    if os.environ.get("OLLAMA_BASE_URL"):
        return "ollama"

    if os.environ.get("CLOUDFLARE_API_KEY") and os.environ.get("CLOUDFLARE_ACCOUNT_ID"):
        return "cloudflare"

    if os.environ.get("GOOGLE_AI_API_KEY") and not os.environ.get("OPENROUTER_API_KEY"):
        return "google"

    return "openrouter"


def _normalize_base_url(base: str) -> str:
    base = base.rstrip("/")
    if base.endswith("/chat/completions") or base.endswith("/generateContent"):
        return base
    return base


def _api_base() -> str:
    provider = _provider()
    if provider == "ollama":
        base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        return _normalize_base_url(base)

    # cloudflare and google build their own full URLs — no shared base needed
    if provider in ("cloudflare", "google"):
        return ""

    base = os.environ.get("OPENROUTER_API_BASE")
    if not base:
        raise LlmCallError(
            "OPENROUTER_API_BASE is not set. Add it to backend/.env (see backend/.env.example)."
        )
    return base.rstrip("/")


def _api_key() -> str:
    provider = _provider()
    if provider == "google":
        key = os.environ.get("GOOGLE_AI_API_KEY")
        if not key:
            raise LlmCallError(
                "GOOGLE_AI_API_KEY is not set. Add it to backend/.env (see backend/.env.example)."
            )
        return key

    if provider == "ollama":
        return os.environ.get("OLLAMA_API_KEY", "ollama")

    if provider == "cloudflare":
        key = os.environ.get("CLOUDFLARE_API_KEY")
        if not key:
            raise LlmCallError(
                "CLOUDFLARE_API_KEY is not set. Add it to backend/.env (see backend/.env.example)."
            )
        return key

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise LlmCallError(
            "OPENROUTER_API_KEY is not set. Add it to backend/.env (see backend/.env.example)."
        )
    return key


def _model() -> str:
    if _provider() == "ollama":
        return os.environ.get("OLLAMA_MODEL") or os.environ.get("LLM_MODEL") or "llama3.2:latest"

    if _provider() == "google":
        return os.environ.get("GOOGLE_AI_MODEL") or os.environ.get("LLM_MODEL") or "gemini-2.0-flash"

    if _provider() == "cloudflare":
        return (
            os.environ.get("CLOUDFLARE_MODEL")
            or os.environ.get("LLM_MODEL")
            or "@cf/meta/llama-3.1-8b-instruct"
        )

    model = os.environ.get("LLM_MODEL")
    if not model:
        raise LlmCallError("LLM_MODEL is not set. Add it to backend/.env (see backend/.env.example).")
    return model


def _call_openrouter_json(
    system_prompt: str,
    user_content: str,
    model: Optional[str],
    max_tokens: int,
    temperature: float,
    timeout_seconds: int,
    max_attempts: int,
) -> Dict[str, Any]:
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


def _call_ollama_json(
    system_prompt: str,
    user_content: str,
    model: Optional[str],
    max_tokens: int,
    temperature: float,
    timeout_seconds: int,
    max_attempts: int,
) -> Dict[str, Any]:
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
        "stream": False,
        "format": "json",
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
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


def _ollama_timeout_seconds(requested_timeout_seconds: int) -> int:
    configured_timeout = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "30"))
    return min(requested_timeout_seconds, configured_timeout)


def _ollama_max_tokens(requested_max_tokens: int) -> int:
    configured_max_tokens = int(os.environ.get("OLLAMA_MAX_TOKENS", "256"))
    return min(requested_max_tokens, configured_max_tokens)


def _call_google_json(
    system_prompt: str,
    user_content: str,
    model: Optional[str],
    max_tokens: int,
    temperature: float,
    timeout_seconds: int,
    max_attempts: int,
) -> Dict[str, Any]:
    api_key = _api_key()
    model_name = (model or _model()).replace("models/", "")
    headers = {"Content-Type": "application/json"}
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }

    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent",
                params={"key": api_key},
                json=payload,
                headers=headers,
                timeout=timeout_seconds,
            )
            if response.status_code == 429:
                raise requests.HTTPError(f"429 rate-limited: {response.text[:300]}", response=response)
            response.raise_for_status()
            data = response.json()
            content_parts = data["candidates"][0]["content"]["parts"]
            content = "".join(part.get("text", "") for part in content_parts if isinstance(part, dict))
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


def _call_cloudflare_json(
    system_prompt: str,
    user_content: str,
    model: Optional[str],
    max_tokens: int,
    temperature: float,
    timeout_seconds: int,
    max_attempts: int,
) -> Dict[str, Any]:
    """Call Cloudflare Workers AI REST API (not OpenAI-compatible).
    
    Docs: https://developers.cloudflare.com/workers-ai/models/
    """
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not account_id:
        raise LlmCallError(
            "CLOUDFLARE_ACCOUNT_ID is not set. Add it to backend/.env (see backend/.env.example)."
        )

    api_key = _api_key()
    model_name = model or _model()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # Cloudflare Workers AI expects messages array directly (no 'model' field in body)
    payload = {
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
            url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_name}"
            logger.info(
                "[cloudflare] LLM request → %s max_tokens=%d attempt=%d/%d",
                url, max_tokens, attempt, max_attempts,
            )
            response = requests.post(url, json=payload, headers=headers, timeout=timeout_seconds)
            if response.status_code == 429:
                raise requests.HTTPError(f"429 rate-limited: {response.text[:300]}", response=response)
            response.raise_for_status()
            data = response.json()
            
            # Cloudflare response shape: { "result": { "response": "..." }, "success": true }
            if not data.get("success"):
                raise LlmCallError(f"Cloudflare API returned success=false: {data}")
            
            content = data["result"]["response"]
            result = _extract_json(content)
            logger.info(
                "[cloudflare] LLM response ← HTTP %d, %d chars, parsed OK",
                response.status_code, len(content),
            )
            return result
        except (requests.RequestException, KeyError, IndexError, LlmCallError) as e:
            last_error = e
            is_rate_limited = isinstance(e, requests.HTTPError) and "429" in str(e)
            logger.warning("LLM call attempt %d/%d failed: %s", attempt, max_attempts, e)
            if attempt < max_attempts and is_rate_limited:
                delay = RATE_LIMIT_BACKOFF_SECONDS[min(attempt - 1, len(RATE_LIMIT_BACKOFF_SECONDS) - 1)]
                logger.info("Rate limited, backing off %ss before retry", delay)
                time.sleep(delay)

    raise LlmCallError(f"LLM call failed after {max_attempts} attempts: {last_error}")


def _extract_json(text: str) -> Dict[str, Any]:
    """Parse the model's raw text as JSON, tolerating markdown code fences."""
    cleaned = text.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1].strip()

    cleaned = _FENCE_RE.sub("", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Some models include extra prose or multiple example blocks.
        # Extract the first balanced JSON object and ignore the rest.
        start = cleaned.find("{")
        if start != -1:
            depth = 0
            in_string = False
            escape = False
            for index in range(start, len(cleaned)):
                char = cleaned[index]
                if in_string:
                    if escape:
                        escape = False
                    elif char == "\\":
                        escape = True
                    elif char == '"':
                        in_string = False
                    continue

                if char == '"':
                    in_string = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(cleaned[start:index + 1])
                        except json.JSONDecodeError:
                            break
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
    provider = _provider()
    if provider == "ollama":
        return _call_ollama_json(
            system_prompt,
            user_content,
            model,
            _ollama_max_tokens(max_tokens),
            temperature,
            _ollama_timeout_seconds(timeout_seconds),
            max_attempts,
        )

    if provider == "google":
        return _call_google_json(system_prompt, user_content, model, max_tokens, temperature, timeout_seconds, max_attempts)

    if provider == "cloudflare":
        return _call_cloudflare_json(system_prompt, user_content, model, max_tokens, temperature, timeout_seconds, max_attempts)

    return _call_openrouter_json(system_prompt, user_content, model, max_tokens, temperature, timeout_seconds, max_attempts)
