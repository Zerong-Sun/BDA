"""Real-run regressions: nested room payloads and ignored delivery limits."""
import json
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot import agent_loop, agent_runs
from backend_v2.app.copilot.agent_review import review_messages
from backend_v2.app.copilot.delivery_context import delivery_constraints, room_preview
from backend_v2.app.copilot.task_contracts import build_contract, evaluate_delivery
from backend_v2.app.core.problem import DomainError
from backend_v2.tests.test_copilot_agent_loop import _project, _provider, _run, _script
from backend_v2.tests.test_copilot_agent_loop import session as session_fixture
from backend_v2.tests.test_copilot_agent_review import _delivery, _receipt


@pytest.fixture(name="session")
def db_session():
    yield from session_fixture.__wrapped__()


@pytest.mark.parametrize(("goal", "expected"), [
    ("每名成员200字；最终中文汇报不超过600字。", 600),
    ("最终汇报所有可见文字合计不超过600字", 600),
    ("所有可见文字合计最多300字符", 300),
    ("Final report at most 600 characters", 600),
    ("文献共600字，每名成员200字", None),
    ("Final report at most 600 words", None),
    ("不要求最终汇报不超过600字", None),
])
def test_only_explicit_final_character_limit(goal, expected):
    assert delivery_constraints(SimpleNamespace(goal=goal), [])["max_visible_characters"] == expected


def test_followup_limit_overrides_goal_but_tool_text_cannot():
    run = SimpleNamespace(goal="最终报告不超过600字")
    turns = [SimpleNamespace(role="user", content="全部可见文字最多400字"),
             SimpleNamespace(role="tool", content="最终报告最多900字")]
    assert delivery_constraints(run, turns)["max_visible_characters"] == 400
    turns.append(SimpleNamespace(role="user", content="取消字数限制，保留必要依据。"))
    assert delivery_constraints(run, turns)["max_visible_characters"] is None


def test_room_preview_is_bounded_idempotent_and_preserves_exact_ids_and_states():
    original = {"active_tasks": [{"run_id": "root", "status": "running", "goal": "任务"}],
                "recent_activity": [{"id": "event", "kind": "message", "bot": "auditor",
                                     "message": {"content": "x" * 5000, "sources": [{"data": "x" * 500000}]}}]}
    result = room_preview(original)
    assert len(json.dumps(result)) < 2500
    assert result["active_tasks"] == original["active_tasks"]
    message = result["recent_activity"][0]["message"]
    assert message["content_truncated"] and message["omitted_fields"] == ["sources"]
    assert result == room_preview(result)
    assert len(original["recent_activity"][0]["message"]["content"]) == 5000


