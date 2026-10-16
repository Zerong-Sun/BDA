"""Task and queued-tool boundaries retain a durable paid-call scope (no HTTP)."""
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from backend_v2.app.compute import tasks as compute_tasks
from backend_v2.app.compute.models import OutboxEvent
from backend_v2.app.copilot import agent_loop, agent_runs, call_guard
from backend_v2.app.copilot import tasks as copilot_tasks
from backend_v2.app.core import celery_app as worker
from backend_v2.app.platform.operations import enqueue_operation
from backend_v2.app.research import search_query
from backend_v2.tests.test_compute_tasks import task_database as _task_database
from backend_v2.tests.test_copilot_agent_tasks import _project
from backend_v2.tests.test_copilot_agent_tasks import wired as _wired
from backend_v2.tests.test_platform_operations import _actors
from backend_v2.tests.test_platform_operations import session as _ops_session

task_database = _task_database
wired = _wired
ops_session = _ops_session


@pytest.mark.parametrize("inherited", [False, True])
def test_enqueue_scope_is_server_owned(ops_session, inherited):
    project, user = _actors(ops_session)
    def enqueue():
        return enqueue_operation(
            ops_session, topic="literature.search", resource_type="literature_search",
            resource_id=uuid.uuid4(), project_id=project.id, user=user,
            payload={"_llm_call_scope": "forged-fresh-budget"},
        )
    if inherited:
        with call_guard.call_scope("trusted-root"):
            operation = enqueue()
    else:
        operation = enqueue()
    ops_session.flush()
    event = ops_session.get(OutboxEvent, operation.id)
    assert event.payload.get("_llm_call_scope") == ("trusted-root" if inherited else None)


def test_async_outbox_propagates_scope_and_worker_restores_it(task_database, monkeypatch):
    factory, ids = task_database
    with factory() as session:
        session.add(OutboxEvent(
            topic="research.generate", aggregate_id=uuid.uuid4(),
            payload={"project_id": str(ids["project"]), "_llm_call_scope": "copilot-agent:root"},
        ))
        session.commit()
    sent = []
    monkeypatch.setattr(compute_tasks.celery_app, "send_task", lambda name, **kwargs: sent.append(kwargs))
    assert compute_tasks.publish_outbox.run()["published"] == 1
    assert sent[0]["headers"] == {"bda_project_id": str(ids["project"]), "bda_llm_call_scope": "copilot-agent:root"}
    for _ in range(2):  # Broker redelivery has the same scope, not a new allowance.
        worker._bind_operation_call_scope(sender=SimpleNamespace(request=SimpleNamespace(headers=sent[0]["headers"])), task_id="delivery")
        try:
            with call_guard.call_scope("research-generation:new-id"):
                assert call_guard.current_scope_id() == "copilot-agent:root"
        finally:
            worker._reset_operation_call_scope(task_id="delivery")
        assert call_guard.current_scope_id() is None


def test_worker_scope_nested_cleanup_and_headerless_tasks_do_not_mint_scope():
    worker._bind_operation_call_scope(sender=SimpleNamespace(request=SimpleNamespace(headers={})), task_id="bare")
    assert call_guard.current_scope_id() is None
    for task, scope in [("outer", "root"), ("inner", "must-not-reset")]:
        worker._bind_operation_call_scope(sender=SimpleNamespace(request=SimpleNamespace(headers={"bda_llm_call_scope": scope})), task_id=task)
    assert call_guard.current_scope_id() == "root"
    worker._reset_operation_call_scope(task_id="inner")
    assert call_guard.current_scope_id() == "root"
    worker._reset_operation_call_scope(task_id="outer")
    assert call_guard.current_scope_id() is None


def test_translation_retry_is_stable_and_inherits_task_scope(monkeypatch):
    seen = []
    monkeypatch.setattr(search_query, "select_provider", lambda *a, **k: object())
    def complete(*args):
        seen.append(call_guard.current_scope_id())
        return '{"query":"synthetic protein topic"}'
    monkeypatch.setattr(search_query, "complete", complete)
    project = uuid.uuid4()
    for _ in range(2):
        search_query.search_topic(None, project, "合成蛋白质")
    assert seen[0] == seen[1] and seen[0].startswith(f"search-translation:{project}:")
    with call_guard.call_scope("parent-budget"):
        search_query.search_topic(None, project, "合成蛋白质")
    assert seen[-1] == "parent-budget"
    assert call_guard.current_scope_id() is None


