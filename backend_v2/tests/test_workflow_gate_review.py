"""Regression cases discovered during the six-aspect workflow review. Synthetic data only."""

from __future__ import annotations

import hashlib
import uuid

import pytest
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.compute.parsers.base import ParsedOutputs
from backend_v2.app.workflows.gate_runtime import capture_results, ensure_gate, run_gate
from backend_v2.app.workflows.gate_schemas import GateRelease
from backend_v2.app.workflows.gate_service import release_gate, retry_gate
from backend_v2.app.workflows.models import GateEvaluation, WorkflowResult
from backend_v2.tests.test_compute_binding import env as env
from backend_v2.tests.test_workflow_gates import runtime_fixture
from sqlalchemy import delete, select


def test_bundle_metadata_cannot_collapse_individual_sequence_identity(env):
    s, _, _, source, _, gate, storage = runtime_fixture(env)
    s.execute(delete(WorkflowResult).where(WorkflowResult.job_id == source.id))
    fasta = s.scalar(select(Artifact).where(Artifact.object_key == "design.fasta"))
    fasta.lineage = {**fasta.lineage, "metadata": {"candidate_key": "bundle-parent"}}
    scores = s.scalar(select(Artifact).where(Artifact.object_key == "scores.csv"))
    capture_results(s, source, [fasta, scores], ParsedOutputs(), storage)
    rows = list(s.scalars(select(WorkflowResult).where(WorkflowResult.job_id == source.id)))
    assert {r.result_key for r in rows} == {"keep", "drop"}
    run_gate(s, gate, storage)
    subset = s.get(Artifact, uuid.UUID(gate.inputs[0]["artifact_id"]))
    assert storage.files[subset.object_key] == b">keep\nAAAA\n"


def test_integrity_gate_accepts_reference_json_and_checks_actual_bytes(env):
    s, _, _, source, _, gate, storage = runtime_fixture(env)
    artifact = s.scalar(select(Artifact).where(Artifact.object_key == "design.fasta"))
    data = b'{"reference": 42}'
    artifact.filename = "reference.json"
    artifact.size_bytes = len(data)
    artifact.checksum_sha256 = hashlib.sha256(data).hexdigest()
    storage.files[artifact.object_key] = data
    s.execute(delete(WorkflowResult).where(WorkflowResult.job_id == source.id))
    capture_results(s, source, [artifact], ParsedOutputs(), storage)
    gate.snapshot = {
        **gate.snapshot,
        "edge": {**gate.snapshot["edge"], "gate": {"mode": "integrity", "configured": True}},
        "output_policy": {"structure": {"chains": ["B"]}},
    }
    run_gate(s, gate, storage)
    assert gate.status == "released" and gate.inputs[0]["artifact_id"] == str(artifact.id)
    gate.status = "waiting"
    storage.files[artifact.object_key] = b"corrupt"
    with pytest.raises(ValueError, match="gate_source_integrity_failed"):
        run_gate(s, gate, storage)


def test_formal_gate_does_not_collide_with_existing_preview_revision(env):
    s, _, _, source, target, original, _ = runtime_fixture(env)
    original.preview = True
    s.flush()
    gate = ensure_gate(s, target, source, original.snapshot["edge"])
    s.flush()
    assert not gate.preview and gate.revision > original.revision
    assert ensure_gate(s, target, source, original.snapshot["edge"]).id == gate.id


def test_manual_materialization_retry_preserves_selection(env):
    s, w, _, _, _, gate, storage = runtime_fixture(env, "review")
    before = gate.version
    run_gate(s, gate, storage)
    assert gate.status == "awaiting_review" and gate.version > before
    chosen = [d["id"] for d in gate.decisions if d["passed"]]
    release_gate(w.id, gate.id, GateRelease(version=gate.version, selected_ids=chosen), s, env["user"])
    gate.status, gate.error_message = "error", "transient storage error"
    result = retry_gate(w.id, gate.id, s, env["user"])
    retried = s.get(GateEvaluation, uuid.UUID(result["id"]))
    assert retried.status == "materializing" and retried.selected_ids == chosen
    assert retried.released_by == env["user"].id
    run_gate(s, retried, storage)
    assert retried.status == "released" and retried.selected_ids == chosen


