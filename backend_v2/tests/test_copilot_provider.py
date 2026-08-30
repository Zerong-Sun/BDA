from __future__ import annotations

import uuid
from types import SimpleNamespace

import httpx
import pytest
from backend_v2.app.copilot import provider, service
from backend_v2.app.core.problem import DomainError


def test_credential_references(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BDA_TEST_LLM_TOKEN", "secret-token")
    assert provider.credential_value("env:BDA_TEST_LLM_TOKEN") == "secret-token"
    token_file = tmp_path / "token"
    token_file.write_text(" file-token \n", encoding="utf-8")
    assert provider.credential_value(f"file:{token_file}") == "file-token"
    assert provider.credential_available(f"file:{token_file}") is True
    assert provider.credential_available("env:BDA_TEST_MISSING") is False
    with pytest.raises(DomainError, match="unavailable"):
        provider.credential_value("env:BDA_TEST_MISSING")
    with pytest.raises(DomainError, match="unavailable"):
        provider.credential_value("secret:unsupported")


def test_local_secret_store_reports_unwritable_directory(monkeypatch, tmp_path) -> None:
    def reject_chmod(*args, **kwargs) -> None:
        raise PermissionError("read-only mount")

    monkeypatch.setattr(service.os, "chmod", reject_chmod)
    with pytest.raises(DomainError, match="not writable") as error:
        service._store_local_secret(tmp_path / "secrets", uuid.uuid4(), "secret")
    assert error.value.status_code == 503


def test_openai_compatible_completion(monkeypatch) -> None:
    captured = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"choices": [{"message": {"content": "  completed answer  "}}]}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setenv("BDA_TEST_LLM_TOKEN", "secret")
    monkeypatch.setattr(provider.httpx, "post", post)
    configured = SimpleNamespace(
        endpoint="https://llm.example/v1",
        credential_ref="env:BDA_TEST_LLM_TOKEN",
        model="research-model",
        config={"temperature": 0.1},
    )
    assert provider.complete(configured, [{"role": "user", "content": "question"}]) == "completed answer"
    assert captured["url"] == "https://llm.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["json"]["model"] == "research-model"
    assert captured["timeout"].connect == 10.0
    assert captured["timeout"].read == 180.0


def test_completion_rejects_missing_endpoint_and_invalid_payload(monkeypatch) -> None:
    with pytest.raises(DomainError, match="endpoint"):
        provider.complete(SimpleNamespace(endpoint=None), [])

    monkeypatch.setenv("BDA_TEST_LLM_TOKEN", "secret")

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"choices": []}

    monkeypatch.setattr(provider.httpx, "post", lambda *args, **kwargs: Response())
    configured = SimpleNamespace(
        endpoint="https://llm.example/chat/completions",
        credential_ref="env:BDA_TEST_LLM_TOKEN",
        model="model",
        config={},
    )
    with pytest.raises(ValueError, match="schema_invalid"):
        provider.complete(configured, [])

    Response.json = lambda self: {"choices": [{"message": {"content": " "}}]}
    with pytest.raises(ValueError, match="response_empty"):
        provider.complete(configured, [])


def test_completion_retries_transient_network_error(monkeypatch) -> None:
    attempts = 0

    def post(url, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("temporary DNS failure")
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"message": {"content": "connected"}}]},
        )

    monkeypatch.setenv("BDA_TEST_LLM_TOKEN", "secret")
    monkeypatch.setattr(provider.httpx, "post", post)
    monkeypatch.setattr(provider.time, "sleep", lambda _: None)
    configured = SimpleNamespace(
        endpoint="https://llm.example/v1",
        credential_ref="env:BDA_TEST_LLM_TOKEN",
        model="research-model",
        config={},
    )
    assert provider.complete(configured, [{"role": "user", "content": "question"}]) == "connected"
    assert attempts == 2
