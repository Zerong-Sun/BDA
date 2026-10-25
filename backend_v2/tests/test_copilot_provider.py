from __future__ import annotations

import uuid
from types import SimpleNamespace

import httpx
import pytest
from backend_v2.app.copilot import provider, service
from backend_v2.app.core.problem import DomainError
from backend_v2.tests._provider_transport import mock_post


@pytest.fixture(autouse=True)
def offline_guard(monkeypatch):
    from backend_v2.app.copilot import call_guard
    monkeypatch.setattr(call_guard, "reserve_call", lambda *_: "offline-reservation")
    monkeypatch.setattr(call_guard, "record_usage", lambda *_: None)


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
    mock_post(monkeypatch, post)
    configured = SimpleNamespace(
        endpoint="https://llm.example/v1",
        credential_ref="env:BDA_TEST_LLM_TOKEN",
        model="research-model",
        config={"temperature": 0.1, "thinking": {"type": "disabled"}, "max_tokens": 4096, "platform_default": True},
    )
    assert provider.complete(configured, [{"role": "user", "content": "question"}]) == "completed answer"
    assert captured["url"] == "https://llm.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["json"]["model"] == "research-model"
    assert captured["json"]["messages"] == [{"role": "user", "content": "question"}]
    assert captured["json"]["thinking"] == {"type": "disabled"}
    assert captured["json"]["max_tokens"] == 4096
    assert "platform_default" not in captured["json"]
    assert "stream" not in captured["json"]
    assert captured["timeout"].connect == 10.0
    assert captured["timeout"].read == 180.0


@pytest.mark.parametrize("message", [{"content": "partial result"}, {"content": None, "tool_calls": []}])
def test_truncated_output_is_not_accepted_as_a_complete_answer(monkeypatch, message) -> None:
    monkeypatch.setenv("BDA_TEST_LLM_TOKEN", "secret")
    mock_post(monkeypatch, lambda url, **kwargs: httpx.Response(
        200, request=httpx.Request("POST", url),
        json={"choices": [{"message": message, "finish_reason": "length"}]},
    ))
    configured = SimpleNamespace(endpoint="https://llm.example/v1", credential_ref="env:BDA_TEST_LLM_TOKEN", model="model", config={})
    with pytest.raises(DomainError) as error:
        provider.complete(configured, [{"role": "user", "content": "question"}])
    assert error.value.error_code == "llm_output_truncated"


def test_filtered_output_is_not_accepted_as_a_complete_answer(monkeypatch) -> None:
    monkeypatch.setenv("BDA_TEST_LLM_TOKEN", "secret")
    mock_post(monkeypatch, lambda url, **kwargs: httpx.Response(
        200, request=httpx.Request("POST", url),
        json={"choices": [{"message": {"content": "partial"}, "finish_reason": "content_filter"}]},
    ))
    configured = SimpleNamespace(endpoint="https://llm.example/v1", credential_ref="env:BDA_TEST_LLM_TOKEN", model="model", config={})
    with pytest.raises(DomainError) as error:
        provider.complete(configured, [{"role": "user", "content": "question"}])
    assert error.value.error_code == "llm_output_filtered"


@pytest.mark.parametrize("calls", ["not-an-array", [None], [{"id": "a", "function": None}],
                                   [{"id": "a", "type": "function", "function": {"name": "tool", "arguments": {}}}]])
