"""Saved-window integrity and one bounded scope check; no live provider calls."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot import agent_loop, agent_runs
from backend_v2.app.copilot.task_contracts import (
    DELIVERY_SECTIONS,
    build_contract,
    evaluate_delivery,
    pending_source_coverage,
    progress,
    source_coverage,
    task_view,
)
from backend_v2.tests.test_copilot_agent_loop import _call, _project, _provider, _run
from backend_v2.tests.test_copilot_agent_loop import session as session  # noqa: F401


def _page(offset=0, count=50, total=66, document="document", checksum="a" * 64):
    rows = [{"kind": "literature_excerpt", "data": {
        "document_id": document, "ref_id": "R-saved", "chunk_id": f"{document}-{offset + n}",
        "content": f"Saved excerpt {offset + n}",
        "content_provenance": {"content_checksum_sha256": checksum, "retrieval_trace_id": "trace"},
    }} for n in range(count)]
    if rows:
        rows[0]["data"]["read_window"] = {
            "offset": offset, "returned_count": count, "total_count": total,
            "has_more": offset + count < total,
            "next_offset": offset + count if offset + count < total else None,
            # Last page still covers only a window of the document.
            "truncated": bool(offset or offset + count < total),
        }
    return rows


def _turn(result, call_id="page-1", name="get_reference_content"):
    return SimpleNamespace(role="tool", content=json.dumps(result),
                           tool_calls=[{"tool_call_id": call_id, "name": name}])


def _answer():
    return json.dumps({
        "status": "completed", "summary": "The observed excerpt answers this narrowly scoped question.",
        "sections": {key: "Scope is the read excerpts; other saved windows are not needed for this answer."
                     for key in DELIVERY_SECTIONS["literature"]},
        "missing": [], "evidence_call_ids": ["discovery", "page-1"],
        "next_action": "No additional source coverage is claimed.",
    })


def test_first_page_is_evidence_but_not_complete_source_coverage():
    turns = [_turn(_page())]
    assert progress(build_contract("literature", []), turns)[1]["status"] == "completed"
    coverage = source_coverage(turns)[0]
    assert coverage["document_id"] == "document"
    assert coverage["content_checksum_sha256"] == "a" * 64
    assert coverage["read_windows"] == [[0, 50]]
    assert coverage["read_count"] == 50 and coverage["total_count"] == 66
    assert coverage["known_next_offset"] == 50
    assert not coverage["coverage_complete"]
    assert pending_source_coverage(turns) == [coverage]


def test_source_coverage_does_not_force_narrow_answer_to_be_partial():
    turns = [_turn([], "discovery", "search_research"), _turn(_page())]
    run = SimpleNamespace(task_contract=build_contract("literature", []), outcome={})
    run.outcome = evaluate_delivery(run, _answer(), turns)
    assert run.outcome["status"] == "completed"
    view = task_view(run, turns)
    assert view["status"] == "completed"
    assert view["source_coverage"][0]["coverage_complete"] is False


def test_later_page_completes_union_even_though_its_window_is_truncated():
    last = _page(50, 16)
    assert last[0]["data"]["read_window"]["truncated"] is True
    turns = [_turn(_page()), _turn(last, "page-2")]
    coverage = source_coverage(turns)[0]
    assert coverage["read_windows"] == [[0, 66]]
    assert coverage["read_count"] == 66
    assert coverage["coverage_complete"] is True
    assert coverage["known_next_offset"] is None
    assert pending_source_coverage(turns) == []


def test_repeated_and_overlapping_windows_do_not_double_count():
    turns = [_turn(_page()), _turn(_page(), "repeat"), _turn(_page(40, 16), "overlap")]
    coverage = source_coverage(turns)[0]
    assert coverage["read_windows"] == [[0, 56]]
    assert coverage["read_count"] == 56 and coverage["known_next_offset"] == 56
    assert not coverage["coverage_complete"]


def test_checksums_are_separate_and_unseen_prefix_remains_unread():
    turns = [_turn(_page()), _turn(_page(50, 16, checksum="b" * 64), "new-version")]
    sources = source_coverage(turns)
    assert len(sources) == 2
    assert [item["read_count"] for item in sources] == [50, 16]
    assert sources[1]["known_next_offset"] == 0
    assert not any(item["coverage_complete"] for item in sources)
    # Only a source observed to have more pages receives automatic feedback.
    assert [item["content_checksum_sha256"] for item in pending_source_coverage(turns)] == ["a" * 64]


@pytest.mark.parametrize("bad", [[], None, {"error": "unavailable"}, {"status": "failed"},
                                  [{"data": "not-a-row"}], [{"data": {"content_provenance": "bad"}}]])
def test_empty_failed_or_malformed_reads_do_not_erase_known_gap(bad):
    turns = [_turn(_page()), _turn(bad, "bad-read")]
    assert source_coverage(turns) == source_coverage(turns[:1])


def test_malformed_secondary_provenance_is_ignored_without_crashing():
    invalid = _page(50, 16)
    invalid[1]["data"]["content_provenance"] = "not-a-dict"
    assert source_coverage([_turn(_page()), _turn(invalid, "bad")])[0]["read_count"] == 50


def test_conflicting_totals_remain_explicit_and_do_not_invent_a_cursor():
    coverage = source_coverage([_turn(_page()), _turn(_page(50, 16, total=70), "changed")])[0]
    assert coverage["observed_total_counts"] == [66, 70]
    assert coverage["total_count"] is None
    assert not coverage["coverage_complete"] and coverage["known_next_offset"] is None


def _seeded_run(session, monkeypatch, **kwargs):
    project, user = _project(session)
    run = _run(session, project, user, bot="researcher", goal="Answer from the named saved source.",
               allowed_tools=kwargs.pop("allowed_tools", ["get_reference_content", "search_research"]),
               task_contract=build_contract("literature", []), **kwargs)
    for turn in [_turn([], "discovery", "search_research"), _turn(_page())]:
        agent_runs.append_turn(session, run, role=turn.role, content=turn.content, tool_calls=turn.tool_calls)
    # Scientific review is a separate phase; these tests pin only the coverage check.
    monkeypatch.setattr(agent_loop, "needs_review", lambda *args: False)
    return run


def _script(monkeypatch, replies):
    seen = []
    replies = iter(replies)

    def fake(provider, messages, *, tools=None):
        seen.append({"messages": messages, "tools": tools})
        return next(replies)

    monkeypatch.setattr(agent_loop, "completion_message", fake)
    return seen


def test_only_one_check_is_offered_and_can_accept_a_scoped_answer(session, monkeypatch):
    run = _seeded_run(session, monkeypatch)
    seen = _script(monkeypatch, [{"content": _answer()}, {"content": _answer()}])
    agent_loop.drive(session, run, _provider(session))
    assert len(seen) == 2
    assert run.status == "succeeded" and run.outcome["status"] == "completed"
    assert run.outcome["source_coverage_check"] == {"attempts": 1, "status": "responded"}
    check = "\n".join(message["content"] or "" for message in seen[1]["messages"])
    assert "One bounded source-coverage check" in check
    assert '"known_next_offset": 50' in check
    assert "narrow" in check and "partial" in check
    assert any(tool["function"]["name"] == "get_reference_content" for tool in seen[1]["tools"])
    assert run.outcome["source_coverage"][0]["read_count"] == 50


@pytest.mark.parametrize("result", [_page(50, 16), [], {"error": "saved-source-unavailable"}])
def test_check_can_read_next_page_and_never_repeats_after_empty_or_failed_read(session, monkeypatch, result):
    run = _seeded_run(session, monkeypatch)
    seen = _script(monkeypatch, [
        {"content": _answer()},
        {"content": "Read the known remaining window.", "tool_calls": [_call("page-2", "get_reference_content", {"reference_id": "document", "offset": 50})]},
        {"content": _answer()},
    ])
    monkeypatch.setattr(agent_loop, "_tool_context", lambda *args: SimpleNamespace())
    monkeypatch.setattr(agent_loop, "_run_tool", lambda *args: (result, None))
    agent_loop.drive(session, run, _provider(session))
    assert len(seen) == 3 and run.status == "succeeded"
    assert run.outcome["source_coverage_check"]["attempts"] == 1
    assert run.outcome["source_coverage"][0]["read_count"] == (66 if isinstance(result, list) and result else 50)
    if isinstance(result, list) and result:
        assert not any("One bounded source-coverage check" in (m["content"] or "") for m in seen[2]["messages"])


def test_missing_read_tool_preserves_draft_and_gap_without_another_model_call(session, monkeypatch):
    run = _seeded_run(session, monkeypatch, allowed_tools=["search_research"])
    seen = _script(monkeypatch, [{"content": _answer()}])
    agent_loop.drive(session, run, _provider(session))
    assert len(seen) == 1
    assert run.outcome["status"] == "partial" and run.outcome["summary"].startswith("The observed excerpt")
    assert "get_reference_content is unavailable" in run.outcome["source_coverage_check"]["reason"]
    assert any("read 50 of 66" in item for item in run.outcome["missing"])


def test_turn_limit_preserves_draft_and_never_calls_again(session, monkeypatch):
    run = _seeded_run(session, monkeypatch, max_turns=3)
    seen = _script(monkeypatch, [{"content": _answer()}])
    agent_loop.drive(session, run, _provider(session))
    assert len(seen) == 1 and run.turn_count == 3
    assert run.status == "succeeded" and run.outcome["status"] == "partial"
    assert "turn limit" in run.outcome["source_coverage_check"]["reason"]


def test_cost_reservation_denial_preserves_gap_and_never_calls_over_budget(session, monkeypatch):
    run = _seeded_run(session, monkeypatch, max_cost_usd_cents=3)
    provider = _provider(session)
    # Every provider call reserves2 cents. The first draft fits; its check does not.
    provider.config = {"bda_pricing": {"input_usd_per_million": 0, "output_usd_per_million": 1}, "max_tokens": 4000}
    seen = _script(monkeypatch, [{"content": _answer()}])
    agent_loop.drive(session, run, provider)
    assert len(seen) == 1 and run.cost_usd_cents == 2
    assert run.status == "succeeded" and run.outcome["status"] == "partial"
    assert "copilot_budget_insufficient" in run.outcome["source_coverage_check"]["reason"]
    assert run.outcome["scientific_review"] == "unavailable"
    assert "scientific_review_unavailable" in run.outcome["missing"]
    assert run.outcome["source_coverage"][0]["known_next_offset"] == 50
    assert any("read 50 of 66" in item for item in run.outcome["missing"])


@pytest.mark.parametrize("status", ["blocked", "needs_input"])
def test_coverage_limit_does_not_upgrade_an_existing_stop(session, monkeypatch, status):
    run = _seeded_run(session, monkeypatch, max_turns=3)
    answer = {**json.loads(_answer()), "status": status, "missing": ["Required input unavailable."]}
    seen = _script(monkeypatch, [{"content": json.dumps(answer)}])
    agent_loop.drive(session, run, _provider(session))
    assert len(seen) == 1
    assert run.outcome["status"] == status
    assert run.outcome["scientific_review"] == "unavailable"
    assert "Required input unavailable." in run.outcome["missing"]


def test_full_source_does_not_trigger_an_extra_check(session, monkeypatch):
    run = _seeded_run(session, monkeypatch)
    page = _turn(_page(50, 16), "page-2")
    agent_runs.append_turn(session, run, role=page.role, content=page.content, tool_calls=page.tool_calls)
    seen = _script(monkeypatch, [{"content": _answer()}])
    agent_loop.drive(session, run, _provider(session))
    assert len(seen) == 1
    assert "source_coverage_check" not in run.outcome
    assert run.outcome["source_coverage"][0]["coverage_complete"] is True
