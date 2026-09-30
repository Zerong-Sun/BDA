"""The final factual pass is independent of a bot's optional guided recipe."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot import agent_loop, agent_runs
from backend_v2.app.copilot.agent_review import review_messages
from backend_v2.app.copilot.task_contracts import build_contract
from backend_v2.tests.test_copilot_agent_loop import _call, _project, _provider, _run, _script
from backend_v2.tests.test_copilot_agent_loop import session as session_fixture
from sqlalchemy.orm import Session


@pytest.fixture(name="session")
def db_session():
    yield from session_fixture.__wrapped__()


def _delivery(status="partial", **values):
    return json.dumps({"status": status, "summary": "Observed three records in this query.",
                       "sections": {"observations": "Only this query's scope was inspected."},
                       "evidence_call_ids": ["read-1"], "missing": ["independent validation"],
                       "next_action": "Review the available records.", **values})


def _receipt(session, run, result=None):
    agent_runs.append_turn(session, run, role="assistant", tool_calls=[
        _call("read-1", "list_project_candidates", {"limit": 3, "query": "subset"})])
    agent_runs.append_turn(session, run, role="tool", content=json.dumps(
        result if result is not None else {"items": [{"value": "1 nM"}], "truncated": True}),
        tool_calls=[{"name": "list_project_candidates", "tool_call_id": "read-1"}])


@pytest.mark.parametrize("bot", ["researcher", "planner", "runner", "analyst", "conductor", "auditor"])
def test_direct_bot_delivery_receives_one_bounded_review_without_service_kind(session: Session, monkeypatch, bot):
    project, user = _project(session)
    run = _run(session, project, user, bot=bot, task_contract=build_contract("custom", []))
    _receipt(session, run)
    corrected = _delivery(summary="The inspected subset has three records; the total remains unknown.")
    seen = _script(monkeypatch, [{"content": _delivery()}, {"content": corrected}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 2
    packet = json.loads(seen[1][1]["content"])
    assert packet["goal"] == run.goal
    assert packet["bot"]["id"] == bot and packet["bot"]["charter"]
    assert packet["tool_records"][0]["arguments"] == {"limit": 3, "query": "subset"}
    assert packet["tool_records"][0]["result"]["items"][0]["value"] == "1 nM"
    assert run.status == "succeeded"
    assert run.outcome["scientific_review"] == "automated_review_completed"
    assert run.outcome["summary"] == json.loads(corrected)["summary"]
    assert agent_runs.transcript(session, run)[-1].content == corrected


@pytest.mark.parametrize("status", ["blocked", "needs_input"])
def test_blocked_evidence_summary_is_reviewed_and_retains_its_task_state(session: Session, monkeypatch, status):
    project, user = _project(session)
    run = _run(session, project, user, bot="conductor", task_contract=build_contract("custom", []))
    _receipt(session, run, {"error": "child_budget_exhausted"})
    draft = _delivery(status, evidence_call_ids=[], summary="The delegated step is blocked.")
    seen = _script(monkeypatch, [{"content": draft}, {"content": draft}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 2
    assert json.loads(seen[1][1]["content"])["tool_records"][0]["successful"] is False
    assert run.outcome["status"] == status
    assert run.outcome["scientific_review"] == "automated_review_completed"


@pytest.mark.parametrize("status", ["blocked", "needs_input"])
def test_final_budget_slot_preserves_honest_stop_without_an_extra_call_or_charge(session: Session, monkeypatch, status):
    project, user = _project(session)
    run = _run(session, project, user, bot="conductor", max_turns=3,
               task_contract=build_contract("custom", []))
    _receipt(session, run)
    draft = _delivery(status)
    seen = _script(monkeypatch, [{"content": draft}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 1 and run.turn_count == 3 and run.cost_usd_cents == 0
    assert run.status == "succeeded"
    assert run.outcome["status"] == status
    assert run.outcome["summary"] == json.loads(draft)["summary"]
    assert run.outcome["scientific_review"] == "unavailable"
    assert "scientific_review_unavailable" in run.outcome["missing"]
    assert agent_runs.transcript(session, run)[-1].content == draft


def test_no_tool_refusal_does_not_add_a_review_call(session: Session, monkeypatch):
    project, user = _project(session)
    run = _run(session, project, user, bot="runner", task_contract=build_contract("custom", []))
    seen = _script(monkeypatch, [{"content": _delivery("blocked", evidence_call_ids=[])}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 1 and run.outcome["status"] == "blocked"
    assert "scientific_review" not in run.outcome


def test_review_matches_scope_by_exact_call_id_and_tool_without_inventing_missing_arguments():
    run = SimpleNamespace(goal="Audit only this subset", task_contract={}, bot="auditor", outcome={})
    turns = [
        SimpleNamespace(role="assistant", tool_calls=[_call("reused", "wrong_tool", {"limit": 10})]),
        SimpleNamespace(role="tool", content='{"count": 3}', tool_calls=[
            {"tool_call_id": "reused", "name": "list_project_candidates"}]),
    ]
    packet = json.loads(review_messages(run, turns)[1]["content"])
    assert packet["tool_records"][0]["arguments"] is None
    assert packet["tool_records"][0]["result"] == {"count": 3}


def test_completed_custom_goal_is_factually_reviewed_but_still_requires_human_review(session: Session, monkeypatch):
    from backend_v2.app.copilot.task_contracts import evaluate_delivery

    project, user = _project(session)
    run = _run(session, project, user, bot="auditor", task_contract=build_contract("custom", []))
    _receipt(session, run)
    draft = _delivery("completed", missing=[])
    # This is a deliberate server downgrade, not invalid JSON or bad evidence.
    evaluated = evaluate_delivery(run, draft, agent_runs.transcript(session, run))
    assert evaluated["status"] == "review_required" and evaluated["missing"] == []
    corrected = _delivery("completed", missing=[], summary="Three records were returned; the full population is unknown.")
    seen = _script(monkeypatch, [{"content": draft}, {"content": corrected}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 2
    assert run.outcome["status"] == "review_required"
    assert run.outcome["scientific_review"] == "automated_review_completed"
    assert run.outcome["summary"] == json.loads(corrected)["summary"]
    assert agent_runs.transcript(session, run)[-1].content == corrected


@pytest.mark.parametrize("invalid", [
    {"evidence_call_ids": ["invented-call"]},
    {"sections": {"observation": {"invalid_nested_value": 3}}},
])
def test_custom_review_rejects_bad_evidence_or_structure_and_keeps_the_original(session: Session, monkeypatch, invalid):
    project, user = _project(session)
    run = _run(session, project, user, bot="auditor", task_contract=build_contract("custom", []))
    _receipt(session, run)
    draft = _delivery("completed", missing=[])
    seen = _script(monkeypatch, [{"content": draft}, {"content": _delivery("completed", missing=[], **invalid)}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 2
    assert run.outcome["status"] == "review_required"
    assert run.outcome["scientific_review"] == "unavailable"
    assert run.outcome["summary"] == json.loads(draft)["summary"]
    assert agent_runs.transcript(session, run)[-1].content == draft
