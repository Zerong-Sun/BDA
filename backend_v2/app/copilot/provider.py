from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import httpx

from ..core.problem import DomainError
from ..registry.models import LLMProvider

LLM_TIMEOUT = httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0)
LLM_MAX_ATTEMPTS = 3


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
    token = credential_value(provider.credential_ref)
    endpoint = provider.endpoint.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"
    body: dict[str, Any] = {"model": provider.model, "messages": messages, **provider.config}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    response: httpx.Response | None = None
    last_error: httpx.HTTPError | None = None
    for attempt in range(LLM_MAX_ATTEMPTS):
        try:
            response = httpx.post(
                endpoint,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body,
                timeout=LLM_TIMEOUT,
            )
            response.raise_for_status()
            break
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status = exc.response.status_code
            if status != 429 and status < 500:
                raise
        except httpx.RequestError as exc:
            last_error = exc
        if attempt < LLM_MAX_ATTEMPTS - 1:
            time.sleep(0.25 * (2**attempt))
    if response is None or last_error is not None and response.is_error:
        if last_error is None:
            raise RuntimeError("llm_request_failed")
        raise last_error
    payload = response.json()
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("llm_response_schema_invalid") from exc
    if not isinstance(message, dict):
        raise ValueError("llm_response_schema_invalid")
    return message


def complete(provider: LLMProvider, messages: list[dict[str, Any]]) -> str:
    content = completion_message(provider, messages).get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("llm_response_empty")
    return content.strip()
