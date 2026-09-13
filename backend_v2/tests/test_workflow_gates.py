from __future__ import annotations

import io
import uuid
import zipfile
from types import SimpleNamespace

import pytest
from backend_v2.app.workflows.assistance import parse_script
from backend_v2.app.workflows.gate_engine import evaluate, records_in_file, subset_file
from backend_v2.app.workflows.gate_schemas import GatePolicy, ScriptImport, StructurePolicy
from backend_v2.app.workflows.structure_metrics import count_helices
from backend_v2.tests.test_compute_binding import BACKBONE_OUT, _node
from backend_v2.tests.test_compute_binding import env as _binding_env

env = _binding_env


def test_rules_missing_metric_or_and_stable_top_n():
    rows = [
        {"id": "c", "metrics": {"confidence": 90}},
        {"id": "b", "metrics": {"confidence": 90}},
        {"id": "a", "metrics": {}},
    ]
    policy = GatePolicy(
        configured=True,
        rules={
            "operator": "or",
            "conditions": [{"metric": "confidence", "op": "gte", "value": 80}],
            "sort_metric": "confidence",
            "top_n": 1,
        },
    )
    decisions = evaluate(rows, policy)
    assert [d["id"] for d in decisions if d["passed"]] == ["b"]
    assert decisions[0]["reasons"][0] == "missing_metric:confidence"
    assert decisions[-1]["reasons"] == ["outside_top_n"]


def test_fasta_subset_does_not_pass_rejected_sequence():
    data = b">keep description\nAAAA\n>drop\nCCCC\n>keep2\nDDDD\n"
    records = records_in_file("sequences.fasta", data)
    result = subset_file("sequences.fasta", data, [records[0], records[2]])
    assert result == b">keep description\nAAAA\n>keep2\nDDDD\n"
    assert b"CCCC" not in result


@pytest.mark.parametrize(
    "name,data",
    [
        ("scores.csv", b"id,score\na,1\nb,2\n"),
        ("scores.tsv", b"id\tscore\na\t1\nb\t2\n"),
        ("scores.jsonl", b'{"id":"a","score":1}\n{"id":"b","score":2}\n'),
    ],
)
def test_tabular_subset(name, data):
    rows = records_in_file(name, data)
    subset = subset_file(name, data, [rows[1]])
    assert [r["key"] for r in records_in_file(name, subset)] == ["b"]


def test_archive_subset_filters_inside_member():
    source = io.BytesIO()
    with zipfile.ZipFile(source, "w") as z:
        z.writestr("seqs.fasta", ">a\nAAA\n>b\nCCC\n")
        z.writestr("extra.pdb", "ATOM\n")
    rows = records_in_file("bundle.zip", source.getvalue())
    subset = subset_file("bundle.zip", source.getvalue(), [rows[1]])
    with zipfile.ZipFile(io.BytesIO(subset)) as z:
        assert z.namelist() == ["seqs.fasta"]
        assert z.read("seqs.fasta") == b">b\nCCC\n"


def test_ambiguous_records_fail_closed():
    with pytest.raises(ValueError, match="duplicate"):
        records_in_file("seq.fasta", b">a\nAAA\n>a\nCCC\n")
    with pytest.raises(ValueError, match="id_missing"):
        records_in_file("scores.csv", b"score\n2\n")
    with pytest.raises(ValueError, match="selected_result_missing"):
        subset_file("seq.fasta", b">a\nAAA\n", [{"key": "b"}])


@pytest.mark.parametrize(
    "assignments,expected",
    [
        ([], 0),
        ([("B", i, "H") for i in range(1, 5)], 1),
        ([("B", i, "H" if i != 5 else "-") for i in range(1, 10)], 2),
        ([("A", i, "H") for i in range(1, 15)], 0),
        ([("B", i, "E") for i in range(1, 15)], 0),
    ],
)
def test_design_chain_helices(assignments, expected):
    assert count_helices(assignments, StructurePolicy(chains=["B"])) == expected


def test_static_script_import_never_executes(tmp_path):
    destination = tmp_path / "must-not-exist"
    source = f"temperature = 0.1\nopen({str(destination)!r}, 'w').write('oops')\n"
    result = parse_script(ScriptImport(filename="node.py", language="python", source=source))
    assert result["parameters"] == {"temperature": 0.1}
    assert not destination.exists()
    shell = parse_script(ScriptImport(filename="node.sh", language="shell", source="count=10\nvalue=$(touch x)\n"))
    assert shell["parameters"] == {"count": 10}
    assert "Dynamic assignment" in shell["warnings"][0]


