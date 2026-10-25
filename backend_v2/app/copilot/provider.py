from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ..core.problem import DomainError
from ..registry.models import LLMProvider
from .endpoint_policy import validate_llm_endpoint

LLM_TIMEOUT = httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0)
LLM_MAX_ATTEMPTS = 1
# HTTPX read timeouts bound inactivity between chunks, not the whole response.
# One deadline includes connection and response body; a provider
# sending keepalive bytes must not hold a durable run's transaction indefinitely.
LLM_COMPLETION_DEADLINE_SECONDS = 180.0


def structured_retry_provider(provider: LLMProvider) -> LLMProvider | None:
    """Build JSON-only settings; the caller must reserve a separate model call.

    DeepSeek thinking tokens share the output budget. A format/factual pass may
    exhaust that budget before returning JSON. Preserve the configured ceiling
    and credentials; do not change saved settings or guess third-party support.
    This helper never sends or retries a request itself.
    """
    if (urlparse(provider.endpoint or "").hostname != "api.deepseek.com"
            or provider.model not in {"deepseek-flash", "deepseek-v4-flash", "deepseek-v4-pro"}):
        return None
    config = {key: value for key, value in (provider.config or {}).items()
              if key not in {"thinking", "reasoning", "reasoning_effort"}}
    config.update({"thinking": {"type": "disabled"}, "response_format": {"type": "json_object"}})
    return LLMProvider(id=provider.id, name=provider.name, model=provider.model,
                       provider_type=provider.provider_type, endpoint=provider.endpoint,
                       credential_ref=provider.credential_ref, config=config)


async def _completion_response(endpoint: str, token: str, body: dict[str, Any]) -> httpx.Response:
    try:
        async with asyncio.timeout(LLM_COMPLETION_DEADLINE_SECONDS):
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
                # A timeout/connection break/5xx can happen after generation
                # was accepted and charged. Never replay an ambiguous POST.
                # Even an apparently safe connection failure remains one
                # accounted attempt; any recovery needs a fresh reservation.
                response = await client.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=body,
                    timeout=LLM_TIMEOUT,
                )
                response.raise_for_status()
                return response
    except TimeoutError as exc:
        # Cancellation closes the in-flight response and client before this
        # reaches the caller. No detached request thread is used for timeouts.
        raise DomainError(
            "llm_completion_deadline_exceeded",
            f"Model completion exceeded the {LLM_COMPLETION_DEADLINE_SECONDS:g}-second total deadline; no response was accepted.",
            status_code=504,
        ) from exc


def credential_value(reference: str) -> str:
    if reference.startswith("env:"):
        value = os.getenv(reference.removeprefix("env:"))
    elif reference.startswith("file:"):
        path = Path(reference.removeprefix("file:"))
        value = path.read_text(encoding="utf-8").strip() if path.is_file() else None
    else:
        value = None
    if not value:
        raise DomainError("credential_unavailable", "Configured credential reference is unavailable", status_code=503)
    return value


def credential_available(reference: str) -> bool:
    try:
        credential_value(reference)
    except (DomainError, OSError):
        return False
    return True


def completion_message(
    provider: LLMProvider,
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not provider.endpoint:
        raise DomainError("llm_endpoint_missing", "LLM provider endpoint is not configured", status_code=503)
    reserved = sorted({"model", "messages", "stream"} & provider.config.keys())
    if reserved:
        raise DomainError(
            "llm_config_reserved_fields",
            "LLM provider config cannot set reserved request fields: " + ", ".join(reserved),
            status_code=422,
        )
    if "n" in provider.config and (type(provider.config["n"]) is not int or provider.config["n"] != 1):
        raise DomainError("llm_multiple_completions_not_allowed", "Each model call must request exactly one completion.", status_code=422)
    validate_llm_endpoint(provider.endpoint)
    token = credential_value(provider.credential_ref)
    endpoint = provider.endpoint.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"
    body: dict[str, Any] = {
        "model": provider.model,
        "messages": messages,
        **{key: value for key, value in provider.config.items() if key not in {"platform_default", "bda_pricing"}},
    }
    if provider.config.get("bda_pricing") and "max_tokens" not in body and "max_completion_tokens" not in body:
        body["max_tokens"] = 2048
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    # This API is synchronous: Celery workers and FastAPI's synchronous route
    # threadpool call it. Async callers must use a worker thread, just as for its
    # other synchronous domain/DB operations. The event loop lives only here.
    from . import call_guard
    receipt = call_guard.reserve_call(provider, body)
    response = asyncio.run(_completion_response(endpoint, token, body))
    payload = response.json()
    # Account for returned usage even when the generated answer is rejected
    # below. Failed HTTP/JSON responses retain their conservative reservation.
    call_guard.record_usage(receipt, payload.get("usage") if isinstance(payload, dict) else None)
    try:
        choice = payload["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("llm_response_schema_invalid") from exc
    if not isinstance(message, dict):
        raise ValueError("llm_response_schema_invalid")
    if choice.get("finish_reason") == "length":
        raise DomainError(
            "llm_output_truncated",
            "The model reached its output limit. Shorten the request or increase the provider output token limit and retry.",
            status_code=502,
        )
    if choice.get("finish_reason") == "content_filter":
        raise DomainError("llm_output_filtered", "The provider filtered this response; partial output was not accepted.", status_code=502)
    calls = message.get("tool_calls")
    if calls is not None:
        if not isinstance(calls, list):
            raise ValueError("llm_response_schema_invalid")
        ids: set[str] = set()
        for call in calls:
            if not isinstance(call, dict) or not isinstance(call.get("id"), str) or not call["id"] or call["id"] in ids:
                raise ValueError("llm_response_schema_invalid")
            function = call.get("function")
            if (call.get("type") != "function" or not isinstance(function, dict)
                    or not isinstance(function.get("name"), str) or not function["name"]
                    or not isinstance(function.get("arguments"), str)):
                raise ValueError("llm_response_schema_invalid")
            ids.add(call["id"])
    return message


def complete(provider: LLMProvider, messages: list[dict[str, Any]]) -> str:
    content = completion_message(provider, messages).get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("llm_response_empty")
    return content.strip()
