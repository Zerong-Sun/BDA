"""Declared scales survive ingestion, triage and automatic screening."""
from __future__ import annotations

import uuid

import pytest
from backend_v2.app.candidates.triage import evaluate, triage
from backend_v2.app.compute.parsers import get_parser
from backend_v2.app.compute.parsers.base import ParseContext
from backend_v2.app.core import confidence_scale as scales
from backend_v2.app.workflows.gate_engine import evaluate as gate_evaluate
from backend_v2.app.workflows.gate_schemas import GatePolicy
from backend_v2.tests.test_compute_binding import env as _binding_env


def parse_csv(rows: str, *, metadata: dict | None = None):
    body = "run_id,cycle,pdb_filename,iptm,plddt,iplddt,plddt_scale,iplddt_scale\n" + rows
    return get_parser("proteinhunter_boltz")(ParseContext(
        job_id=uuid.uuid4(), project_id=uuid.uuid4(), attempt_number=1,
        outputs=[{"filename": "summary_high_iptm.csv", "object_key": "summary", "metadata": metadata or {}},
                 {"filename": "design.pdb", "object_key": "pdb"}],
        parameters={}, read_bytes=lambda key: body.encode(),
    ))


def test_native_provider_is_normalized_and_raw_value_remains_traceable():
    parsed = parse_csv("1,1,design.pdb,0.85,0.94,0.88,,\n")
    candidate = parsed.candidates[0]
    assert candidate.scores == {"iptm": 0.85, "plddt": 94.0, "iplddt": 88.0}
    metric = next(m for m in candidate.metrics if m.key == "plddt")
    assert metric.unit == "pLDDT_0_100"
    assert metric.context["reported_value"] == 0.94
    assert metric.context["reported_scale"] == scales.FRACTION
    assert metric.context["source_row"] == 2
    assert metric.context["scale_source"] == "provider:proteinhunter_boltz"
    assert candidate.properties["confidence_scale"]["plddt"]["stored_scale"] == scales.PERCENT
    assert evaluate([metric.__dict__], {"plddt": "> 70"})[0].outcome == "pass"
    decision = gate_evaluate([{"id": "a", "metrics": candidate.scores, "metric_sources": [m.__dict__ for m in candidate.metrics]}],
                            GatePolicy(rules={"conditions": [{"metric": "plddt", "value": 70}]}))[0]
    assert decision["passed"]


def test_declared_percent_preserves_genuinely_low_value_and_never_infers_from_column():
    parsed = parse_csv("1,1,design.pdb,0.85,0.8,90,percent_0_100,percent_0_100\n2,1,design.pdb,0.8,94,80,percent_0_100,percent_0_100\n")
    assert [c.scores["plddt"] for c in parsed.candidates] == [0.8, 94]
    assert parsed.candidates[0].metrics[1].context["reported_value"] == 0.8
    assert evaluate([parsed.candidates[0].metrics[1].__dict__], {"plddt": "> 70"})[0].outcome == "fail"


def test_output_declaration_supports_normalized_wrappers():
    candidate = parse_csv("1,1,design.pdb,0.85,90,80,,\n", metadata={"confidence_scales": {"plddt": scales.PERCENT, "iplddt": scales.PERCENT}}).candidates[0]
    assert candidate.scores["plddt"] == 90
    assert candidate.properties["confidence_scale"]["plddt"]["scale_source"] == "output_metadata"


def test_out_of_range_native_value_is_retained_as_conflict_not_reinterpreted():
    parsed = parse_csv("1,1,design.pdb,0.85,94,0.8,,\n")
    metric = next(m for m in parsed.candidates[0].metrics if m.key == "plddt")
    assert metric.value == metric.context["reported_value"] == 94
    assert metric.context["scale_status"] == "scale_conflict"
    assert any("scale_conflict" in message for message in parsed.warnings)
    assert evaluate([metric.__dict__], {"plddt": "> 70"})[0].outcome == "scale_conflict"


@pytest.mark.parametrize("value", [0, 0.8, 85, 101])
def test_unknown_history_is_not_classified_by_magnitude(value):
    verdict = triage([{"key": "plddt", "value": value}], {"a": {"plddt": "> 70"}})
    assert verdict.tier is None and verdict.failed == 0 and verdict.scale_unknown == 1