def test_connections_update_graph_and_binding_and_reject_cycle(env):
    from backend_v2.app.core.problem import DomainError
    from backend_v2.app.workflows.connections import replace_connections
    from backend_v2.app.workflows.models import WorkflowRun

    s = env["session"]
    w = WorkflowRun(
        project_id=env["project"].id,
        name="gate",
        created_by=env["user"].id,
        graph={"nodes": [{"key": "a"}, {"key": "b"}], "edges": []},
    )
    s.add(w)
    s.flush()
    a, b = _node(w, "a", env["producer"], []), _node(w, "b", env["consumer"], [])
    s.add_all([a, b])
    s.flush()
    edge = {"id": "ab", "source": str(a.id), "target": str(b.id), "gate": {"mode": "manual", "configured": True}}
    result = replace_connections(s, w, [edge], w.version)
    assert result[0]["source_port"] == "backbones"
    assert b.input_bindings == [{"source": "upstream", "port": "backbone", "from_node": "a", "from_port": "backbones"}]
    from pydantic import ValidationError

    with pytest.raises((ValidationError, DomainError)):
        replace_connections(
            s, w, [*result, {"id": "ba", "source": "b", "target": "a", "gate": {"mode": "dependency"}}], w.version
        )
    replace_connections(s, w, [], w.version)
    assert b.input_bindings == []


def test_ordering_connection_between_incompatible_stages(env):
    """Two stages that share no compatible port can still be sequenced.

    This is what the canvas now offers when a drag finds no port pair: the alternative
    was a dialog that said "no compatible ports" and left the user with no way to state
    "run this after that", even though the server has always accepted a dependency.
    """
    from backend_v2.app.core.problem import DomainError
    from backend_v2.app.workflows.connections import replace_connections
    from backend_v2.app.workflows.models import WorkflowRun

    s = env["session"]
    w = WorkflowRun(
        project_id=env["project"].id,
        name="ordering",
        created_by=env["user"].id,
        graph={"nodes": [{"key": "a"}, {"key": "b"}], "edges": []},
    )
    s.add(w)
    s.flush()
    # Both on the consumer plugin: it emits protein_sequence and accepts only
    # protein_structure, so a to b has no compatible pair in either direction.
    a, b = _node(w, "a", env["consumer"], []), _node(w, "b", env["consumer"], [])
    s.add_all([a, b])
    s.flush()

    with pytest.raises(DomainError) as refused:
        replace_connections(s, w, [{"id": "ab", "source": "a", "target": "b"}], w.version)
    assert refused.value.error_code == "connection_ports_ambiguous"

    result = replace_connections(
        s, w, [{"id": "ab", "source": "a", "target": "b", "gate": {"mode": "dependency"}}], w.version
    )
    assert result[0]["source_port"] is None and result[0]["target_port"] is None
    assert result[0]["gate"]["configured"] is True
    # Ordering stages nothing, so it must not manufacture an input binding.
    assert b.input_bindings == []

    # It is still a real graph edge, so the cycle check applies to it.
    with pytest.raises(DomainError):
        replace_connections(
            s,
            w,
            [*result, {"id": "ba", "source": "b", "target": "a", "gate": {"mode": "dependency"}}],
            w.version,
        )


def test_layout_cannot_rewire_execution(env):
    from backend_v2.app.workflows.models import WorkflowRun
    from backend_v2.app.workflows.schemas import WorkflowLayoutUpdate
    from backend_v2.app.workflows.service import update_layout

    w = WorkflowRun(version=1, graph={"edges": [{"source": "a", "target": "b"}]})
    update_layout(w, WorkflowLayoutUpdate(nodes=[], edges=[{"source": "b", "target": "a"}]), 1)
    assert w.graph["edges"] == [{"source": "a", "target": "b"}]


