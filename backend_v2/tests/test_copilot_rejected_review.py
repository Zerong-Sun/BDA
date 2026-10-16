"""Rejected factual replies remain inspectable and have one correction ceiling."""
import json
import uuid

import pytest
from backend_v2.app.copilot import agent_loop, agent_runs
from backend_v2.app.copilot.models import CopilotAgentTurn
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
    _receipt(session, run, {"items": [{"value": "1 nM"}], "child_call_id": "child-only"})
    return run


def _saved(session, rejection):
    return session.get(CopilotAgentTurn, uuid.UUID(rejection["turn_id"]))


def test_invalid_review_is_saved_then_corrected_once_with_exact_call_scope(session, monkeypatch):
    run = _setup(session)
    original = _delivery()
    rejected = _delivery(evidence_call_ids=["child-only"])
    corrected = _delivery(summary="Checked only this query; independent validation remains required.")
    seen = _script(monkeypatch, [{"content": original}, {"content": rejected}, {"content": corrected}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 3
    assert run.outcome["scientific_review"] == "automated_review_completed"
    assert run.outcome["scientific_review_format_repair"] == "attempted_once"
    rejection, = run.outcome["scientific_review_rejections"]
    assert rejection["validation_errors"] == ["unverified_evidence_call_ids"]
    assert _saved(session, rejection).content == rejected
    for conversation in seen[1:]:
        packet = json.loads(conversation[1]["content"])
        assert packet["valid_evidence_calls"] == [{"call_id": "read-1", "tool": "list_project_candidates"}]
        assert "Nested child-run call IDs" in conversation[0]["content"]
    assert json.loads(seen[2][1]["content"])["draft"] == rejected


def test_invalid_format_correction_is_saved_and_never_gets_another_retry(session, monkeypatch):
    run = _setup(session)
    rejected = _delivery(evidence_call_ids=["child-only"])
    bad_format = "invalid review JSON"
    seen = _script(monkeypatch, [{"content": _delivery()}, {"content": rejected}, {"content": bad_format}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 3
    assert run.outcome["scientific_review"] == "unavailable"
    assert run.outcome["scientific_review_error"] == "invalid_review_delivery"
    failures = run.outcome["scientific_review_rejections"]
    assert [x["stage"] for x in failures] == ["factual_review", "format_repair"]
    assert failures[-1]["validation_errors"] == ["structured_delivery_required"]
    assert [_saved(session, x).content for x in failures] == [rejected, bad_format]
    assert run.outcome["summary"] == json.loads(_delivery())["summary"]


def test_failed_post_review_shortening_keeps_both_replies_and_does_not_add_format_retry(session, monkeypatch):
    run = _setup(session)
    long_review = _delivery(summary="字" * 700)
    bad_short = _delivery(evidence_call_ids=["child-only"])
    seen = _script(monkeypatch, [{"content": _delivery()}, {"content": long_review}, {"content": bad_short}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 3
    failures = run.outcome["scientific_review_rejections"]
    assert [x["stage"] for x in failures] == ["factual_review", "length_repair"]
    assert failures[0]["validation_errors"] == ["delivery_length_exceeded"]
    assert failures[1]["validation_errors"] == ["unverified_evidence_call_ids"]
    assert [_saved(session, x).content for x in failures] == [long_review, bad_short]
    assert run.outcome["scientific_review"] == "unavailable"
    assert "scientific_review_format_repair" not in run.outcome
    short_packet = json.loads(seen[2][1]["content"])
    assert short_packet["valid_evidence_calls"] == [{"call_id": "read-1", "tool": "list_project_candidates"}]
    assert short_packet["draft"]["evidence_call_ids"] == ["read-1"]


def test_rejected_review_consumes_turn_before_format_repair_budget_check(session, monkeypatch):
    run = _setup(session, max_turns=4)
    rejected = _delivery(evidence_call_ids=["child-only"])
    seen = _script(monkeypatch, [{"content": _delivery()}, {"content": rejected}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 2 and run.turn_count == 4
    assert run.outcome["scientific_review_error"] == "copilot_turn_limit_reached"
    assert run.outcome["scientific_review"] == "unavailable"
    rejection, = run.outcome["scientific_review_rejections"]
    assert _saved(session, rejection).content == rejected
    assert agent_runs.transcript(session, run)[-1].content == rejected


def test_empty_review_cannot_be_replaced_by_a_format_call_and_claim_review_completed(session, monkeypatch):
    run = _setup(session)
    seen = _script(monkeypatch, [{"content": _delivery()}, {"content": ""}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 2
    assert run.outcome["scientific_review"] == "unavailable"
    assert run.outcome["scientific_review_error"] == "invalid_review_delivery"
    rejection, = run.outcome["scientific_review_rejections"]
    assert rejection["validation_errors"] == ["structured_delivery_required"]
    assert _saved(session, rejection).content == ""


@pytest.mark.parametrize("repair_succeeds", [True, False])
def test_mixed_length_and_citation_error_uses_receipts_in_its_single_correction(session, monkeypatch, repair_succeeds):
    run = _setup(session)
    mixed = _delivery(summary="字" * 700, evidence_call_ids=["child-only"])
    corrected = _delivery() if repair_succeeds else _delivery(evidence_call_ids=["child-only"])
    seen = _script(monkeypatch, [{"content": _delivery()}, {"content": mixed}, {"content": corrected}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 3
    packet = json.loads(seen[2][1]["content"])
    assert set(packet["validation_errors"]) == {"delivery_length_exceeded", "unverified_evidence_call_ids"}
    assert packet["tool_records"][0]["result"]["items"] == [{"value": "1 nM"}]
    assert packet["tool_records"][0]["call_id"] == "read-1"
    assert packet["field_budgets"]["summary"] == 360
    assert packet["draft"] == mixed
    assert run.outcome["scientific_review_format_repair"] == "attempted_once"
    assert "scientific_review_length_repair" not in run.outcome
    assert run.outcome["scientific_review"] == ("automated_review_completed" if repair_succeeds else "unavailable")
    failures = run.outcome["scientific_review_rejections"]
    assert _saved(session, failures[0]).content == mixed
    if not repair_succeeds:
        assert failures[-1]["validation_errors"] == ["unverified_evidence_call_ids"]
        assert run.outcome["scientific_review_error"] == "invalid_review_delivery"
