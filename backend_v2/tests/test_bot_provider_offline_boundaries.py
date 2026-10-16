"""Scripted transport failures; these tests do not call any live model."""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from backend_v2.app.copilot import provider
from backend_v2.tests._provider_transport import mock_post, mock_sleep


@pytest.fixture(autouse=True)
def offline_guard(monkeypatch):
    from backend_v2.app.copilot import call_guard
    monkeypatch.setattr(call_guard, "reserve_call", lambda *_: "offline-reservation")
    monkeypatch.setattr(call_guard, "record_usage", lambda *_: None)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(provider, "credential_value", lambda _: "synthetic-offline-token")
    return SimpleNamespace(endpoint="https://provider.invalid/v1", model="selected-model",
                           credential_ref="env:OFFLINE_ONLY", config={"max_tokens": 4096})


def response(url, status):
    return httpx.Response(status, request=httpx.Request("POST", url),
                          json={"choices": [{"message": {"content": "scripted answer"}}]})


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transient_status_is_not_replayed_even_if_next_request_would_succeed(configured, monkeypatch, status):
    requests, sleeps = [], []

    def post(url, **kwargs):
        requests.append((url, kwargs["json"]["model"]))
        return response(url, status if len(requests) == 1 else 200)

    mock_post(monkeypatch, post)
    mock_sleep(monkeypatch, sleeps.append)
    with pytest.raises(httpx.HTTPStatusError):
        provider.complete(configured, [{"role": "user", "content": "offline"}])
    assert requests == [("https://provider.invalid/v1/chat/completions", "selected-model")]
    assert sleeps == []


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transient_status_raises_after_one_accounted_attempt(configured, monkeypatch, status):
    requests, sleeps = [], []

    def post(url, **kwargs):
        requests.append(kwargs["json"]["model"])
        return response(url, status)

    mock_post(monkeypatch, post)
    mock_sleep(monkeypatch, sleeps.append)
    with pytest.raises(httpx.HTTPStatusError) as error:
        provider.complete(configured, [])
    assert error.value.response.status_code == status
    assert requests == ["selected-model"]
    assert sleeps == []


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_nonretryable_client_error_is_not_replayed(configured, monkeypatch, status):
    requests, sleeps = [], []

    def post(url, **kwargs):
        requests.append(url)
        return response(url, status)

    mock_post(monkeypatch, post)
    mock_sleep(monkeypatch, sleeps.append)
    with pytest.raises(httpx.HTTPStatusError) as error:
        provider.complete(configured, [])
    assert error.value.response.status_code == status
    assert len(requests) == 1 and sleeps == []


@pytest.mark.parametrize("error_type", [httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout,
                                        httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError])
def test_network_errors_surface_without_replaying_ambiguous_requests(configured, monkeypatch, error_type):
    attempts, sleeps = [], []

    def post(url, **kwargs):
        attempts.append(kwargs["json"]["model"])
        raise error_type("scripted offline timeout", request=httpx.Request("POST", url))

    mock_post(monkeypatch, post)
    mock_sleep(monkeypatch, sleeps.append)
    with pytest.raises(error_type, match="scripted offline timeout"):
        provider.complete(configured, [])
    assert attempts == ["selected-model"]
    assert sleeps == []


def test_read_timeout_does_not_replay_until_a_later_attempt_succeeds(configured, monkeypatch):
    attempts = []

    def post(url, **kwargs):
        attempts.append(kwargs["json"]["model"])
        if len(attempts) < 3:
            raise httpx.ReadTimeout("scripted timeout", request=httpx.Request("POST", url))
        return response(url, 200)

    mock_post(monkeypatch, post)
    mock_sleep(monkeypatch, lambda _: None)
    with pytest.raises(httpx.ReadTimeout):
        provider.complete(configured, [])
    assert attempts == ["selected-model"]