def test_repair_draft_repeatable_and_rollback(env):
    from backend_v2.app.workflows.models import WorkflowRun
    from backend_v2.app.workflows.repair import apply_repair, rollback_repair

    s = env["session"]
    original = {"nodes": [{"key": "a"}, {"key": "b"}], "edges": [{"source": "a", "target": "b"}]}
    w = WorkflowRun(project_id=env["project"].id, name="legacy", created_by=env["user"].id, graph=original)
    s.add(w)
    s.flush()
    s.add_all([_node(w, "a", env["producer"], []), _node(w, "b", env["consumer"], [])])
    s.flush()
    result = apply_repair(s, w, "batch", env["user"], env["project"])
    assert result["issues"]
    assert apply_repair(s, w, "batch", env["user"], env["project"])["action"] == "already_repaired"
    assert rollback_repair(s, w, "batch")
    assert w.graph == original


class MemoryStorage:
    def __init__(self):
        self.files = {}

    def read_bytes(self, key, **kwargs):
        return self.files[key]

    def put_bytes(self, key, body, content_type):
        self.files[key] = body


def runtime_fixture(env, mode="automatic", threshold=80, optional=False):
    from backend_v2.app.artifacts.models import Artifact
    from backend_v2.app.compute.models import JobEvent
    from backend_v2.app.compute.parsers.base import ParsedOutputs
    from backend_v2.app.compute.schemas import SubmissionCreate
    from backend_v2.app.compute.service import create_submission, schedule_ready_jobs
    from backend_v2.app.workflows.gate_runtime import capture_results, latest_gate
    from backend_v2.app.workflows.models import WorkflowRun

    s = env["session"]
    producer, consumer = env["producer"], env["consumer"]
    producer.output_ports = [{"name": "sequences", "kind": "protein_sequence", "artifact_type": "sequence_set"}]
    consumer.input_ports = [
        {"name": "sequences", "kind": "protein_sequence", "accepts": ["sequence_set"], "required": not optional}
    ]
    w = WorkflowRun(
        project_id=env["project"].id,
        name="screen",
        created_by=env["user"].id,
        graph={
            "nodes": [{"key": "a"}, {"key": "b"}],
            "edges": [
                {
                    "id": "ab",
                    "source": "a",
                    "target": "b",
                    "source_port": "sequences",
                    "target_port": "sequences",
                    "gate": {
                        "mode": mode,
                        "configured": True,
                        "rules": {"conditions": [{"metric": "score", "op": "gte", "value": threshold}]},
                    },
                }
            ],
        },
    )
    s.add(w)
    s.flush()
    s.add_all(
        [
            _node(w, "a", producer, []),
            _node(
                w,
                "b",
                consumer,
                [{"port": "sequences", "source": "upstream", "from_node": "a", "from_port": "sequences"}],
            ),
        ]
    )
    s.flush()
    submission, jobs = create_submission(
        s,
        workflow=w,
        project=env["project"],
        payload=SubmissionCreate(compute_backend="demo"),
        idempotency_key="test-gate",
        user=env["user"],
    )
    source = next(j for j in jobs if j.runtime_spec["node_key"] == "a")
    target = next(j for j in jobs if j.runtime_spec["node_key"] == "b")
    storage = MemoryStorage()
    artifacts = []
    for filename, data, port in [
        ("design.fasta", b">keep\nAAAA\n>drop\nCCCC\n", "sequences"),
        ("scores.csv", b"id,score\nkeep,90\ndrop,40\n", "scores"),
    ]:
        a = Artifact(
            project_id=w.project_id,
            created_by=env["user"].id,
            artifact_type="sequence_set" if port == "sequences" else "score_table",
            filename=filename,
            object_key=filename,
            checksum_sha256=__import__("hashlib").sha256(data).hexdigest(),
            size_bytes=len(data),
            content_type="text/plain",
            lineage={"job_id": str(source.id), "output_port": port},
        )
        s.add(a)
        s.flush()
        artifacts.append(a)
        storage.files[filename] = data
    capture_results(s, source, artifacts, ParsedOutputs(), storage)
    source.status = "succeeded"
    s.add(
        JobEvent(job_id=source.id, event_type="job.succeeded", payload={"artifact_ids": [str(a.id) for a in artifacts]})
    )
    s.flush()
    schedule_ready_jobs(s, submission, w)
    return s, w, submission, source, target, latest_gate(s, target.id, "ab"), storage