def test_historical_room_receipt_compacted_in_actor_repair_review_not_storage(session, monkeypatch):
    project, user = _project(session)
    run = _run(session, project, user, bot="conductor", task_contract=build_contract("custom", []))
    _receipt(session, run)
    old = {"active_tasks": [], "recent_activity": [{"kind": "message", "message": {
        "content": "Past report", "sources": [{"payload": "x" * 500000}]}}]}
    agent_runs.append_turn(session, run, role="tool", content=json.dumps(old),
                           tool_calls=[{"name": "read_team_progress", "tool_call_id": "room-1"}])
    agent_runs.append_turn(session, run, role="user", content="只汇报本轮已完成事项。")
    turns = agent_runs.transcript(session, run)
    seen = _script(monkeypatch, [{"content": "bad format"}, {"content": _delivery()}, {"content": _delivery()}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 3
    assert all(len(json.dumps(messages)) < 40000 for messages in seen)
    assert json.loads(seen[1][1]["content"])["user_followups"] == ["只汇报本轮已完成事项。"]
    assert json.loads(seen[2][1]["content"])["user_followups"] == ["只汇报本轮已完成事项。"]
    assert json.loads(turns[-2].content) == old


def test_overlong_delivery_gets_bounded_repair_and_short_review(session, monkeypatch):
    project, user = _project(session)
    run = _run(session, project, user, bot="conductor", goal="最终汇报不超过300字", task_contract=build_contract("custom", []))
    _receipt(session, run)
    long = _delivery(summary="字" * 301)
    initial = evaluate_delivery(run, long, agent_runs.transcript(session, run))
    assert initial["status"] == "review_required" and "delivery_length_exceeded" in initial["missing"]
    short = _delivery(summary="已核对，尚待科学验证。")
    seen = _script(monkeypatch, [{"content": long}, {"content": short}, {"content": short}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 3
    assert json.loads(seen[1][1]["content"])["repair_reasons"] == ["delivery_length_exceeded"]
    assert run.outcome["scientific_review"] == "automated_review_completed"
    assert "delivery_length_exceeded" not in run.outcome["missing"]
    assert json.loads(seen[1][1]["content"])["delivery_constraints"]["max_visible_characters"] == 300


def test_returned_review_required_is_not_malformed_and_length_diagnostic_is_recomputed(session):
    project, user = _project(session)
    run = _run(session, project, user, goal="最终汇报不超过300字", task_contract=build_contract("custom", []))
    _receipt(session, run)
    outcome = evaluate_delivery(run, _delivery("review_required", missing=["delivery_length_exceeded"]), agent_runs.transcript(session, run))
    assert outcome["status"] == "review_required"
    assert outcome["missing"] == []
    assert outcome["evidence_call_ids"] == ["read-1"]


def test_failed_review_keeps_draft_and_safe_actionable_error(session, monkeypatch):
    project, user = _project(session)
    run = _run(session, project, user, bot="conductor", task_contract=build_contract("custom", []))
    _receipt(session, run)
    calls = []
    def fake(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            return {"content": _delivery()}
        raise DomainError("llm_output_truncated", "sensitive provider diagnostic", status_code=502)
    monkeypatch.setattr(agent_loop, "completion_message", fake)
    agent_loop.step(session, run, _provider(session))
    assert run.status == "succeeded" and run.outcome["status"] == "review_required"
    assert run.outcome["scientific_review_error"] == "llm_output_truncated"
    assert "sensitive" not in json.dumps(run.outcome)
    assert run.outcome["summary"] == json.loads(_delivery())["summary"]
    assert review_messages(run, agent_runs.transcript(session, run))


def test_truncated_review_retries_once_without_changing_saved_provider_or_ceiling(session, monkeypatch):
    project, user = _project(session)
    run = _run(session, project, user, bot="conductor", task_contract=build_contract("custom", []))
    _receipt(session, run)
    provider = _provider(session)
    provider.endpoint = "https://api.deepseek.com/v1"
    provider.model = "deepseek-flash"
    provider.config = {"max_tokens": 16384, "thinking": {"type": "enabled"}}
    configs = []
    def fake(selected, *args, **kwargs):
        configs.append(dict(selected.config))
        if len(configs) == 2:
            raise DomainError("llm_output_truncated", "truncated", status_code=502)
        return {"content": _delivery()}
    monkeypatch.setattr(agent_loop, "completion_message", fake)
    agent_loop.step(session, run, provider)
    assert len(configs) == 3
    assert configs[-1]["thinking"] == {"type": "disabled"}
    assert configs[-1]["response_format"] == {"type": "json_object"}
    assert all(config["max_tokens"] == 16384 for config in configs)
    assert provider.config == {"max_tokens": 16384, "thinking": {"type": "enabled"}}
    assert run.outcome["scientific_review"] == "automated_review_completed"
    assert run.outcome["scientific_review_recovery"] == "truncated_output_json_retry"


@pytest.mark.parametrize("endpoint", ["https://third-party.example/v1", "https://api.deepseek.com.evil.example/v1"])
def test_third_party_provider_never_receives_guessed_deepseek_options(session, endpoint):
    from backend_v2.app.copilot.provider import structured_retry_provider
    provider = _provider(session)
    provider.endpoint, provider.model = endpoint, "deepseek-flash"
    assert structured_retry_provider(provider) is None


@pytest.mark.parametrize("max_turns, expected_calls", [(10, 3), (4, 2)])
def test_review_length_correction_is_bounded_and_cannot_bypass_turn_budget(session, monkeypatch, max_turns, expected_calls):
    project, user = _project(session)
    run = _run(session, project, user, bot="conductor", max_turns=max_turns,
               goal="最终汇报不超过300字", task_contract=build_contract("custom", []))
    _receipt(session, run)
    short = _delivery(summary="已完成本轮核对，仍待科学验证。")
    seen = _script(monkeypatch, [{"content": short}, {"content": _delivery(summary="字" * 301)}, {"content": short}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == expected_calls
    if max_turns == 4:
        assert run.outcome["scientific_review_error"] == "copilot_turn_limit_reached"
        assert run.outcome["scientific_review"] == "unavailable"
    else:
        assert run.outcome["scientific_review_length_repair"] == "attempted_once"
        assert run.outcome["scientific_review"] == "automated_review_completed"
    assert run.outcome["summary"] == json.loads(short)["summary"]
