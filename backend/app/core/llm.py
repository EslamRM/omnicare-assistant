"""
Thin wrapper around the Groq client.

Kept intentionally small: one function to get a plain text completion,
one to get JSON-mode structured output. Callers never touch the SDK
directly, which makes it trivial to swap providers (e.g. to Ollama)
without touching agent logic.
"""
import json
import logging

from groq import Groq

from app.core.config import get_settings

logger = logging.getLogger("omnicare.llm")


class LLMUnavailableError(Exception):
    """Raised when the LLM call fails for any reason (timeout, auth,
    rate limit, network). Callers must handle this gracefully — Section 20
    requires infrastructure errors to degrade safely, not crash the request."""


def _client() -> Groq:
    settings = get_settings()
    return Groq(api_key=settings.groq_api_key, timeout=settings.llm_timeout_seconds)


def complete(system_prompt: str, user_prompt: str) -> str:
    """Plain text completion. Used for RAG answer synthesis."""
    settings = get_settings()
    try:
        response = _client().chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=300,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.error("LLM completion failed: %s", exc)
        raise LLMUnavailableError from exc


def complete_json(system_prompt: str, user_prompt: str) -> dict:
    """JSON-mode completion. Used for structured field extraction
    (e.g. claim submission), so the caller gets a dict to validate
    against a Pydantic model rather than free text to parse with regex."""
    settings = get_settings()
    try:
        response = _client().chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception as exc:
        logger.error("LLM JSON completion failed: %s", exc)
        raise LLMUnavailableError from exc