@pytest.mark.parametrize("mode", ["automatic", "manual", "review"])
def test_runtime_only_releases_selected_bytes_once(env, mode):
    import uuid

    from backend_v2.app.artifacts.models import Artifact
    from backend_v2.app.compute.repository import ComputeRepository
    from backend_v2.app.compute.service import schedule_ready_jobs
    from backend_v2.app.workflows.api import release_gate
    from backend_v2.app.workflows.gate_runtime import run_gate
    from backend_v2.app.workflows.gate_schemas import GateRelease

    s, w, submission, source, target, gate, storage = runtime_fixture(env, mode)
    assert target.timeout_at is None
    assert not ComputeRepository(s).has_outbox_event("job.dispatch", target.id)
    run_gate(s, gate, storage)
    if mode != "automatic":
        assert gate.status == "awaiting_review"
        keep = [d["id"] for d in gate.decisions if d["passed"]]
        release_gate(w.id, gate.id, GateRelease(version=gate.version, selected_ids=keep), s, env["user"])
        # Double clicks do not enqueue a second decision or change the version.
        version = gate.version
        release_gate(w.id, gate.id, GateRelease(version=version - 1, selected_ids=keep), s, env["user"])
        assert gate.version == version
        run_gate(s, gate, storage)
    assert gate.status == "released"
    schedule_ready_jobs(s, submission, w)
    schedule_ready_jobs(s, submission, w)
    inputs = target.runtime_spec["input_manifest"]["inputs"]
    assert len(inputs) == 1
    artifact = s.get(Artifact, uuid.UUID(inputs[0]["artifact_id"]))
    assert storage.files[artifact.object_key] == b">keep\nAAAA\n"
    assert storage.files["design.fasta"] == b">keep\nAAAA\n>drop\nCCCC\n"
    assert target.timeout_at is not None
    assert ComputeRepository(s).has_outbox_event("job.dispatch", target.id)


@pytest.mark.parametrize("optional", [False, True])
def test_empty_gate_skips_only_when_required(env, optional):
    from backend_v2.app.compute.repository import ComputeRepository
    from backend_v2.app.compute.service import schedule_ready_jobs
    from backend_v2.app.workflows.gate_runtime import run_gate

    s, w, submission, source, target, gate, storage = runtime_fixture(env, threshold=100, optional=optional)
    run_gate(s, gate, storage)
    assert gate.status == "empty"
    schedule_ready_jobs(s, submission, w)
    assert (target.status == "skipped") is not optional
    assert ComputeRepository(s).has_outbox_event("job.dispatch", target.id) is optional
    if not optional:
        assert w.status == "succeeded"


def test_gate_rejects_stale_or_unqualified_manual_selection(env):
    from backend_v2.app.core.problem import DomainError
    from backend_v2.app.workflows.api import release_gate
    from backend_v2.app.workflows.gate_runtime import run_gate
    from backend_v2.app.workflows.gate_schemas import GateRelease

    s, w, _, _, _, gate, storage = runtime_fixture(env, "review")
    run_gate(s, gate, storage)
    with pytest.raises(DomainError, match="stale"):
        release_gate(w.id, gate.id, GateRelease(version=0, selected_ids=[]), s, env["user"])
    drop = [d["id"] for d in gate.decisions if not d["passed"]]
    with pytest.raises(DomainError, match="qualified"):
        release_gate(w.id, gate.id, GateRelease(version=gate.version, selected_ids=drop), s, env["user"])


def test_proteinmpnn_native_and_sample_ids():
    data = b">native, score=2\nNNNN\n>T=0.1, sample=1, score=0.9\nAAAA\n>T=0.1, sample=2, score=1.1\nCCCC\n"
    rows = records_in_file("binder.fa", data)
    assert rows[0]["native"]
    assert rows[1]["key"] == "binder_sample1"
    filtered = subset_file("binder.fa", data, [rows[1]])
    assert b"AAAA" in filtered and b"NNNN" not in filtered and b"CCCC" not in filtered


@pytest.mark.parametrize(
    "language,filename,source",
    [("python", "node.py", "count = 5\nprint(count)\n"), ("shell", "node.sh", 'count=5\nprintf "%s" "$count"\n')],
)
def test_imported_script_uses_reviewed_parameters(language, filename, source):
    import subprocess
    from types import SimpleNamespace

    from backend_v2.app.workflows.assistance import node_command

    imported = parse_script(ScriptImport(language=language, filename=filename, source=source))
    node = SimpleNamespace(configuration={"script": imported}, parameters={"count": 17}, command=None)
    script = node_command(node, None)
    assert subprocess.check_output(["bash", "-c", script], text=True).strip() == "17"
    assert imported["source"] == source