def test_no_coordinates_is_actionable_data_error_not_empty_success(env):
    s, _, _, _, _, gate, storage = runtime_fixture(env)
    gate.snapshot = {
        **gate.snapshot,
        "edge": {**gate.snapshot["edge"], "gate": {"configured": True, "structure": {"chains": ["B"]}}},
    }
    run_gate(s, gate, storage)
    assert gate.status == "error" and gate.error_message == "structure_data_needs_attention"
    assert gate.decisions and all(d["needs_attention"] for d in gate.decisions)
    assert not gate.selected_ids


def test_skipped_parent_does_not_hide_another_valid_source_on_same_port(env):
    from types import SimpleNamespace

    from backend_v2.app.compute.service import schedule_ready_jobs

    s, w, submission, source, target, gate, storage = runtime_fixture(env)
    run_gate(s, gate, storage)
    # A skipped branch has no candidate input. The other branch still supplies the port.
    from backend_v2.app.workflows.gate_runtime import gate_inputs

    target.runtime_spec = {
        **target.runtime_spec,
        "workflow_edges": [
            *target.runtime_spec["workflow_edges"],
            {
                "id": "empty-b",
                "source": "empty",
                "target": "b",
                "target_port": "sequences",
                "gate": {"configured": True},
            },
        ],
    }
    assert gate_inputs(s, target, {"a"}, {"a": source, "empty": SimpleNamespace(status="skipped")}) == "ready"
    assert target.runtime_spec["gate_selected_counts"]["empty"] == 0
    # Re-entry must not append the same filtered input twice.
    assert gate_inputs(s, target, {"a"}, {"a": source}) == "ready"
    assert len(target.runtime_spec["input_manifest"]["inputs"]) == 1
    schedule_ready_jobs(s, submission, w)
    assert target.status == "pending"


def test_invalid_configuration_and_cycles_are_client_errors(env):
    from backend_v2.app.core.problem import DomainError
    from backend_v2.app.workflows.assistance import validate_configuration
    from backend_v2.app.workflows.connections import replace_connections

    for configuration in [{"parameter_links": {"count": "broken"}}, {"output_policy": {"structure": {"chains": [""]}}}]:
        with pytest.raises(DomainError) as error:
            validate_configuration(configuration)
        assert error.value.status_code == 422
    s, w, _, _, _, _, _ = runtime_fixture(env)
    w.status = "draft"
    with pytest.raises(DomainError) as error:
        replace_connections(
            s, w, [*w.graph["edges"], {"source": "b", "target": "a", "gate": {"mode": "dependency"}}], w.version
        )
    assert error.value.status_code == 422


def test_real_scheduler_merge_continues_with_one_skipped_source(env):
    from backend_v2.app.compute.models import Job
    from backend_v2.app.compute.repository import ComputeRepository
    from backend_v2.app.compute.service import schedule_ready_jobs
    from backend_v2.tests.test_compute_binding import _node

    s, w, submission, source, target, gate, storage = runtime_fixture(env)
    run_gate(s, gate, storage)
    node = _node(w, "empty", env["producer"], [])
    s.add(node)
    s.flush()
    skipped = Job(
        submission_id=submission.id,
        workflow_run_id=w.id,
        workflow_node_id=node.id,
        project_id=w.project_id,
        compute_backend="demo",
        model_plugin="synthetic",
        status="skipped",
        runtime_spec={"node_key": "empty"},
    )
    s.add(skipped)
    edges = [
        *source.runtime_spec["workflow_edges"],
        {"id": "empty-b", "source": "empty", "target": "b", "target_port": "sequences", "gate": {"configured": True}},
    ]
    for job in [source, target, skipped]:
        job.runtime_spec = {**job.runtime_spec, "workflow_edges": edges}
    s.flush()
    schedule_ready_jobs(s, submission, w)
    assert target.status == "pending"
    assert ComputeRepository(s).has_outbox_event("job.dispatch", target.id)
    assert target.runtime_spec["gate_selected_counts"]["empty"] == 0


