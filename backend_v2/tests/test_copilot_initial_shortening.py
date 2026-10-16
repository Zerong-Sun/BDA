"""Initial oversized deliveries get one bounded shortening before factual review."""
import json

import pytest
from backend_v2.app.copilot import agent_loop, agent_runs
from backend_v2.app.copilot.delivery_context import visible_characters
from backend_v2.app.copilot.task_contracts import build_contract
from backend_v2.tests.test_copilot_agent_loop import _project, _provider, _run, _script
from backend_v2.tests.test_copilot_agent_loop import session as session_fixture
from backend_v2.tests.test_copilot_agent_review import _delivery, _receipt


@pytest.fixture(name="session")
def db_session():
    yield from session_fixture.__wrapped__()


def _setup(session, **kwargs):
    project, user = _project(session)
    run = _run(session, project, user, bot="conductor", goal="最终汇报不超过600字",
               task_contract=build_contract("custom", []), **kwargs)
    _receipt(session, run, {"items": [{"value": "1 nM"}], "original_evidence": "exact source receipt"})
    return run


def test_long_initial_draft_shortens_once_then_receives_original_receipt_review(session, monkeypatch):
    run = _setup(session)
    provider = _provider(session)
    provider.endpoint = "https://api.deepseek.com/v1"
    provider.model = "deepseek-flash"
    provider.config = {"max_tokens": 16384, "thinking": {"type": "enabled"}}
    replies = iter([
        {"content": _delivery(summary="字" * 700)},
        {"content": _delivery(summary="记录中有1 nM，仍待验证。")},
        {"content": _delivery(summary="记录值为1 nM，仅限已查来源，仍待验证。")},
    ])
    seen = []
    def fake(selected, messages, **kwargs):
        seen.append((dict(selected.config), messages))
        return next(replies)
    monkeypatch.setattr(agent_loop, "completion_message", fake)
    agent_loop.step(session, run, provider)
    assert len(seen) == 3
    short_packet = json.loads(seen[1][1][1]["content"])
    assert sum(short_packet["field_budgets"].values()) == 480
    assert short_packet["field_budgets"]["sections_combined_including_titles"] > 0
    assert short_packet["field_budgets"]["missing_combined"] == len("independent validation")
    assert short_packet["target_template"]["sections"] == {"observations": ""}
    assert "tool_records" not in short_packet
    assert short_packet["draft"]["evidence_call_ids"] == ["read-1"]
    assert "Only contract required_sections keys" in seen[1][1][0]["content"]
    assert seen[1][0]["thinking"] == {"type": "disabled"}
    assert seen[1][0]["max_tokens"] == 16384
    assert seen[2][0]["thinking"] == {"type": "enabled"}
    review_packet = json.loads(seen[2][1][1]["content"])
    assert review_packet["tool_records"][0]["result"]["original_evidence"] == "exact source receipt"
    assert run.outcome["scientific_review"] == "automated_review_completed"
    assert visible_characters(run.outcome) <= 600
    assert run.outcome["missing"] == ["independent validation"]
    assert json.loads(agent_runs.transcript(session, run)[2].content)["summary"] == "字" * 700


def test_still_oversized_initial_repair_stops_without_review_or_second_shortening(session, monkeypatch):
    run = _setup(session)
    long = _delivery(summary="字" * 700)
    seen = _script(monkeypatch, [{"content": long}, {"content": long}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 2
    assert run.outcome["format_repair"] == "attempted_once"
    assert run.outcome["status"] == "review_required"
    assert "delivery_length_exceeded" in run.outcome["missing"]
    assert "scientific_review" not in run.outcome
    assert run.outcome["summary"] == "字" * 700


def test_initial_shortening_cannot_exceed_transcript_budget(session, monkeypatch):
    run = _setup(session, max_turns=3)
    seen = _script(monkeypatch, [{"content": _delivery(summary="字" * 700)}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 1
    assert run.turn_count == 3
    assert run.outcome["format_repair_error"] == "copilot_turn_limit_reached"
    assert run.outcome["status"] == "review_required"
    assert "scientific_review" not in run.outcome


def test_combined_format_length_repair_keeps_receipts_and_field_budgets(session, monkeypatch):
    run = _setup(session)
    bad = _delivery(summary="字" * 700, evidence_call_ids=["invented"])
    short = _delivery(summary="记录有限，尚待独立验证。", sections={})
    seen = _script(monkeypatch, [{"content": bad}, {"content": short}, {"content": short}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 3
    packet = json.loads(seen[1][1]["content"])
    assert packet["field_budgets"]["summary"] == 360
    assert packet["tool_records"][0]["call_id"] == "read-1"
    assert set(packet["repair_reasons"]) == {"delivery_length_exceeded", "unverified_evidence_call_ids"}
    assert run.outcome["scientific_review"] == "automated_review_completed"