def test_draft_preview_never_dispatches_and_is_bound_to_script_revision(env, monkeypatch):
    from backend_v2.app.compute.repository import ComputeRepository
    from backend_v2.app.workflows.gate_runtime import run_gate
    from backend_v2.app.workflows.gate_schemas import GatePreview
    from backend_v2.app.workflows.gate_service import preview_gate, script_preview_valid
    from backend_v2.app.workflows.models import GateEvaluation, WorkflowRun

    s, w, _, source, target, _, storage = runtime_fixture(env)
    draft = WorkflowRun(project_id=w.project_id, name="draft", graph=w.graph, created_by=env["user"].id)
    s.add(draft)
    s.flush()
    from backend_v2.app.workflows.models import WorkflowNode

    original_node = s.get(WorkflowNode, source.workflow_node_id)
    s.add(_node(draft, "a", env["producer"], []))
    draft_node = s.query(WorkflowNode).filter_by(workflow_run_id=draft.id).one()
    draft_node.model_plugin_id = original_node.model_plugin_id
    s.flush()
    code = 'def screen(records): return [{"id": r["id"], "passed": True, "reason": "ok"} for r in records]'
    policy = GatePolicy(configured=True, script=code)
    row = preview_gate(draft.id, "ab", GatePreview(policy=policy, source_job_id=source.id), s, env["user"])
    import uuid

    evaluation = s.get(GateEvaluation, uuid.UUID(row["id"]))
    assert evaluation.preview and evaluation.target_job_id is None
    monkeypatch.setattr(
        "backend_v2.app.workflows.gate_runtime._script_decisions",
        lambda script, records: [{"id": r["id"], "passed": True} for r in records],
    )
    run_gate(s, evaluation, storage)
    assert evaluation.status == "previewed"
    assert not ComputeRepository(s).has_outbox_event("job.dispatch", target.id)
    edge = {"id": "ab", "gate": {**policy.model_dump(mode="json"), "script_preview_id": str(evaluation.id)}}
    assert script_preview_valid(s, draft, edge, None)
    edge["gate"]["script"] += "\n# changed"
    assert not script_preview_valid(s, draft, edge, None)


def test_inherited_standard_precedes_branch_top_n(env):
    from backend_v2.app.workflows.gate_runtime import run_gate

    s, w, _, source, target, gate, storage = runtime_fixture(env, threshold=0)
    gate.snapshot = {
        **gate.snapshot,
        "output_policy": {"configured": True, "rules": {"conditions": [{"metric": "score", "op": "gte", "value": 80}]}},
        "edge": {
            **gate.snapshot["edge"],
            "gate": {"configured": True, "rules": {"sort_metric": "score", "descending": False, "top_n": 1}},
        },
    }
    run_gate(s, gate, storage)
    assert len(gate.selected_ids) == 1
    assert next(d for d in gate.decisions if d["passed"])["metrics"]["score"] == 90


def test_gate_script_failure_is_not_empty_result(env, monkeypatch):
    from backend_v2.app.workflows.gate_runtime import run_gate

    _, _, _, _, _, gate, storage = runtime_fixture(env)
    gate.snapshot = {
        **gate.snapshot,
        "edge": {**gate.snapshot["edge"], "gate": {"configured": True, "script": "raise RuntimeError('broken')"}},
    }

    def broken(*args):
        raise ValueError("gate_script_failed")

    monkeypatch.setattr("backend_v2.app.workflows.gate_runtime._script_decisions", broken)
    with pytest.raises(ValueError, match="gate_script_failed"):
        run_gate(env["session"], gate, storage)
    assert gate.status != "empty"