def test_binding_edit_keeps_node_changes_and_gate_configuration(env):
    from backend_v2.app.workflows.api import patch_workflow_node
    from backend_v2.app.workflows.gate_schemas import GatePolicy
    from backend_v2.app.workflows.models import WorkflowNode
    from backend_v2.app.workflows.schemas import WorkflowNodeUpdate
    from fastapi import Response

    s, w, _, _, target, _, _ = runtime_fixture(env)
    w.status = "draft"
    node = s.get(WorkflowNode, target.workflow_node_id)
    updated = patch_workflow_node(
        w.id,
        node.id,
        WorkflowNodeUpdate(parameters={"count": 12}, input_bindings=node.input_bindings),
        Response(),
        f'W/"{w.version}"',
        s,
        env["user"],
    )
    s.flush()
    s.expire_all()
    assert updated.parameters == {"count": 12}
    assert node.parameters == {"count": 12}
    assert w.graph["edges"][0]["id"] == "ab"
    assert GatePolicy.model_validate(w.graph["edges"][0]["gate"]).configured


def test_dssp_insertion_codes_do_not_split_a_contiguous_helix():
    from backend_v2.app.workflows.gate_schemas import StructurePolicy
    from backend_v2.app.workflows.structure_metrics import count_helices

    assignments = [("B", (10, " "), "H"), ("B", (10, "A"), "H"), ("B", (10, "B"), "H"), ("B", (11, " "), "H")]
    assert count_helices(assignments, StructurePolicy(chains=["B"])) == 1


def test_static_import_observes_commands_and_files_without_executing(tmp_path):
    from backend_v2.app.workflows.assistance import parse_script
    from backend_v2.app.workflows.gate_schemas import ScriptImport

    destination = str(tmp_path / "not-created")
    source = f'import subprocess\nCOUNT = 4\nsubprocess.run(["tool", "--input", "source.fa"])\nopen("source.fa", "r")\nopen({destination!r}, "w")\n'
    parsed = parse_script(ScriptImport(filename="node.py", language="python", source=source))
    assert parsed["parameters"]["COUNT"] == 4
    assert parsed["commands"] == ["tool --input source.fa"]
    assert parsed["inputs"] == ["source.fa"] and parsed["outputs"] == [destination]
    assert not (tmp_path / "not-created").exists()
    shell = parse_script(
        ScriptImport(
            filename="node.sh", language="shell", source="COUNT=4\ntool --input source.fa --output filtered.fa\n"
        )
    )
    assert shell["parameters"]["COUNT"] == 4
    assert shell["inputs"] == ["source.fa"] and shell["outputs"] == ["filtered.fa"]


def test_nonfinite_measurements_remain_missing_in_postgres_json():
    import json

    from backend_v2.app.workflows.gate_engine import evaluate
    from backend_v2.app.workflows.gate_runtime import json_safe
    from backend_v2.app.workflows.gate_schemas import GatePolicy

    record = json_safe({"id": "bad", "metrics": {"score": float("nan")}, "metric_sources": [{"value": float("inf")}]})
    json.dumps(record, allow_nan=False)
    assert record["metrics"]["score"] is None
    policy = GatePolicy(rules={"sort_metric": "score", "top_n": 1})
    assert not evaluate([record], policy)[0]["passed"]
    assert not evaluate([{"id": "bool", "metrics": {"score": True}}], policy)[0]["passed"]


