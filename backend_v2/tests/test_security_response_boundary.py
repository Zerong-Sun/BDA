"""Sensitive response bodies and untrusted tracing must stay within their boundary."""
from __future__ import annotations

import json
import re

import pytest
from backend_v2.app.core.problem import validation_error_handler
from backend_v2.app.core.security import SecurityHeadersMiddleware
from backend_v2.app.core.trace import TraceMiddleware
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, model_validator


class CredentialInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: str

    @model_validator(mode="after")
    def reject(self):
        raise ValueError("Invalid provider configuration")


def protected_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(TraceMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    @app.post("/api/v2/provider-credentials")
    def credentials(body: CredentialInput):
        return body

    @app.get("/api/v2/events")
    def events():
        return StreamingResponse(iter([b"data: private\n\n"]), media_type="text/event-stream")

    @app.post("/mcp")
    def mcp():
        return {"result": "private"}

    return app


def test_non_auth_validation_does_not_echo_credentials_or_private_payload() -> None:
    client = TestClient(protected_app())
    secret = "synthetic-sensitive-provider-key"
    response = client.post("/api/v2/provider-credentials", json={"api_key": secret})
    assert response.status_code == 422
    assert secret not in response.text
    errors = response.json()["errors"]
    assert errors[0]["type"] == "value_error"
    assert "input" not in errors[0] and "ctx" not in errors[0]
    assert response.headers["cache-control"] == "no-store"
    # An extra-field error used to reflect a whole nested private object.
    response = client.post("/api/v2/provider-credentials", json={"api_key": secret, "extra": {"sequence": secret}})
    assert secret not in response.text
    json.loads(response.text)


@pytest.mark.parametrize("headers", [
    {"X-Trace-Id": "sensitive-data-not-an-id"},
    {"X-Trace-Id": "0" * 32},
    {"X-Trace-Id": "a" * 10000},
    {"traceparent": "00-" + "0" * 32 + "-" + "0" * 16 + "-01"},
])
def test_untrusted_trace_identifiers_are_replaced(headers) -> None:
    response = TestClient(protected_app()).get("/api/v2/missing", headers=headers)
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-trace-id"])
    assert response.headers["x-trace-id"] != "0" * 32
    assert re.fullmatch(r"00-[0-9a-f]{32}-[0-9a-f]{16}-01", response.headers["traceparent"])


def test_security_headers_cover_errors_mcp_and_streams_without_buffering() -> None:
    client = TestClient(protected_app())
    responses = [client.get("/api/v2/missing"), client.post("/mcp"), client.get("/api/v2/events")]
    for response in responses:
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
    assert responses[-1].content == b"data: private\n\n"