@pytest.mark.parametrize("method", ["alphafold2_superfold", "alphafold3"])
def test_existing_known_alphafold_contracts_remain_usable(method):
    assert evaluate([{"key": "plddt", "value": 85, "method": method}], {"plddt": "> 70"})[0].outcome == "pass"
    assert evaluate([{"key": "plddt", "value": 0.8, "method": method}], {"plddt": "> 70"})[0].outcome == "fail"
    assert evaluate([{"key": "plddt", "value": 0.8, "method": method}], {"plddt": "> 0.7"})[0].outcome == "pass"


def test_mixed_known_and_unknown_seeds_cannot_be_cherry_picked():
    metrics = [{"key": "plddt", "value": 95, "method": "alphafold3"}, {"key": "plddt", "value": 0.9}]
    assert evaluate(metrics, {"plddt": "> 70"})[0].outcome == "scale_unknown"
    assert evaluate(list(reversed(metrics)), {"plddt": "> 70"})[0].outcome == "scale_unknown"


def test_native_fraction_history_blocks_as_conflict_without_a_design_failure():
    verdict = triage([{"key": "plddt", "value": 0.94, "method": "boltz2"}], {"a": {"plddt": "> 70"}})
    assert verdict.failed == 0 and verdict.conflicted == 1
    assert "not a design failure" in verdict.criteria[0].note


@pytest.mark.parametrize("rules", [
    {"operator": "or", "conditions": [{"metric": "plddt", "value": 70}, {"metric": "iptm", "value": 0.8}]},
    {"sort_metric": "plddt", "top_n": 1},
])
def test_unknown_scale_blocks_or_and_sort_only_gates(rules):
    decision = gate_evaluate([{"id": "a", "metrics": {"plddt": 0.94, "iptm": 0.9}}], GatePolicy(rules=rules))[0]
    assert not decision["passed"] and decision["needs_attention"]
    assert any(reason.startswith("scale_unknown:") for reason in decision["reasons"])


def test_fully_qualified_gate_metric_uses_its_own_source_unit():
    key = "plddt:boltz2:seed1:target"
    row = {"id": "a", "metrics": {key: 94}, "metric_sources": [{"key": "plddt", "method": "boltz2", "model_variant": "seed1", "condition": "target", "unit": "pLDDT_0_100"}]}
    assert gate_evaluate([row], GatePolicy(rules={"conditions": [{"metric": key, "value": 70}]}))[0]["passed"]


@pytest.mark.parametrize("value", [-1, 101, float("nan"), True])
def test_declared_percent_out_of_range_is_conflict(value):
    assert scales.comparison_issue("plddt", value, unit="pLDDT_0_100") == "scale_conflict"


def test_nonconfidence_metrics_have_no_added_unit_requirement():
    assert evaluate([{"key": "iptm", "value": 0.9}], {"iptm": "> 0.8"})[0].outcome == "pass"


@pytest.mark.parametrize("context,unit", [
    (["bad"], ""), ("bad", ""), ({"stored_scale": scales.PERCENT}, "0-1"),
    ({}, ["0-100"]), ({"stored_scale": scales.PERCENT, "scale_status": "garbage"}, ""),
])
def test_invalid_or_conflicting_declarations_cannot_pass(context, unit):
    assert scales.comparison_issue("plddt", 90, context=context, unit=unit) == "scale_conflict"


def test_explicit_unknown_status_is_not_promoted_by_stored_scale():
    assert scales.comparison_issue("plddt", 90, context={"stored_scale": scales.PERCENT, "scale_status": "unknown"}) == "scale_unknown"


@pytest.mark.parametrize("extras", [
    {"metric_sources": None}, {"metric_sources": [None]}, {"metric_sources": "bad"},
    {"metric_scales": []}, {"metric_sources": [{"key": "plddt", "context": "bad"}]},
    {"metric_sources": [{"key": "plddt", "unit": ["0-100"]}]},
])
def test_gate_malformed_source_metadata_fails_with_attention_instead_of_exception(extras):
    row = {"id": "a", "metrics": {"plddt": 90}, **extras}
    decision = gate_evaluate([row], GatePolicy(rules={"conditions": [{"metric": "plddt", "value": 70}]}))[0]
    assert not decision["passed"] and decision["needs_attention"]
    assert decision["reasons"][0].startswith("scale_conflict:")


