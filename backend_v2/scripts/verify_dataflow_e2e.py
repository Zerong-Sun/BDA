"""End-to-end check of input binding and node dataflow against the live database.

Runs entirely inside a transaction that is rolled back, so it proves the code works
against the real schema, real seeded plugin ports and real artifacts without leaving
anything behind.

    python backend_v2/scripts/verify_dataflow_e2e.py
"""

from __future__ import annotations

import sys
import uuid

from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.artifacts.models import Artifact, ArtifactLineageEdge
from backend_v2.app.compute.models import Job, JobEvent
from backend_v2.app.compute.repository import ComputeRepository
from backend_v2.app.compute.schemas import SubmissionCreate
from backend_v2.app.compute.service import create_submission, schedule_ready_jobs
from backend_v2.app.core.database import engine
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import User
from backend_v2.app.projects.models import Project
from backend_v2.app.registry.models import ModelPlugin
from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun
from sqlalchemy import select
from sqlalchemy.orm import Session

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((PASS if ok else FAIL, name, detail))


def main() -> int:
    with Session(engine) as session:
        project = session.scalar(
            select(Project).where(Project.name == "SweetProtein_RFdiffusion_100x2_20260626")
        ) or session.scalar(select(Project).order_by(Project.created_at.desc()))
        user = session.scalar(select(User).where(User.enabled.is_(True)).order_by(User.created_at))
        rfd = session.scalar(select(ModelPlugin).where(ModelPlugin.plugin_key == "RFdiffusion"))
        mpnn = session.scalar(select(ModelPlugin).where(ModelPlugin.plugin_key == "ProteinMPNN"))
        if not all([project, user, rfd, mpnn]):
            print("missing fixtures in live database", file=sys.stderr)
            return 2
        assert project and user and rfd and mpnn

        print(f"project={project.name}  user={user.username}")
        check("RFdiffusion has seeded output ports", len(rfd.output_ports) > 0, str(rfd.output_ports))
        check("ProteinMPNN has seeded input ports", len(mpnn.input_ports) > 0, str(mpnn.input_ports))

        structure = session.scalar(
            select(Artifact).where(
                Artifact.project_id == project.id,
                Artifact.artifact_type.in_(["backbone_set", "target_structure"]),
                Artifact.status == "available",
                Artifact.deleted_at.is_(None),
            )
        )
        if structure is None:
            print("no bindable structure artifact in project", file=sys.stderr)
            return 2
        print(f"binding artifact={structure.filename} type={structure.artifact_type} ct={structure.content_type}")

        workflow = WorkflowRun(
            project_id=project.id,
            name=f"e2e-dataflow-{uuid.uuid4().hex[:8]}",
            status="draft",
            graph={
                "nodes": [{"key": "rfd"}, {"key": "mpnn"}],
                "edges": [
                    {
                        "source": "rfd",
                        "target": "mpnn",
                        "source_port": rfd.output_ports[0]["name"],
                        "target_port": mpnn.input_ports[0]["name"],
                    }
                ],
            },
            created_by=user.id,
        )
        session.add(workflow)
        session.flush()
        session.add_all(
            [
                WorkflowNode(
                    workflow_run_id=workflow.id,
                    node_key="rfd",
                    node_type="model",
                    model_plugin=rfd.plugin_key,
                    model_plugin_id=rfd.id,
                    status="draft",
                    parameters={},
                    input_bindings=[
                        {
                            "port": rfd.input_ports[0]["name"],
                            "source": "artifact",
                            "artifact_id": str(structure.id),
                        }
                    ]
                    if rfd.input_ports
                    else [],
                ),
                WorkflowNode(
                    workflow_run_id=workflow.id,
                    node_key="mpnn",
                    node_type="model",
                    model_plugin=mpnn.plugin_key,
                    model_plugin_id=mpnn.id,
                    status="draft",
                    parameters={},
                    input_bindings=[
                        {
                            "port": mpnn.input_ports[0]["name"],
                            "source": "upstream",
                            "from_node": "rfd",
                            "from_port": rfd.output_ports[0]["name"],
                        }
                    ],
                ),
            ]
        )
        session.flush()

        # 1. Preflight must pass for a correctly wired graph.
        from backend_v2.app.workflows.preflight import evaluate_preflight

        blockers, warnings, _ = evaluate_preflight(session, workflow)
        check("preflight passes for a wired graph", not blockers, str(blockers))

        # 2. Submission resolves the direct artifact binding into the manifest.
        submission, jobs = create_submission(
            session,
            workflow=workflow,
            project=project,
            payload=SubmissionCreate(compute_backend="demo", timeout_minutes=30),
            idempotency_key=f"e2e-{uuid.uuid4().hex}",
            user=user,
        )
        by_key = {job.runtime_spec["node_key"]: job for job in jobs}
        upstream_inputs = by_key["rfd"].runtime_spec["input_manifest"]["inputs"]
        check(
            "upstream job receives its bound artifact",
            [item["artifact_id"] for item in upstream_inputs] == [str(structure.id)],
            str(upstream_inputs),
        )
        check(
            "downstream job records a pending upstream input",
            by_key["mpnn"].runtime_spec["input_manifest"]["pending_inputs"]
            == [
                {
                    "port": mpnn.input_ports[0]["name"],
                    "from_node": "rfd",
                    "from_port": rfd.output_ports[0]["name"],
                }
            ],
            str(by_key["mpnn"].runtime_spec["input_manifest"]),
        )

        # 3. Upstream succeeds and produces an artifact on its declared port.
        upstream = by_key["rfd"]
        produced = Artifact(
            project_id=project.id,
            created_by=user.id,
            artifact_type=rfd.output_ports[0]["artifact_type"],
            filename="e2e_design_0.pdb",
            content_type="application/vnd.palm",
            object_key=f"jobs/{upstream.id}/attempt-1/outputs/e2e_design_0.pdb",
            size_bytes=42,
            checksum_sha256="0" * 64,
            lineage={"job_id": str(upstream.id), "output_port": rfd.output_ports[0]["name"]},
        )
        session.add(produced)
        session.flush()
        upstream.status = "succeeded"
        session.add(
            JobEvent(job_id=upstream.id, event_type="job.succeeded", payload={"artifact_ids": [str(produced.id)]})
        )
        session.flush()

        schedule_ready_jobs(session, submission, workflow)
        session.flush()

        downstream = session.get(Job, by_key["mpnn"].id)
        assert downstream is not None
        manifest = downstream.runtime_spec["input_manifest"]
        check(
            "downstream job receives the upstream output",
            [item["artifact_id"] for item in manifest["inputs"]] == [str(produced.id)],
            str(manifest["inputs"]),
        )
        check("pending inputs cleared after resolution", manifest["pending_inputs"] == [], str(manifest))
        check(
            "downstream is dispatchable",
            ComputeRepository(session).has_outbox_event("job.dispatch", downstream.id),
        )

        # 4. compute_input lineage edges are produced (this relation had zero rows).
        from backend_v2.app.compute import tasks

        collected = tasks._persist_outputs(
            session,
            downstream,
            submission,
            [
                {
                    "object_key": f"jobs/{downstream.id}/attempt-1/outputs/e2e.fa",
                    "checksum_sha256": "1" * 64,
                    "size_bytes": 20,
                    "filename": "e2e.fa",
                    "content_type": "text/x-fasta",
                    "artifact_type": mpnn.output_ports[0]["artifact_type"],
                    "port": mpnn.output_ports[0]["name"],
                    "metadata": {},
                }
            ],
        )
        session.flush()
        edges = list(
            session.scalars(
                select(ArtifactLineageEdge).where(ArtifactLineageEdge.child_artifact_id == collected[0].id)
            )
        )
        check(
            "compute_input lineage edge created",
            [edge.relation for edge in edges] == ["compute_input"]
            and edges[0].parent_artifact_id == produced.id,
            str([(edge.relation, str(edge.parent_artifact_id)) for edge in edges]),
        )

        # 5. A missing required input must block submission.
        bad = WorkflowRun(
            project_id=project.id,
            name=f"e2e-bad-{uuid.uuid4().hex[:8]}",
            status="draft",
            graph={"nodes": [{"key": "mpnn"}], "edges": []},
            created_by=user.id,
        )
        session.add(bad)
        session.flush()
        # Derived ports are all optional by design, so this check needs a plugin with an
        # explicitly required port to have anything to block on.
        strict = ModelPlugin(
            plugin_key=f"e2e-strict-{uuid.uuid4().hex[:8]}",
            plugin_version="1.0.0",
            name="E2E strict",
            container_image="e2e:1.0.0",
            command="true",
            enabled=True,
            validation_status="valid",
            input_ports=[
                {
                    "name": "required_structure",
                    "kind": "protein_structure",
                    "accepts": ["backbone_set"],
                    "required": True,
                }
            ],
            output_ports=[],
        )
        session.add(strict)
        session.flush()
        session.add(
            WorkflowNode(
                workflow_run_id=bad.id,
                node_key="mpnn",
                node_type="model",
                model_plugin=strict.plugin_key,
                model_plugin_id=strict.id,
                status="draft",
                parameters={},
                input_bindings=[],
            )
        )
        session.flush()
        try:
            create_submission(
                session,
                workflow=bad,
                project=project,
                payload=SubmissionCreate(compute_backend="demo"),
                idempotency_key=f"e2e-bad-{uuid.uuid4().hex}",
                user=user,
            )
            check("submission blocked when a required input is unbound", False, "submission was accepted")
        except DomainError as exc:
            check(
                "submission blocked when a required input is unbound",
                exc.error_code == "workflow_preflight_failed"
                and any(item["code"] == "input_binding_unsatisfied" for item in exc.errors or []),
                f"{exc.error_code}: {[i['code'] for i in exc.errors or []]}",
            )

        session.rollback()
        print("\n-- transaction rolled back; live data unchanged --\n")

    width = max(len(name) for _, name, _ in results)
    for status, name, detail in results:
        print(f"[{status}] {name.ljust(width)}  {detail[:90] if status == FAIL else ''}")
    failures = sum(1 for status, _, _ in results if status == FAIL)
    print(f"\n{len(results) - failures}/{len(results)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
