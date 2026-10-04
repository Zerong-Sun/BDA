"""Bounded correction must use real evidence; a second invalid answer is never blessed."""
import json

import pytest
from backend_v2.app.copilot import agent_loop, agent_runs
from backend_v2.app.copilot.task_contracts import build_contract
from backend_v2.tests.test_copilot_agent_loop import _project, _provider, _run, _script
from backend_v2.tests.test_copilot_agent_loop import session as session_fixture


@pytest.fixture(name="session")
def db_session():
    yield from session_fixture.__wrapped__()


def answer(call_id):
    return json.dumps({"status":"completed", "summary":"A test brief from recorded evidence.",
        "sections":{"objective":"Read only", "constraints":"No real experiment",
                    "success_criteria":"Human review", "missing_inputs":"None for this draft"},
        "evidence_call_ids":[call_id], "missing":[], "next_action":"Human review"})


@pytest.mark.parametrize("repair_id,expected", [("real-call", "completed"), ("invented-again", "review_required")])
def test_repair_is_bounded_and_revalidates_exact_call_ids(session, monkeypatch, repair_id, expected):
    project, user = _project(session)
    run = _run(session, project, user, task_contract=build_contract("brief", []))
    agent_runs.append_turn(session, run, role="tool", content='{"project":"synthetic"}',
                          tool_calls=[{"name":"research_overview", "tool_call_id":"real-call"}])
    seen = _script(monkeypatch, [{"content": answer("invented")}, {"content": answer(repair_id)}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 2
    assert run.outcome["status"] == expected
    packet = json.loads(seen[1][1]["content"])
    assert packet["tool_records"][0]["call_id"] == "real-call"
    assert run.outcome["format_repair"] == "attempted_once"
    assert "invented" not in run.outcome["evidence_call_ids"]


def test_model_sees_exact_evidence_ids_and_remaining_budget(session):
    project, user = _project(session)
    run = _run(session, project, user, max_turns=24)
    agent_runs.append_turn(session, run, role="tool", content='[]',
                          tool_calls=[{"name":"list_project_targets", "tool_call_id":"actual-empty-read"}])
    messages = agent_loop.messages_for(run, agent_runs.transcript(session, run))
    assert '"call_id": "actual-empty-read"' in messages[-1]["content"]
    assert '"successful": true' in messages[-1]["content"]
    assert "23 messages" in messages[-1]["content"]


def test_a_premature_answer_gets_only_two_chances_to_finish_required_reads(session, monkeypatch):
    project, user = _project(session)
    run = _run(session, project, user, allowed_tools=["research_overview"], task_contract=build_contract("brief", []))
    seen = _script(monkeypatch, [{"content": answer("invented")} for _ in range(4)])
    assert agent_loop.step(session, run, _provider(session)) == "running"
    assert run.outcome["delivery_retry_count"] == 1
    assert agent_loop.step(session, run, _provider(session)) == "running"
    assert run.outcome["delivery_retry_count"] == 2
    agent_loop.step(session, run, _provider(session))
    assert run.status == "succeeded"
    assert run.outcome["status"] == "review_required"
    assert "context" in run.outcome["missing"]
    assert len(seen) == 4  # Three initial answers plus at most one format repair.


@pytest.mark.parametrize("kind", ["brief", "interpretation"])
def test_optional_repair_and_review_cannot_call_after_the_turn_ceiling(session, monkeypatch, kind):
    project, user = _project(session)
    run = _run(session, project, user, max_turns=2, task_contract=build_contract(kind, []))
    tool = "research_overview" if kind == "brief" else "list_project_candidates"
    agent_runs.append_turn(session, run, role="tool", content='[{"id":"synthetic"}]',
                          tool_calls=[{"name": tool, "tool_call_id": "real-call"}])
    draft = json.loads(answer("invented" if kind == "brief" else "real-call"))
    draft["sections"] = {key: "Synthetic evidence only" for key in run.task_contract["required_sections"]}
    seen = _script(monkeypatch, [{"content": json.dumps(draft)}] * 3)

    agent_loop.step(session, run, _provider(session))

    assert len(seen) == 1
    assert run.turn_count == run.max_turns
    assert run.outcome["status"] == "review_required"
    stage = "format_repair" if kind == "brief" else "scientific_review"
    assert run.outcome[stage] == "unavailable"


@pytest.mark.parametrize("result", [[], {"error": "artifact_not_found"}])
def test_attempted_required_read_can_end_with_an_honest_blocked_delivery(session, monkeypatch, result):
    project, user = _project(session)
    run = _run(session, project, user, allowed_tools=["list_experiment_results"],
               task_contract=build_contract("interpretation", []))
    agent_runs.append_turn(session, run, role="tool", content=json.dumps(result),
                          tool_calls=[{"name": "list_experiment_results", "tool_call_id": "empty-read"}])
    draft = {"status": "blocked", "summary": "The requested measured results are unavailable.",
             "sections": {key: "No measurements were retrieved." for key in run.task_contract["required_sections"]},
             "evidence_call_ids": ["empty-read"] if result == [] else [],
             "missing": ["measured results"], "next_action": "Provide the relevant measured results."}
    # An attempted empty/failed read must not trigger another read. The bounded
    # factual reviewer may still verify the explanation for the blocked state.
    seen = _script(monkeypatch, [{"content": json.dumps(draft)}] * 2)

    agent_loop.step(session, run, _provider(session))

    assert run.status == "succeeded"
    assert run.outcome["status"] == "blocked"
    assert "results" in run.outcome["missing"]
    assert len(seen) == 2
    assert run.outcome["scientific_review"] == "automated_review_completed"
    assert "delivery_retry_count" not in run.outcome
    review = json.loads(seen[1][1]["content"])
    assert review["draft"]["status"] == "blocked"
    assert review["tool_records"] == [{"call_id": "empty-read", "tool": "list_experiment_results",
                                      "successful": result == [], "result": result, "arguments": None}]
    turns = agent_runs.transcript(session, run)
    assert len([turn for turn in turns if turn.role == "tool"]) == 1
    assert not any(turn.tool_calls for turn in turns if turn.role == "assistant")