def test_malformed_tool_calls_are_rejected_at_provider_boundary(monkeypatch, calls):
    monkeypatch.setenv("BDA_TEST_LLM_TOKEN", "secret")
    mock_post(monkeypatch, lambda url, **kwargs: httpx.Response(
        200, request=httpx.Request("POST", url),
        json={"choices": [{"message": {"content": None, "tool_calls": calls}, "finish_reason": "tool_calls"}]},
    ))
    configured = SimpleNamespace(endpoint="https://llm.example/v1", credential_ref="env:BDA_TEST_LLM_TOKEN", model="model", config={})
    with pytest.raises(ValueError, match="llm_response_schema_invalid"):
        provider.completion_message(configured, [])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model", "different-model"),
        ("messages", [{"role": "user", "content": "overridden input"}]),
        ("stream", True),
        ("stream", False),
    ],
)
def test_completion_rejects_reserved_config_before_credentials_or_request(monkeypatch, field, value) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid provider config must fail before reading credentials or sending a request")

    monkeypatch.setattr(provider, "credential_value", forbidden)
    mock_post(monkeypatch, forbidden)
    configured = SimpleNamespace(
        endpoint="https://llm.example/v1",
        credential_ref="env:BDA_TEST_LLM_TOKEN",
        model="selected-model",
        config={field: value},
    )
    with pytest.raises(DomainError) as error:
        provider.complete(configured, [{"role": "user", "content": "original input"}])
    assert error.value.error_code == "llm_config_reserved_fields"
    assert error.value.status_code == 422
    assert error.value.detail == "LLM provider config cannot set reserved request fields: " + field


def test_completion_rejects_missing_endpoint_and_invalid_payload(monkeypatch) -> None:
    with pytest.raises(DomainError, match="endpoint"):
        provider.complete(SimpleNamespace(endpoint=None), [])

    monkeypatch.setenv("BDA_TEST_LLM_TOKEN", "secret")

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"choices": []}

    mock_post(monkeypatch, lambda *args, **kwargs: Response())
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


def test_completion_does_not_replay_even_connection_errors(monkeypatch) -> None:
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
    mock_post(monkeypatch, post)
    configured = SimpleNamespace(
        endpoint="https://llm.example/v1",
        credential_ref="env:BDA_TEST_LLM_TOKEN",
        model="research-model",
        config={},
    )
    with pytest.raises(httpx.ConnectError, match="temporary DNS failure"):
        provider.complete(configured, [{"role": "user", "content": "question"}])
    assert attempts == 1


@pytest.mark.parametrize("count", [0, 2, 5, True, "2"])
def test_multiple_completions_fail_before_reservation_or_network(monkeypatch, count):
    from backend_v2.app.copilot import call_guard
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid multiplicity must fail before any paid attempt")
    monkeypatch.setattr(provider, "credential_value", forbidden)
    monkeypatch.setattr(call_guard, "reserve_call", forbidden)
    mock_post(monkeypatch, forbidden)
    configured = SimpleNamespace(endpoint="https://llm.invalid/v1", config={"n": count})
    with pytest.raises(DomainError) as caught:
        provider.completion_message(configured, [])
    assert caught.value.error_code == "llm_multiple_completions_not_allowed"


@pytest.mark.parametrize("finish_reason, malformed", [("stop", False), ("length", False),
                                                       ("content_filter", False), ("stop", True)])
def test_usage_is_recorded_before_rejected_output_validation(monkeypatch, finish_reason, malformed):
    from backend_v2.app.copilot import call_guard
    events = []
    usage = {"prompt_tokens": 101, "completion_tokens": 33, "total_tokens": 134}
    configured = SimpleNamespace(endpoint="https://llm.invalid/v1", credential_ref="env:OFFLINE",
                                  model="unchanged-model", config={"n": 1, "max_tokens": 1024})
    monkeypatch.setattr(provider, "credential_value", lambda _: "offline-token")
    def reserve(selected, body):
        assert selected is configured and body["model"] == "unchanged-model"
        events.append("reserved")
        return "receipt-1"
    def post(url, **kwargs):
        events.append("post")
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "usage": usage, "choices": [] if malformed else [{"finish_reason": finish_reason, "message": {"content": "answer"}}]})
    def record(receipt, received):
        assert receipt == "receipt-1" and received == usage
        events.append("usage")
    monkeypatch.setattr(call_guard, "reserve_call", reserve)
    monkeypatch.setattr(call_guard, "record_usage", record)
    mock_post(monkeypatch, post)
    if malformed:
        with pytest.raises(ValueError, match="llm_response_schema_invalid"):
            provider.completion_message(configured, [])
    elif finish_reason != "stop":
        with pytest.raises(DomainError):
            provider.completion_message(configured, [])
    else:
        assert provider.completion_message(configured, []) == {"content": "answer"}
    assert events == ["reserved", "post", "usage"]