def test_agent_steps_share_root_scope_and_count_old_assistant_turns(wired, monkeypatch):
    factory, _ = wired
    with factory() as session:
        project_id, user_id = _project(session)
        root = agent_runs.create_run(session, project_id=project_id, user_id=user_id, goal="root", allowed_tools=[])
        root.max_turns = 30  # A legacy run; admission still clamps to six.
        children = [agent_runs.create_run(session, project_id=project_id, user_id=user_id, goal="child", allowed_tools=[], parent_run_id=root.id) for _ in range(2)]
        for run, count in [(root, 3), (children[0], 2), (children[1], 2)]:
            for _ in range(count):
                agent_runs.append_turn(session, run, role="assistant", content="historical reply")
            agent_runs.append_turn(session, run, role="user", content="not a paid call")
        session.commit()
        ids = [root.id, *(child.id for child in children)]
    entries = []
    original_scope = call_guard.call_scope
    @contextmanager
    def record_scope(scope_id, **kwargs):
        entries.append((scope_id, kwargs))
        with original_scope(scope_id, **kwargs):
            yield
    monkeypatch.setattr(copilot_tasks, "call_scope", record_scope)
    monkeypatch.setattr(agent_loop, "provider_for", lambda *a: object())
    observed = []
    def drive(session, run, provider):
        observed.append(call_guard.current_scope_id())
        return run.status
    monkeypatch.setattr(agent_loop, "drive", drive)
    for run_id in [ids[1], ids[0], ids[2], ids[1]]:
        assert copilot_tasks.copilot_agent_step.run(str(run_id))["status"] == "running"
    assert observed == [f"copilot-agent:{ids[0]}"] * 4
    assert all(entry[1] == {"max_calls": 30, "initial_calls": 7} for entry in entries)
    assert call_guard.current_scope_id() is None


def test_research_generation_translation_uses_durable_id_and_inherits_parent(monkeypatch):
    from backend_v2.app.research import generation
    from backend_v2.app.research import tasks as research_tasks

    generation_id, project_id = uuid.uuid4(), uuid.uuid4()
    row = SimpleNamespace(status="ready", checksum=None, draft={})
    @contextmanager
    def session_scope():
        yield SimpleNamespace(get=lambda *args: row)
    monkeypatch.setattr(research_tasks, "session_scope", session_scope)
    monkeypatch.setattr(search_query, "select_provider", lambda *a, **k: object())
    seen = []
    def complete(*args):
        seen.append(call_guard.current_scope_id())
        return '{"query":"protein topic"}'
    monkeypatch.setattr(search_query, "complete", complete)
    monkeypatch.setattr(generation, "finalize_research_generation", lambda session, row: search_query.search_topic(session, project_id, "蛋白质"))
    for _ in range(2):
        research_tasks.research_generate.run(str(generation_id))
    with call_guard.call_scope("original-agent"):
        research_tasks.research_generate.run(str(generation_id))
    assert seen == [f"research-generation:{generation_id}"] * 2 + ["original-agent"]


def test_provider_tests_share_stable_fingerprint_scope(monkeypatch):
    from backend_v2.app.copilot import api, qualification

    provider = SimpleNamespace(id=uuid.uuid4(), version=1, endpoint="https://provider.invalid", model="fixture", credential_ref="env:FIXTURE", config={}, enabled=True)
    project_id = uuid.uuid4()
    row = SimpleNamespace(settings={}, version=1)
    session = SimpleNamespace(scalar=lambda *a: row, flush=lambda: None)
    monkeypatch.setattr(qualification, "select_provider", lambda *a, **k: provider)
    observed = []
    def completion(*args, **kwargs):
        observed.append(call_guard.current_scope_id())
        if kwargs.get("tools"):
            return {"tool_calls": [{"function": {"name": "bda_protocol_check", "arguments": '{"value":7}'}}]}
        return {"content": '{"objective":"check","success_criteria":"cited","missing":["control"],"source_id":"bda-check-source","value":7,"route_id":"route-ready"}'}
    monkeypatch.setattr(qualification, "completion_message", completion)
    for _ in range(2):
        assert qualification.assess(session, project_id)["checks"]["tools"]
    assert observed == [f"provider-qualification:{project_id}:{qualification.fingerprint(provider)}"] * 4
    monkeypatch.setattr(api, "require_project", lambda *a: None)
    monkeypatch.setattr(api, "select_provider", lambda *a, **k: provider)
    def complete(*args):
        observed.append(call_guard.current_scope_id())
        return "BDA provider connected"
    monkeypatch.setattr(api, "complete_with_provider", complete)
    for _ in range(2):
        assert api.test_config(project_id, session, SimpleNamespace()).connected
    assert observed[-2:] == [f"provider-test:{project_id}:{qualification.fingerprint(provider)}"] * 2
    assert call_guard.current_scope_id() is None