@pytest.mark.parametrize("metadata", [[], "bad", {"confidence_scales": []}, {"confidence_scales": None}, {"confidence_scales": {"plddt": None}}])
def test_parser_invalid_explicit_metadata_cannot_silently_fall_back_to_provider(metadata):
    body = b"run_id,cycle,pdb_filename,iptm,plddt\n1,1,design.pdb,0.8,0.9\n"
    parsed = get_parser("proteinhunter_boltz")(ParseContext(
        job_id=uuid.uuid4(), project_id=uuid.uuid4(), attempt_number=1,
        outputs=[{"filename": "summary_high_iptm.csv", "object_key": "summary", "metadata": metadata}],
        parameters={}, read_bytes=lambda key: body,
    ))
    metric = next(m for m in parsed.candidates[0].metrics if m.key == "plddt")
    assert metric.value == 0.9 and metric.context["scale_status"] == "scale_conflict"


def test_conflicting_file_and_column_declarations_preserve_both_and_block():
    candidate = parse_csv("1,1,design.pdb,0.85,0.9,0.8,percent_0_100,\n", metadata={"confidence_scales": {"plddt": scales.FRACTION}}).candidates[0]
    context = candidate.properties["confidence_scale"]["plddt"]
    assert context["row_declared_scale"] == scales.PERCENT
    assert context["metadata_declared_scale"] == scales.FRACTION
    assert context["scale_status"] == "scale_conflict"
    assert candidate.scores["plddt"] == 0.9


# The ordinary workflow fixture uses disposable in-memory persistence; this checks
# the actual capture boundary, including raw metadata vs normalized parser values.

env = _binding_env


@pytest.mark.parametrize("mode", ["normalized", "invalid_metadata", "raw_conflict"])
def test_capture_persists_stored_scale_without_confusing_raw_file_metadata(env, mode):
    from backend_v2.app.artifacts.models import Artifact
    from backend_v2.app.workflows.gate_runtime import capture_results
    from backend_v2.app.workflows.models import WorkflowResult
    from backend_v2.tests.test_workflow_gates import runtime_fixture
    from sqlalchemy import select

    session, _workflow, _submission, source, _target, _gate, storage = runtime_fixture(env)
    parsed = parse_csv("1,1,design.pdb,0.85,0.94,0.88,,\n")
    candidate = parsed.candidates[0]
    from dataclasses import replace
    candidate = replace(candidate, complex_output_index=0)
    if mode != "normalized":
        candidate = replace(candidate, metrics=[], scores={"plddt": 85}, properties={"predicted_by": "alphafold3"})
    parsed = replace(parsed, candidates=[candidate])
    artifact = Artifact(project_id=env["project"].id, created_by=env["user"].id,
                        artifact_type="predicted_structure", filename="design.pdb", object_key="confidence.pdb",
                        checksum_sha256="a" * 64, size_bytes=5, content_type="text/plain",
                        lineage={"output_port": "structure", "metadata": {"confidence_scales": [] if mode == "invalid_metadata" else {"plddt": scales.FRACTION}}})
    session.add(artifact)
    session.flush()
    storage.files["confidence.pdb"] = b"ATOM\n"
    capture_results(session, source, [artifact], parsed, storage)
    session.flush()
    saved = session.scalar(select(WorkflowResult).where(WorkflowResult.job_id == source.id, WorkflowResult.result_key == candidate.candidate_key))
    assert saved is not None
    if mode == "normalized":
        assert saved.payload["reported_confidence_scales"]["plddt"] == scales.FRACTION
        metric = next(m for m in saved.payload["metric_sources"] if m["key"] == "plddt")
        assert metric["context"]["reported_value"] == 0.94 and metric["unit"] == "pLDDT_0_100"
    decision = gate_evaluate([{"id": str(saved.id), **saved.payload}], GatePolicy(rules={"conditions": [{"metric": "plddt", "value": 70}]}))[0]
    assert decision["passed"] == (mode == "normalized")
    if mode != "normalized":
        assert decision["needs_attention"]
        assert any(reason.startswith("scale_conflict:") for reason in decision["reasons"])
