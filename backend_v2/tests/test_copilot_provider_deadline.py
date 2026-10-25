"""A provider sending bytes forever cannot retain a durable run indefinitely."""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from types import SimpleNamespace

import httpx
import pytest
from backend_v2.app.copilot import agent_loop, agent_runs, provider
from backend_v2.app.copilot import tasks as copilot_tasks
from backend_v2.app.copilot.models import CopilotAgentRun, CopilotAgentTask
from backend_v2.app.core.problem import DomainError
from backend_v2.tests.test_copilot_agent_tasks import _project
from backend_v2.tests.test_copilot_agent_tasks import wired as wired  # noqa: F401


@pytest.fixture(autouse=True)
def offline_guard(monkeypatch):
    from backend_v2.app.copilot import call_guard
    monkeypatch.setattr(call_guard, "reserve_call", lambda *_: "offline-reservation")
    monkeypatch.setattr(call_guard, "record_usage", lambda *_: None)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(provider, "validate_llm_endpoint", lambda _: None)
    monkeypatch.setattr(provider, "credential_value", lambda _: "offline-only-token")
    monkeypatch.setattr(provider, "LLM_COMPLETION_DEADLINE_SECONDS", 0.06)
    return SimpleNamespace(endpoint="https://provider.invalid/v1", model="unchanged-model",
                           credential_ref="env:OFFLINE_ONLY", config={})


class KeepaliveBody(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.chunks = 0
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        while True:
            self.chunks += 1
            yield b" "
            await asyncio.sleep(0.005)

    async def aclose(self) -> None:
        self.closed = True


def _transport(monkeypatch, handler):
    original_client = httpx.AsyncClient
    clients = []

    def client(**kwargs):
        instance = original_client(transport=httpx.MockTransport(handler), **kwargs)
        clients.append(instance)
        return instance

    monkeypatch.setattr(provider.httpx, "AsyncClient", client)
    return clients


def test_keepalive_response_hits_total_deadline_and_closes_without_replay(configured, monkeypatch):
    stream, requests = KeepaliveBody(), []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, stream=stream)

    clients = _transport(monkeypatch, handler)
    start = time.monotonic()
    with pytest.raises(DomainError) as error:
        provider.completion_message(configured, [{"role": "user", "content": "offline"}])
    assert error.value.error_code == "llm_completion_deadline_exceeded"
    assert error.value.status_code == 504
    assert time.monotonic() - start < 1.0
    assert stream.chunks >= 2, "Reads kept making progress; this is not an inactivity timeout"
    assert stream.closed and all(client.is_closed for client in clients)
    assert len(requests) == 1, "Expiry ends this completion instead of starting a fresh deadline"


def test_server_error_returns_without_retry_or_backoff(configured, monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(503, json={"error": "offline transient failure"})

    clients = _transport(monkeypatch, handler)
    with pytest.raises(httpx.HTTPStatusError) as error:
        provider.completion_message(configured, [])
    assert error.value.response.status_code == 503
    assert len(requests) == 1
    assert all(client.is_closed for client in clients)


def test_200_headers_followed_by_broken_body_never_replays_paid_request(configured, monkeypatch):
    requests = []
    class BrokenBody(httpx.AsyncByteStream):
        closed = False
        async def __aiter__(self):
            yield b'{"choices":'
            raise httpx.RemoteProtocolError("Synthetic break after response headers")
        async def aclose(self):
            self.closed = True
    stream = BrokenBody()
    def handler(request):
        requests.append(request)
        return httpx.Response(200, stream=stream)
    clients = _transport(monkeypatch, handler)
    with pytest.raises(httpx.RemoteProtocolError):
        provider.completion_message(configured, [])
    assert len(requests) == 1
    assert stream.closed and all(client.is_closed for client in clients)


def test_response_before_deadline_retains_model_parameters_and_tool_protocol(configured, monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {
            "content": None, "tool_calls": [{"id": "call-1", "type": "function", "function": {
                "name": "list_proteins", "arguments": "{}"}}]}, "finish_reason": "tool_calls"}]})

    clients = _transport(monkeypatch, handler)
    result = provider.completion_message(configured, [])
    assert result["tool_calls"][0]["id"] == "call-1"
    assert b'"model":"unchanged-model"' in requests[0].content
    assert b"max_tokens" not in requests[0].content
    assert all(client.is_closed for client in clients)


def test_deadline_fails_child_durably_settles_parent_task_and_wakes_parent(wired, configured, monkeypatch):
    factory, sent = wired
    with factory() as session:
        project_id, user_id = _project(session)
        parent = agent_runs.create_run(session, project_id=project_id, user_id=user_id,
                                       goal="Review evidence", allowed_tools=[])
        child = agent_runs.create_run(session, project_id=project_id, user_id=user_id,
                                      parent_run_id=parent.id, goal="Read saved evidence", allowed_tools=[])
        task = agent_runs.suspend(session, parent, [("subagent", child.id, "delegated-call")])[0]
        parent_id, child_id, task_id = parent.id, child.id, task.id
        session.commit()
    stream = KeepaliveBody()
    _transport(monkeypatch, lambda request: httpx.Response(200, stream=stream))
    monkeypatch.setattr(agent_loop, "provider_for", lambda *_: configured)

    outcome = copilot_tasks.copilot_agent_step.run(str(child_id))
    assert outcome["status"] == "failed"
    with factory() as session:
        child = session.get(CopilotAgentRun, child_id)
        task = session.get(CopilotAgentTask, task_id)
        assert child.status == "failed" and "total deadline" in child.error
        assert child.turn_count == 0
        assert task.status == "failed" and "total deadline" in task.error
    assert ("bda_v2.copilot_agent_step", [str(parent_id)]) in sent
    assert stream.closed