def test_historical_workflow_repair_derives_once(env):
    from backend_v2.app.workflows.models import WorkflowRun
    from backend_v2.app.workflows.repair import apply_repair

    s, w, _, _, _, _, _ = runtime_fixture(env)
    original_graph, original_status = w.graph, w.status
    first = apply_repair(s, w, "batch", env["user"], env["project"])
    second = apply_repair(s, w, "batch", env["user"], env["project"])
    assert first["draft_id"] == second["draft_id"]
    assert w.graph == original_graph and w.status == original_status
    import uuid

    assert s.get(WorkflowRun, uuid.UUID(first["draft_id"])).status == "draft"


def test_script_screening_happens_before_top_n(env, monkeypatch):
    from backend_v2.app.workflows.gate_runtime import run_gate

    s, _, _, _, _, gate, storage = runtime_fixture(env, threshold=0)
    gate.snapshot = {
        **gate.snapshot,
        "edge": {
            **gate.snapshot["edge"],
            "gate": {"configured": True, "script": "screen", "rules": {"sort_metric": "score", "top_n": 1}},
        },
    }
    monkeypatch.setattr(
        "backend_v2.app.workflows.gate_runtime._script_decisions",
        lambda script, records: [
            {"id": r["id"], "passed": r["key"] == "drop", "reason": "custom rule"} for r in records
        ],
    )
    run_gate(s, gate, storage)
    assert len(gate.selected_ids) == 1
    assert next(d for d in gate.decisions if d["passed"])["metrics"]["score"] == 40


def test_migration_upgrade_and_downgrade():
    import importlib

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect

    migration = importlib.import_module("backend_v2.alembic.versions.0056_workflow_gates")
    engine = create_engine("sqlite+pysqlite://")
    with engine.begin() as connection:
        for table in ["projects", "users", "jobs", "workflow_runs", "workflow_nodes"]:
            connection.exec_driver_sql(f"CREATE TABLE {table} (id CHAR(32) PRIMARY KEY)")
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
            assert "workflow_gate_evaluations" in inspect(connection).get_table_names()
            assert "configuration" in {c["name"] for c in inspect(connection).get_columns("workflow_nodes")}
            assert next(
                c for c in inspect(connection).get_columns("workflow_gate_evaluations") if c["name"] == "target_job_id"
            )["nullable"]
            migration.downgrade()
            assert "workflow_gate_evaluations" not in inspect(connection).get_table_names()
            assert "configuration" not in {c["name"] for c in inspect(connection).get_columns("workflow_nodes")}


def test_gate_input_names_do_not_overwrite_files_from_multiple_branches():
    from backend_v2.app.workflows.gate_runtime import unique_input_names

    inputs = [
        {"port": "sequences", "filename": "results.fasta", "artifact_id": "one", "object_key": "a"},
        {"port": "sequences", "filename": "results.fasta", "artifact_id": "two", "object_key": "b"},
        {"port": "reference", "filename": "results.fasta", "artifact_id": "ref", "object_key": "c"},
    ]
    staged = unique_input_names(inputs)
    assert len({(i["port"], i["filename"]) for i in staged}) == 3
    assert staged[2]["filename"] == "results.fasta"
    assert [i["object_key"] for i in staged] == ["a", "b", "c"]
    assert inputs[0]["filename"] == "results.fasta"
    assert unique_input_names(staged) == staged


def test_collected_empty_manifest_ends_branch_but_missing_manifest_errors(env):
    from backend_v2.app.workflows.gate_runtime import run_gate
    from backend_v2.app.workflows.models import WorkflowResult
    from sqlalchemy import delete

    s, _, _, source, _, gate, storage = runtime_fixture(env)
    s.execute(delete(WorkflowResult).where(WorkflowResult.job_id == source.id))
    source.runtime_spec = {**source.runtime_spec, "result_manifest": {"version": 1, "ports": {"sequences": 0}}}
    run_gate(s, gate, storage)
    assert gate.status == "empty" and gate.selected_ids == []
    gate.status = "waiting"
    source.runtime_spec = {**source.runtime_spec, "result_manifest": {}}
    with pytest.raises(ValueError, match="upstream_result_manifest_missing"):
        run_gate(s, gate, storage)


def test_unsupported_output_is_not_manually_eligible(env):
    from backend_v2.app.workflows.gate_runtime import run_gate
    from backend_v2.app.workflows.models import WorkflowResult
    from sqlalchemy import select

    s, _, _, source, _, gate, storage = runtime_fixture(env, mode="manual")
    for row in s.scalars(select(WorkflowResult).where(WorkflowResult.job_id == source.id)):
        row.payload = {
            **row.payload,
            "files": [
                {**f, "selector": {**f["selector"], "error": "bundle_unsplittable"}} for f in row.payload["files"]
            ],
        }
    with pytest.raises(ValueError, match="upstream_result_format_unsupported"):
        run_gate(s, gate, storage)
    assert not gate.selected_ids