def test_repair_preserves_an_independent_configured_gate(env):
    from backend_v2.app.workflows.models import WorkflowRun
    from backend_v2.app.workflows.repair import inspect_repair
    from backend_v2.tests.test_compute_binding import _node

    s = env["session"]
    w = WorkflowRun(
        project_id=env["project"].id,
        name="independent policies",
        created_by=env["user"].id,
        graph={
            "nodes": [{"key": k} for k in ["a", "b", "c"]],
            "edges": [
                {"id": "ab", "source": "a", "target": "b"},
                {"id": "ac", "source": "a", "target": "c", "gate": {"configured": True, "mode": "manual"}},
            ],
        },
    )
    s.add(w)
    s.flush()
    s.add_all(
        [_node(w, "a", env["producer"], []), _node(w, "b", env["consumer"], []), _node(w, "c", env["consumer"], [])]
    )
    s.flush()
    report = inspect_repair(s, w)
    assert not report["edges"][0]["gate"]["configured"]
    assert report["edges"][1]["gate"]["configured"]


def test_metric_variants_do_not_leave_an_ambiguous_summary_alias(env):
    from backend_v2.app.compute.parsers.base import ParsedCandidate, ParsedMetric

    s, _, _, source, _, _, storage = runtime_fixture(env)
    s.execute(delete(WorkflowResult).where(WorkflowResult.job_id == source.id))
    fasta = s.scalar(select(Artifact).where(Artifact.object_key == "design.fasta"))
    parsed = ParsedOutputs(
        candidates=[
            ParsedCandidate(
                candidate_key="keep",
                scores={"confidence": 99},
                metrics=[
                    ParsedMetric(key="confidence", value=99, method="predict", model_variant="v1"),
                    ParsedMetric(key="confidence", value=30, method="predict", model_variant="v2"),
                ],
            )
        ]
    )
    capture_results(s, source, [fasta], parsed, storage)
    row = s.scalar(
        select(WorkflowResult).where(WorkflowResult.job_id == source.id, WorkflowResult.result_key == "keep")
    )
    assert "confidence" not in row.payload["metrics"]
    assert row.payload["metrics"]["confidence:predict:v1:"] == 99
    assert row.payload["metrics"]["confidence:predict:v2:"] == 30


def test_skipped_execution_dependency_stops_its_downstream(env):
    from backend_v2.app.compute.repository import ComputeRepository
    from backend_v2.app.compute.service import schedule_ready_jobs

    s, w, submission, source, target, _, _ = runtime_fixture(env)
    edges = [{"id": "order", "source": "a", "target": "b", "gate": {"mode": "dependency", "configured": True}}]
    source.status = "skipped"
    for job in [source, target]:
        job.runtime_spec = {**job.runtime_spec, "workflow_edges": edges}
    schedule_ready_jobs(s, submission, w)
    assert target.status == "skipped" and target.error_code == "no_qualified_inputs"
    assert "execution dependency" in target.error_message
    assert not ComputeRepository(s).has_outbox_event("job.dispatch", target.id)


def test_filtered_count_is_validated_before_any_compute_dispatch(env):
    from backend_v2.app.compute.repository import ComputeRepository
    from backend_v2.app.compute.service import schedule_ready_jobs

    s, w, submission, _, target, gate, storage = runtime_fixture(env)
    run_gate(s, gate, storage)
    target.runtime_spec = {
        **target.runtime_spec,
        "configuration": {"parameter_links": {"count": {"source": "selected_count", "from_node": "a"}}},
        "plugin_snapshot": {
            **target.runtime_spec["plugin_snapshot"],
            "parameter_schema": {"type": "object", "properties": {"count": {"type": "integer", "minimum": 2}}},
        },
    }
    schedule_ready_jobs(s, submission, w)
    assert target.status == "failed" and target.error_code == "runtime_parameters_invalid"
    assert "minimum" in target.error_message
    assert not ComputeRepository(s).has_outbox_event("job.dispatch", target.id)
