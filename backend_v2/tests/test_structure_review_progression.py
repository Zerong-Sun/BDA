"""Real parsers + scheduler + subset binding in an isolated SQLite/memory fixture."""

import hashlib
import json
import uuid

from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.compute.models import JobEvent
from backend_v2.app.compute.parsers import ParseContext, get_parser
from backend_v2.app.compute.repository import ComputeRepository
from backend_v2.app.compute.schemas import SubmissionCreate
from backend_v2.app.compute.service import create_submission, schedule_ready_jobs
from backend_v2.app.registry.models import ModelPlugin
from backend_v2.app.workflows.gate_runtime import capture_results, latest_gate, run_gate
from backend_v2.app.workflows.preflight import evaluate_preflight
from backend_v2.app.workflows.schemas import WorkflowCreate
from backend_v2.app.workflows.service import create_workflow
from backend_v2.tests.scientific_gate_helpers import approve_test_gate, review_test_design
from backend_v2.tests.test_compute_binding import env as _binding_env
from backend_v2.tests.test_workflow_gates import MemoryStorage

env = _binding_env

def test_three_models_advance_only_with_filtered_checksum_matched_structures(env):
    s = env["session"]
    storage = MemoryStorage()
    plugins = []
    for key, parser in [("fold", "alphafold2_superfold"), ("rosetta", "rosetta_interface"), ("align", None)]:
        plugin = ModelPlugin(
            plugin_key=key,
            plugin_version="test",
            name=key,
            container_image="test:1",
            command="true",
            output_parser=parser,
            parameter_schema={},
            output_schema={},
            input_ports=[]
            if key == "fold"
            else [{"name": "structures", "kind": "protein_structure", "required": True, "multiple": True}],
            output_ports=[
                {
                    "name": "structures",
                    "kind": "protein_structure",
                    "artifact_type": "predicted_structure",
                    "filename_glob": "*.pdb",
                }
            ],
        )
        s.add(plugin)
        s.flush()
        plugins.append(plugin)
    workflow = create_workflow(
        s,
        env["project"],
        WorkflowCreate.model_validate(
            {
                "name": "isolated model chain",
                "nodes": [
                    {
                        "key": p.plugin_key,
                        "model_plugin": p.plugin_key,
                        "model_plugin_id": str(p.id),
                        "node_type": "model",
                    }
                    for p in plugins
                ],
                "edges": [
                    {
                        "id": "fold-gate",
                        "source": "fold",
                        "target": "rosetta",
                        "source_port": "structures",
                        "target_port": "structures",
                        "gate": {
                            "mode": "automatic",
                            "configured": True,
                            "rules": {
                                "conditions": [
                                    {"metric": "plddt", "op": "gte", "value": 80},
                                    {"metric": "pae_interaction", "op": "lte", "value": 10},
                                ]
                            },
                        },
                    },
                    {
                        "id": "interface-gate",
                        "source": "rosetta",
                        "target": "align",
                        "source_port": "structures",
                        "target_port": "structures",
                        "gate": {
                            "mode": "automatic",
                            "configured": True,
                            "rules": {"sort_metric": "dG_separated", "descending": False, "top_n": 1},
                        },
                    },
                ],
            }
        ),
        env["user"],
    )
    # Automatic gates need real evidence/review service records even in this
    # synthetic parser/scheduler regression; no production check is bypassed.
    blockers, _, _ = evaluate_preflight(s, workflow, compute_backend="demo")
    assert sum(item["code"] == "scientific_evidence_approval_required" for item in blockers) == 2
    # Freeze the design first: its new version must be the one gates approve.
    review_test_design(s, env["project"], workflow, env["user"])
    for edge in workflow.graph["edges"]:
        approve_test_gate(env, workflow, edge)
    blockers, _, _ = evaluate_preflight(s, workflow, compute_backend="demo")
    assert not blockers
    submission, jobs = create_submission(
        s,
        workflow=workflow,
        project=env["project"],
        payload=SubmissionCreate(compute_backend="demo"),
        idempotency_key="isolated-chain",
        user=env["user"],
    )
    by_key = {j.runtime_spec["node_key"]: j for j in jobs}
    repo = ComputeRepository(s)
    assert not repo.has_outbox_event("job.dispatch", by_key["rosetta"].id)
    assert not repo.has_outbox_event("job.dispatch", by_key["align"].id)

    def collect(key, files):
        job = by_key[key]
        outputs = []
        artifacts = []
        for filename, body, port in files:
            object_key = f"{key}/{filename}"
            storage.files[object_key] = body
            artifact = Artifact(
                project_id=workflow.project_id,
                created_by=env["user"].id,
                artifact_type="predicted_structure" if port == "structures" else "score_table",
                filename=filename,
                object_key=object_key,
                size_bytes=len(body),
                checksum_sha256=hashlib.sha256(body).hexdigest(),
                content_type="text/plain",
                lineage={"job_id": str(job.id), "output_port": port},
            )
            s.add(artifact)
            s.flush()
            artifacts.append(artifact)
            outputs.append({"filename": filename, "object_key": object_key})
        parser = get_parser(job.runtime_spec["plugin_snapshot"]["output_parser"])
        parsed = parser(ParseContext(job.id, workflow.project_id, 1, outputs, {}, storage.files.__getitem__))
        capture_results(s, job, artifacts, parsed, storage)
        job.status = "succeeded"
        s.add(
            JobEvent(
                job_id=job.id, event_type="job.succeeded", payload={"artifact_ids": [str(a.id) for a in artifacts]}
            )
        )
        s.flush()
        schedule_ready_jobs(s, submission, workflow)

    files = []
    for name, confidence in [("keep", 90), ("drop", 40)]:
        stem = f"{name}_model_4_ptm_seed_0"
        files += [
            (stem + "_unrelaxed.pdb", f"ATOM {name}\n".encode(), "structures"),
            (
                stem + "_prediction_results.json",
                json.dumps({"mean_plddt": confidence, "mean_pae_interaction": 5}).encode(),
                "metrics",
            ),
        ]
    collect("fold", files)
    gate = latest_gate(s, by_key["rosetta"].id, "fold-gate")
    run_gate(s, gate, storage)
    assert gate.status == "released"
    schedule_ready_jobs(s, submission, workflow)
    selected = by_key["rosetta"].runtime_spec["input_manifest"]["inputs"]
    assert len(selected) == 1
    assert storage.files[s.get(Artifact, uuid.UUID(selected[0]["artifact_id"])).object_key] == b"ATOM keep\n"
    assert repo.has_outbox_event("job.dispatch", by_key["rosetta"].id)
    assert not repo.has_outbox_event("job.dispatch", by_key["align"].id)
    body = b"ATOM relaxed\n"
    checksum = hashlib.sha256(body).hexdigest()
    collect(
        "rosetta",
        [
            ("relaxed.pdb", body, "structures"),
            (
                "scores.csv",
                f"stage,scored_structure_sha256,dG_separated\ninterface,{checksum},-12\n".encode(),
                "scores",
            ),
        ],
    )
    gate = latest_gate(s, by_key["align"].id, "interface-gate")
    run_gate(s, gate, storage)
    assert gate.status == "released"
    schedule_ready_jobs(s, submission, workflow)
    schedule_ready_jobs(s, submission, workflow)
    assert repo.has_outbox_event("job.dispatch", by_key["align"].id)
    selected = by_key["align"].runtime_spec["input_manifest"]["inputs"]
    assert len(selected) == 1
    assert storage.files[s.get(Artifact, uuid.UUID(selected[0]["artifact_id"])).object_key] == body


def test_saved_backend_drives_preflight_and_host_models_reject_docker(env):
    from backend_v2.app.workflows.preflight import evaluate_preflight, workflow_backend

    plugin = env["producer"]
    plugin.runtime_mode = "script"
    workflow = create_workflow(
        env["session"],
        env["project"],
        WorkflowCreate.model_validate(
            {
                "name": "host route",
                "compute_backend": "lsf",
                "nodes": [
                    {
                        "key": "fold",
                        "model_plugin": plugin.plugin_key,
                        "model_plugin_id": str(plugin.id),
                        "node_type": "model",
                    }
                ],
            }
        ),
        env["user"],
    )
    assert workflow.graph["compute_backend"] == "lsf"
    assert workflow_backend(workflow) == "lsf"
    assert workflow_backend(workflow, "docker") == "docker"
    blockers, _, checks = evaluate_preflight(env["session"], workflow)
    assert checks["compute_backend"] == "lsf"
    assert not any(b["code"] == "plugin_backend_incompatible" for b in blockers)
    blockers, _, _ = evaluate_preflight(env["session"], workflow, compute_backend="docker")
    assert any(b["code"] == "plugin_backend_incompatible" for b in blockers)