def test_empty_inherited_standard_does_not_run_branch_script(env, monkeypatch):
    from backend_v2.app.workflows.gate_runtime import run_gate

    s, _, _, _, _, gate, storage = runtime_fixture(env)
    gate.snapshot = {
        **gate.snapshot,
        "output_policy": {"configured": True, "rules": {"conditions": [{"metric": "score", "value": 999}]}},
        "edge": {**gate.snapshot["edge"], "gate": {"configured": True, "script": "screen"}},
    }
    monkeypatch.setattr(
        "backend_v2.app.workflows.gate_runtime._script_decisions",
        lambda *args: pytest.fail("Empty branch must not execute a script"),
    )
    run_gate(s, gate, storage)
    assert gate.status == "empty"


def test_incomplete_coordinates_are_pending_data_not_zero_helices(monkeypatch):
    from backend_v2.app.workflows.structure_metrics import structure_metrics

    monkeypatch.setattr("subprocess.run", lambda *a, **k: pytest.fail("Incomplete coordinates must not invoke DSSP"))
    pdb = b"ATOM      1  CA  ALA B   1       0.000   0.000   0.000  1.00 20.00           C  \nEND\n"
    with pytest.raises(ValueError, match="backbone_atoms_missing:B"):
        structure_metrics("incomplete.pdb", pdb, StructurePolicy(chains=["B"]))
    with pytest.raises(ValueError, match="design_chain_missing:A"):
        structure_metrics("incomplete.pdb", pdb, StructurePolicy(chains=["A"]))


def test_structure_presets_and_region_have_separate_meanings():
    records = [{"id": "beta", "metrics": {"helix_count": 0, "strand_count": 3, "structured_residue_count": 12}}]
    assert not evaluate(records, GatePolicy(structure={"chains": ["B"]}))[0]["passed"]
    assert evaluate(records, GatePolicy(structure={"chains": ["B"], "preset": "beta_sheet"}))[0]["passed"]
    assert evaluate(records, GatePolicy(structure={"chains": ["B"], "preset": "structured"}))[0]["passed"]
    assignments = [("B", i, "H") for i in range(1, 9)]
    assert count_helices(assignments, StructurePolicy(chains=["B"], start=3, end=5)) == 0
    assert count_helices(assignments, StructurePolicy(chains=["B"], start=3, end=6)) == 1


def test_failed_gate_retry_preserves_old_decisions_and_does_not_reexecute_old_revision(env):
    import uuid

    from backend_v2.app.workflows.gate_runtime import run_gate
    from backend_v2.app.workflows.gate_service import retry_gate
    from backend_v2.app.workflows.models import GateEvaluation

    s, w, _, _, _, gate, storage = runtime_fixture(env)
    gate.status = "error"
    gate.error_message = "temporary worker error"
    prior_snapshot = gate.snapshot.copy()
    retried = retry_gate(w.id, gate.id, s, env["user"])
    assert gate.status == "superseded" and gate.snapshot == prior_snapshot
    run_gate(s, gate, storage)
    assert gate.status == "superseded"
    replacement = s.get(GateEvaluation, uuid.UUID(retried["id"]))
    assert replacement.revision == gate.revision + 1
    run_gate(s, replacement, storage)
    assert replacement.status == "released" and len(replacement.selected_ids) == 1
    assert gate.error_message == "temporary worker error"