def test_guard_rejection_prevents_http_request(monkeypatch):
    from backend_v2.app.copilot import call_guard
    monkeypatch.setattr(provider, "credential_value", lambda _: "offline-token")
    def reject(*args):
        raise DomainError("call_limit", "No remaining allowance", status_code=409)
    monkeypatch.setattr(call_guard, "reserve_call", reject)
    mock_post(monkeypatch, lambda *args, **kwargs: pytest.fail("Guard rejected the attempt"))
    configured = SimpleNamespace(endpoint="https://llm.invalid/v1", credential_ref="env:OFFLINE", model="m", config={})
    with pytest.raises(DomainError, match="No remaining allowance"):
        provider.completion_message(configured, [])


@pytest.mark.parametrize("failure", ["http", "json"])
def test_transport_or_json_failure_keeps_reservation_without_usage_refund(monkeypatch, failure):
    from backend_v2.app.copilot import call_guard
    events = []
    monkeypatch.setattr(provider, "credential_value", lambda _: "offline-token")
    monkeypatch.setattr(call_guard, "reserve_call", lambda *_: events.append("reserved"))
    monkeypatch.setattr(call_guard, "record_usage", lambda *_: pytest.fail("No usage was received"))
    def post(url, **kwargs):
        events.append("post")
        return httpx.Response(503 if failure == "http" else 200,
                              request=httpx.Request("POST", url), content=b"not-json")
    mock_post(monkeypatch, post)
    configured = SimpleNamespace(endpoint="https://llm.invalid/v1", credential_ref="env:OFFLINE", model="m", config={})
    with pytest.raises(httpx.HTTPStatusError if failure == "http" else ValueError):
        provider.completion_message(configured, [])
    assert events == ["reserved", "post"]


def test_missing_usage_stays_unknown_for_the_guard(monkeypatch):
    from backend_v2.app.copilot import call_guard
    recorded = []
    monkeypatch.setattr(provider, "credential_value", lambda _: "offline-token")
    monkeypatch.setattr(call_guard, "record_usage", lambda receipt, usage: recorded.append((receipt, usage)))
    mock_post(monkeypatch, lambda url, **kwargs: httpx.Response(
        200, request=httpx.Request("POST", url), json={"choices": [{"message": {"content": "answer"}}]}))
    configured = SimpleNamespace(endpoint="https://llm.invalid/v1", credential_ref="env:OFFLINE", model="m", config={})
    assert provider.complete(configured, []) == "answer"
    assert recorded == [("offline-reservation", None)]


def test_structured_fallback_needs_a_new_guard_reservation(monkeypatch):
    from backend_v2.app.copilot import call_guard
    from backend_v2.app.registry.models import LLMProvider
    events = []
    configured = LLMProvider(id=uuid.uuid4(), name="offline", provider_type="openai_compatible",
                             endpoint="https://api.deepseek.com/v1", model="deepseek-flash",
                             credential_ref="env:OFFLINE", config={"max_tokens": 1024})
    monkeypatch.setattr(provider, "credential_value", lambda _: "offline-token")
    def reserve(*args):
        events.append("reserve")
        if events.count("reserve") > 1:
            raise DomainError("call_limit", "No remaining allowance", status_code=409)
        return "attempt-1"
    def post(url, **kwargs):
        events.append("post")
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]})
    monkeypatch.setattr(call_guard, "reserve_call", reserve)
    mock_post(monkeypatch, post)
    with pytest.raises(DomainError, match="output limit"):
        provider.completion_message(configured, [])
    fallback = provider.structured_retry_provider(configured)
    assert fallback is not None and fallback.config["max_tokens"] == 1024
    with pytest.raises(DomainError, match="No remaining allowance"):
        provider.completion_message(fallback, [])
    assert events == ["reserve", "post", "reserve"]
