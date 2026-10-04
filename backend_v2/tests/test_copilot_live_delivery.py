"""Delivery regressions observed in isolated live bot acceptance.

These tests replay response shapes, not live model requests or public/private
research data. Empty reads, untraced excerpts and draft completion are separate
claims and must stay separate in the resulting delivery status.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot.task_contracts import (
    DELIVERY_SECTIONS,
    build_contract,
    evaluate_delivery,
    progress,
    tool_records,
)


def _turn(tool: str, result, call_id: str = "read-1"):
    return SimpleNamespace(
        role="tool", content=json.dumps(result),
        tool_calls=[{"name": tool, "tool_call_id": call_id}],
    )


def _delivery(kind: str = "execution", **overrides) -> str:
    return json.dumps({
        "status": "completed",
        "summary": "The recorded failure is a synthetic fixture, not a GPU failure.",
        "sections": {key: "Recorded evidence; no computation was submitted." for key in DELIVERY_SECTIONS[kind]},
        "evidence_call_ids": ["workflow-read", "job-read"],
        "missing": [],
        "next_action": "Review the recorded fixture state.",
        **overrides,
    })


def _execution_turns():
    return [
        _turn("get_workflow_status", [{"id": "fixture-workflow", "data": {"status": "running"}}], "workflow-read"),
        _turn("get_compute_status", {"drafts": [], "jobs": [{"data": {"status": "failed", "error_code": "synthetic_oom_fixture"}}]}, "job-read"),
    ]


def test_empty_reads_are_successful_but_do_not_establish_recorded_results():
    turns = [_turn("list_experiment_results", []), _turn("list_project_candidates", [], "read-2")]
    assert all(record["successful"] for record in tool_records(turns))
    result_step = progress(build_contract("interpretation", []), turns)[0]
    assert result_step["status"] == "pending"
    assert result_step["evidence_call_ids"] == []
    turns.append(_turn("list_project_candidates", [{"id": "synthetic-candidate"}], "read-3"))
    assert progress(build_contract("interpretation", []), turns)[0]["evidence_call_ids"] == ["read-3"]


def test_empty_results_can_be_cited_to_explain_an_incomplete_interpretation():
    run = SimpleNamespace(task_contract=build_contract("interpretation", []))
    answer = _delivery("interpretation", status="needs_input", evidence_call_ids=["read-1"], missing=["No recorded candidate or experiment results."])
    outcome = evaluate_delivery(run, answer, [_turn("list_experiment_results", [])])
    assert outcome["status"] == "needs_input"
    assert outcome["evidence_call_ids"] == ["read-1"]
    assert "unverified_evidence_call_ids" not in outcome["missing"]
    assert "results" in outcome["missing"]


@pytest.mark.parametrize("result", [None, {"error": "permission denied"}, {"status": "failed"}, {"status": "cancelled"}, {"status": "pending"}, {"status": "running"}])
def test_errors_and_unsettled_operations_still_do_not_satisfy_steps(result):
    turns = [_turn("start_literature_search", result)]
    assert not tool_records(turns)[0]["successful"]
    assert progress(build_contract("literature", ["start_literature_search"]), turns)[0]["status"] == "pending"


@pytest.mark.parametrize("status", ["succeeded", "failed", "cancelled"])
def test_settled_compute_wait_is_valid_evidence_even_when_job_failed(status):
    result = {"kind": "gpu_job", "resource_id": "fixture-job", "status": status,
              "job_status": status, "error": None if status == "succeeded" else "job " + status}
    assert tool_records([_turn("await_compute_job", result)])[0]["successful"]
    run = SimpleNamespace(task_contract=build_contract("custom", []))
    outcome = evaluate_delivery(run, _delivery(evidence_call_ids=["read-1"]), [_turn("await_compute_job", result)])
    assert "unverified_evidence_call_ids" not in outcome["missing"]


@pytest.mark.parametrize("result", [{"error": "job_not_found"}, {"kind": "gpu_job", "resource_id": "job", "job_status": "running", "status": "running"}])
def test_failed_or_unsettled_compute_wait_is_not_valid_evidence(result):
    assert not tool_records([_turn("await_compute_job", result)])[0]["successful"]


@pytest.mark.parametrize("status", ["succeeded", "failed", "cancelled"])
def test_already_terminal_job_read_is_valid_evidence(status):
    result = {"job_id": "job", "status": status, "waiting": False, "error_code": "fixture"}
    assert tool_records([_turn("await_compute_job", result)])[0]["successful"]


@pytest.mark.parametrize("status", ["running", "failed", "cancelled"])
def test_auditor_can_cite_a_failed_or_unfinished_producers_actual_records(status):
    result = {"run_id": "producer", "status": status, "tool_results": [{"result": [1, 2, 3]}]}
    assert tool_records([_turn("read_operator_work", result)])[0]["successful"]
    assert not tool_records([_turn("read_operator_work", {"error": "run_not_in_project"})])[0]["successful"]


@pytest.mark.parametrize("format_answer", [
    lambda body: body,
    lambda body: " \n```json\n" + body + "\n```\n ",
    lambda body: "I have both the workflow and job states. Here is my delivery.\n\n```json\n" + body + "\n```",
    lambda body: "已读取记录。\n```JSON\n" + body + "\n```",
    lambda body: "```\n" + body + "\n```",
])
def test_one_final_json_object_survives_provider_presentation_variants(format_answer):
    run = SimpleNamespace(task_contract=build_contract("execution", []))
    outcome = evaluate_delivery(run, format_answer(_delivery()), _execution_turns())
    assert outcome["status"] == "completed"
    assert outcome["evidence_call_ids"] == ["workflow-read", "job-read"]
    assert outcome["missing"] == []
    assert outcome["summary"].startswith("The recorded failure is a synthetic fixture")


@pytest.mark.parametrize("wrap", [
    lambda body: "```json\n" + body + "\n```\nBut the evidence above may be wrong.",
    lambda body: "```json\n" + body + "\n```\n```json\n" + body + "\n```",
    lambda body: "```python\n" + body + "\n```",
    lambda body: "```json\n" + body,
    lambda body: "Here is the object: " + body,
])
def test_ambiguous_or_malformed_final_deliveries_still_require_review(wrap):
    run = SimpleNamespace(task_contract=build_contract("execution", []))
    outcome = evaluate_delivery(run, wrap(_delivery()), _execution_turns())
    assert outcome["status"] == "review_required"
    assert outcome["missing"] == ["structured_delivery_required"]


def test_fenced_delivery_cannot_bypass_evidence_or_missing_work_checks():
    run = SimpleNamespace(task_contract=build_contract("execution", []))

    def wrap(body):
        return "Here is my delivery.\n```json\n" + body + "\n```"

    fabricated = evaluate_delivery(run, wrap(_delivery(evidence_call_ids=["invented"])), _execution_turns())
    assert fabricated["status"] == "review_required"
    assert "unverified_evidence_call_ids" in fabricated["missing"]
    unfinished = evaluate_delivery(run, wrap(_delivery(missing=["A running job has not settled."])), _execution_turns())
    assert unfinished["status"] == "partial"
    assert "A running job has not settled." in unfinished["missing"]


def test_live_excerpt_wrapper_requires_actual_content_provenance():
    # The live R-EN transcript returned this nested shape with empty provenance.
    # Metadata verification cannot replace a saved content checksum/trace.
    excerpt = {"kind": "literature_excerpt", "id": "chunk", "data": {
        "document_id": "document", "ref_id": "R036", "chunk_id": "chunk",
        "content": "A saved abstract excerpt.", "chunk_version": 1,
        "review_status": "pending_review", "content_provenance": {},
    }}
    contract = build_contract("literature", [])
    turns = [_turn("get_reference_content", [excerpt])]
    assert tool_records(turns)[0]["successful"]
    assert progress(contract, turns)[1]["status"] == "pending"
    excerpt["data"]["content_provenance"] = {
        "content_kind": "abstract", "content_checksum_sha256": "a" * 64,
        "retrieval_trace_id": "saved-retrieval-trace",
    }
    turns = [_turn("get_reference_content", [excerpt])]
    assert progress(contract, turns)[1]["status"] == "completed"


@pytest.mark.parametrize("missing_field", ["content_checksum_sha256", "retrieval_trace_id"])
def test_excerpt_with_incomplete_provenance_does_not_unlock_delivery(missing_field):
    provenance = {"content_checksum_sha256": "a" * 64, "retrieval_trace_id": "trace"}
    del provenance[missing_field]
    turns = [_turn("get_reference_content", [{"data": {"chunk_id": "chunk", "content_provenance": provenance}}])]
    assert progress(build_contract("literature", []), turns)[1]["status"] == "pending"


@pytest.mark.parametrize("content", [None, "", "   ", {"claim": "metadata only"}])
def test_traced_metadata_without_excerpt_text_never_completes_the_read_step(content):
    excerpt = {"chunk_id": "chunk", "content": content, "content_provenance": {
        "content_checksum_sha256": "a" * 64, "retrieval_trace_id": "trace",
    }}
    turns = [_turn("get_reference_content", [{"data": excerpt}])]
    assert tool_records(turns)[0]["successful"]
    assert progress(build_contract("literature", []), turns)[1]["status"] == "pending"