def test_parameter_suggestions_use_explicit_mapping_and_attempt_results(env):
    from types import SimpleNamespace

    from backend_v2.app.workflows.assistance import suggest_parameters
    from backend_v2.app.workflows.repository import WorkflowRepository

    s, w, _, _, _, _, _ = runtime_fixture(env)
    nodes = WorkflowRepository(s).nodes(w.id)
    source = next(n for n in nodes if n.node_key == "a")
    target = next(n for n in nodes if n.node_key == "b")
    source.parameters = {"temperature": 0.25, "unrelated": 99}
    target.parameters = {"sampling": 0.1, "unrelated": 1}
    plugin = SimpleNamespace(
        parameter_schema={
            "properties": {"sampling": {}, "unrelated": {}},
            "x-bda-upstream-parameters": {"sampling": {"port": "sequences", "parameter": "temperature"}},
        }
    )
    result = suggest_parameters(w, target, nodes, plugin, env["project"], s)
    assert result["suggestions"] == [
        {
            "parameter": "sampling",
            "current": 0.1,
            "value": 0.25,
            "source": "a.temperature",
            "reason": "Explicit plugin upstream parameter mapping",
        }
    ]
    assert result["upstream_results"][0]["count"] == 2
    assert "score" in result["upstream_results"][0]["metrics"]
    assert target.parameters == {"sampling": 0.1, "unrelated": 1}
    source.parameters = {"temperature": 0.5}
    assert suggest_parameters(w, target, nodes, plugin, env["project"], s)["fingerprint"] != result["fingerprint"]


def test_preflight_warns_when_a_source_port_cannot_be_routed(env):
    """A gate on a port with no filename pattern will never see a result.

    Collection tags an output by its directory (outputs/<port>/) or by the port's
    filename_glob, and a glob of '*' is deliberately never matched. On 2026-09-11
    ProteinMPNN succeeded on the cluster, three outputs were collected and verified,
    and the gate settled as `error` with nothing to screen because every output port
    was left at the default.
    """
    from backend_v2.app.workflows.preflight import unroutable_output_warnings

    plugin = env["producer"]
    plugin.output_ports = [{**BACKBONE_OUT, "filename_glob": "*"}]
    workflow = SimpleNamespace(
        graph={
            "edges": [
                {"id": "e", "source": "a", "target": "b", "source_port": "backbones", "gate": {"mode": "manual"}}
            ]
        }
    )
    warnings = unroutable_output_warnings(workflow, {"a": plugin})
    assert [w["code"] for w in warnings] == ["output_port_unroutable"]
    assert "backbones" in warnings[0]["message"]

    # A declared pattern is routable, and an ordering connection carries no data at all.
    plugin.output_ports = [{**BACKBONE_OUT, "filename_glob": "*.pdb"}]
    assert unroutable_output_warnings(workflow, {"a": plugin}) == []
    plugin.output_ports = [{**BACKBONE_OUT, "filename_glob": "*"}]
    workflow.graph["edges"][0]["gate"] = {"mode": "dependency"}
    assert unroutable_output_warnings(workflow, {"a": plugin}) == []


def test_preflight_warns_when_a_queue_contradicts_the_plugin(env):
    """Both directions of a queue/plugin mismatch, and silence for an unknown queue."""
    from backend_v2.app.registry.models import ComputeNode
    from backend_v2.app.workflows.preflight import queue_capability_warnings

    s = env["session"]
    s.add_all(
        [
            ComputeNode(name="cpu", backend="lsf", queue="63", labels={"gpu_count": 0}, enabled=True),
            ComputeNode(name="gpu", backend="lsf", queue="4v100-16-e5", labels={"gpu_count": 4}, enabled=True),
        ]
    )
    s.flush()
    plugin = env["consumer"]
    plugin.resources = {"gpu": True, "gpu_count": 1}

    def _node(queue):
        return SimpleNamespace(node_key="design", id=uuid.uuid4(), queue=queue, execution_mode="dispatch")

    # A GPU plugin on a queue registered with none.
    found = queue_capability_warnings(s, [_node("63")], {"design": plugin})
    assert [w["code"] for w in found] == ["node_queue_capability_mismatch"]
    assert "cannot give it" in found[0]["message"]

    # Matching capability is silent.
    assert queue_capability_warnings(s, [_node("4v100-16-e5")], {"design": plugin}) == []

    # A CPU-only stage on a GPU queue would hold a card it never uses.
    plugin.resources = {"cpus": 1}
    held = queue_capability_warnings(s, [_node("4v100-16-e5")], {"design": plugin})
    assert [w["code"] for w in held] == ["node_queue_capability_mismatch"]
    assert "hold it unused" in held[0]["message"]

    # A queue nobody registered says nothing, rather than guessing from its name.
    assert queue_capability_warnings(s, [_node("v3-64")], {"design": plugin}) == []
