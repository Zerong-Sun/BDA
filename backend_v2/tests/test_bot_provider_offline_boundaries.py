"""Scripted transport failures; these tests do not call any live model."""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from backend_v2.app.copilot import provider


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(provider, "credential_value", lambda _: "synthetic-offline-token")
    return SimpleNamespace(endpoint="https://provider.invalid/v1", model="selected-model",
                           credential_ref="env:OFFLINE_ONLY", config={"max_tokens": 4096})


def response(url, status):
    return httpx.Response(status, request=httpx.Request("POST", url),
                          json={"choices": [{"message": {"content": "scripted answer"}}]})


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transient_status_recovers_without_switching_model(configured, monkeypatch, status):
    requests, sleeps = [], []

    def post(url, **kwargs):
        requests.append((url, kwargs["json"]["model"]))
        return response(url, status if len(requests) == 1 else 200)

    monkeypatch.setattr(provider.httpx, "post", post)
    monkeypatch.setattr(provider.time, "sleep", sleeps.append)
    assert provider.complete(configured, [{"role": "user", "content": "offline"}]) == "scripted answer"
    assert requests == [("https://provider.invalid/v1/chat/completions", "selected-model")] * 2
    assert sleeps == [0.25]


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transient_status_exhaustion_raises_after_three_attempts(configured, monkeypatch, status):
    requests, sleeps = [], []

    def post(url, **kwargs):
        requests.append(kwargs["json"]["model"])
        return response(url, status)

    monkeypatch.setattr(provider.httpx, "post", post)
    monkeypatch.setattr(provider.time, "sleep", sleeps.append)
    with pytest.raises(httpx.HTTPStatusError) as error:
        provider.complete(configured, [])
    assert error.value.response.status_code == status
    assert requests == ["selected-model"] * 3
    assert sleeps == [0.25, 0.5]


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_nonretryable_client_error_is_not_replayed(configured, monkeypatch, status):
    requests, sleeps = [], []

    def post(url, **kwargs):
        requests.append(url)
        return response(url, status)

    monkeypatch.setattr(provider.httpx, "post", post)
    monkeypatch.setattr(provider.time, "sleep", sleeps.append)
    with pytest.raises(httpx.HTTPStatusError) as error:
        provider.complete(configured, [])
    assert error.value.response.status_code == status
    assert len(requests) == 1 and sleeps == []


@pytest.mark.parametrize("error_type", [httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout])
def test_timeout_exhaustion_is_bounded_and_surfaces_the_error(configured, monkeypatch, error_type):
    attempts, sleeps = [], []

    def post(url, **kwargs):
        attempts.append(kwargs["json"]["model"])
        raise error_type("scripted offline timeout", request=httpx.Request("POST", url))

    monkeypatch.setattr(provider.httpx, "post", post)
    monkeypatch.setattr(provider.time, "sleep", sleeps.append)
    with pytest.raises(error_type, match="scripted offline timeout"):
        provider.complete(configured, [])
    assert attempts == ["selected-model"] * 3
    assert sleeps == [0.25, 0.5]


def test_read_timeout_can_recover_on_the_last_attempt(configured, monkeypatch):
    attempts = []

    def post(url, **kwargs):
        attempts.append(kwargs["json"]["model"])
        if len(attempts) < 3:
            raise httpx.ReadTimeout("scripted timeout", request=httpx.Request("POST", url))
        return response(url, 200)

    monkeypatch.setattr(provider.httpx, "post", post)
    monkeypatch.setattr(provider.time, "sleep", lambda _: None)
    assert provider.complete(configured, []) == "scripted answer"
    assert attempts == ["selected-model"] * 3
