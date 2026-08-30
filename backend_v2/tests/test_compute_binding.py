"""Input binding and node-to-node dataflow.

These cover the defect that made the workbench unusable: jobs were dispatched with an
empty input manifest, so a model never received the files it was wired to consume, and
the compute_input lineage edges were dead code.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.artifacts.models import Artifact, ArtifactLineageEdge
from backend_v2.app.compute.binding import (
    BindingError,
    binding_blockers,
    resolve_artifact_bindings,
    resolve_pending_inputs,
)
from backend_v2.app.compute.models import Job, JobEvent, JobSubmission
from backend_v2.app.compute.repository import ComputeRepository
from backend_v2.app.compute.schemas import SubmissionCreate
from backend_v2.app.compute.service import create_submission, schedule_ready_jobs
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.app.registry.models import ModelPlugin
from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun
from backend_v2.tests._sqlite import enforce_foreign_keys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

STRUCTURE_PORT = {
    "name": "backbone",
    "kind": "protein_structure",
    "accepts": ["backbone_set", "target_structure"],
    "required": True,
    "multiple": False,
}
SEQUENCE_OUT = {"name": "sequences", "kind": "protein_sequence", "artifact_type": "sequence_set"}
BACKBONE_OUT = {"name": "backbones", "kind": "protein_structure", "artifact_type": "backbone_set"}
SEQUENCE_IN = {
    "name": "sequences",
    "kind": "protein_sequence",
    "accepts": ["sequence_set"],
    "required": True,
}


@pytest.fixture
def env() -> Generator[dict]:
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://"))
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = User(username="binder", display_name="Binder", role="admin", enabled=True)
        org = Organization(name="Bind Org")
        session.add_all([user, org])
        session.flush()
        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
        project = Project(organization_id=org.id, owner_id=user.id, name="Bind", project_type="design")
        session.add(project)
        session.flush()
        session.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))

        producer = ModelPlugin(
            plugin_key="RFdiffusion",
            plugin_version="1.1.0",
            name="RFdiffusion",
            container_image="rfd:1.1.0",
            command="run_rfd.sh",
            input_ports=[],
            output_ports=[BACKBONE_OUT],
            enabled=True,
        )
        consumer = ModelPlugin(
            plugin_key="ProteinMPNN",
            plugin_version="1.0.0",
            name="ProteinMPNN",
            container_image="mpnn:1.0.0",
            command="run_mpnn.sh",
            input_ports=[STRUCTURE_PORT],
            output_ports=[SEQUENCE_OUT],
            enabled=True,
        )
        session.add_all([producer, consumer])
        session.flush()

        artifact = Artifact(
            project_id=project.id,
            created_by=user.id,
            artifact_type="target_structure",
            filename="target.pdb",
            # Deliberately a browser-mis-sniffed type: real uploads look like this, and
            # binding must not gate on content_type.
            content_type="application/vnd.palm",
            object_key=f"projects/{project.id}/sha256/abc",
            size_bytes=10,
            checksum_sha256="a" * 64,
        )
        session.add(artifact)
        session.commit()
        yield {
            "session": session,
            "user": user,
            "project": project,
            "producer": producer,
            "consumer": consumer,
            "artifact": artifact,
        }
    engine.dispose()


def _node(workflow, key, plugin, bindings) -> WorkflowNode:
    return WorkflowNode(
        workflow_run_id=workflow.id,
        node_key=key,
        node_type="model",
        model_plugin=plugin.plugin_key,
        model_plugin_id=plugin.id,
        status="draft",
        parameters={},
        input_bindings=bindings,
    )


def test_artifact_binding_resolves_into_manifest(env) -> None:
    session, project, consumer, artifact = env["session"], env["project"], env["consumer"], env["artifact"]
    workflow = WorkflowRun(project_id=project.id, name="w", status="draft", graph={}, created_by=env["user"].id)
    session.add(workflow)
    session.flush()
    node = _node(
        workflow, "mpnn", consumer, [{"port": "backbone", "source": "artifact", "artifact_id": str(artifact.id)}]
    )
    session.add(node)
    session.flush()

    inputs, pending = resolve_artifact_bindings(session, node=node, plugin=consumer, project_id=project.id)

    assert pending == []
    assert len(inputs) == 1
    assert inputs[0]["port"] == "backbone"
    assert inputs[0]["artifact_id"] == str(artifact.id)
    assert inputs[0]["object_key"] == artifact.object_key
    assert inputs[0]["checksum_sha256"] == artifact.checksum_sha256


def test_required_port_without_binding_is_a_blocker(env) -> None:
    session, project, consumer = env["session"], env["project"], env["consumer"]
    workflow = WorkflowRun(project_id=project.id, name="w", status="draft", graph={}, created_by=env["user"].id)
    session.add(workflow)
    session.flush()
    node = _node(workflow, "mpnn", consumer, [])
    session.add(node)
    session.flush()

    codes = [item["code"] for item in binding_blockers(node, consumer)]
    assert codes == ["input_binding_unsatisfied"]


def test_binding_rejects_wrong_artifact_type(env) -> None:
    session, project, consumer, user = env["session"], env["project"], env["consumer"], env["user"]
    wrong = Artifact(
        project_id=project.id,
        created_by=user.id,
        artifact_type="score_table",
        filename="scores.csv",
        content_type="text/csv",
        object_key=f"projects/{project.id}/sha256/def",
        size_bytes=5,
        checksum_sha256="b" * 64,
    )
    session.add(wrong)
    session.flush()
    workflow = WorkflowRun(project_id=project.id, name="w", status="draft", graph={}, created_by=user.id)
    session.add(workflow)
    session.flush()
    node = _node(workflow, "mpnn", consumer, [{"port": "backbone", "source": "artifact", "artifact_id": str(wrong.id)}])
    session.add(node)
    session.flush()

    with pytest.raises(BindingError) as excinfo:
        resolve_artifact_bindings(session, node=node, plugin=consumer, project_id=project.id)
    assert excinfo.value.blockers[0]["code"] == "input_artifact_type_rejected"


def test_binding_rejects_artifact_from_another_project(env) -> None:
    session, project, consumer, user = env["session"], env["project"], env["consumer"], env["user"]
    other = Project(organization_id=project.organization_id, owner_id=user.id, name="Other", project_type="design")
    session.add(other)
    session.flush()
    foreign = Artifact(
        project_id=other.id,
        created_by=user.id,
        artifact_type="target_structure",
        filename="foreign.pdb",
        content_type="chemical/x-pdb",
        object_key=f"projects/{other.id}/sha256/fff",
        size_bytes=5,
        checksum_sha256="c" * 64,
    )
    session.add(foreign)
    session.flush()
    workflow = WorkflowRun(project_id=project.id, name="w", status="draft", graph={}, created_by=user.id)
    session.add(workflow)
    session.flush()
    node = _node(
        workflow, "mpnn", consumer, [{"port": "backbone", "source": "artifact", "artifact_id": str(foreign.id)}]
    )
    session.add(node)
    session.flush()

    with pytest.raises(BindingError) as excinfo:
        resolve_artifact_bindings(session, node=node, plugin=consumer, project_id=project.id)
    assert excinfo.value.blockers[0]["code"] == "input_artifact_unavailable"


def test_upstream_outputs_resolve_by_port(env) -> None:
    session, project, user = env["session"], env["project"], env["user"]
    produced = Artifact(
        project_id=project.id,
        created_by=user.id,
        artifact_type="backbone_set",
        filename="design_0.pdb",
        content_type="application/vnd.palm",
        object_key=f"jobs/{uuid.uuid4()}/attempt-1/outputs/design_0.pdb",
        size_bytes=20,
        checksum_sha256="d" * 64,
        lineage={"output_port": "backbones"},
    )
    session.add(produced)
    session.flush()

    resolved, unresolved = resolve_pending_inputs(
        pending=[{"port": "backbone", "from_node": "rfd", "from_port": "backbones"}],
        produced={"rfd": [produced]},
        plugin=env["producer"],
    )
    assert unresolved == []
    assert resolved[0]["port"] == "backbone"
    assert resolved[0]["artifact_id"] == str(produced.id)


def test_dataflow_feeds_downstream_job_and_records_lineage(env) -> None:
    """The end-to-end defect: an upstream node's outputs must reach the next node."""
    session, project, user = env["session"], env["project"], env["user"]
    producer, consumer = env["producer"], env["consumer"]

    workflow = WorkflowRun(
        project_id=project.id,
        name="chain",
        status="draft",
        graph={
            "nodes": [{"key": "rfd"}, {"key": "mpnn"}],
            "edges": [{"source": "rfd", "target": "mpnn", "source_port": "backbones", "target_port": "backbone"}],
        },
        created_by=user.id,
    )
    session.add(workflow)
    session.flush()
    session.add_all(
        [
            _node(workflow, "rfd", producer, []),
            _node(
                workflow,
                "mpnn",
                consumer,
                [{"port": "backbone", "source": "upstream", "from_node": "rfd", "from_port": "backbones"}],
            ),
        ]
    )
    session.flush()

    submission, jobs = create_submission(
        session,
        workflow=workflow,
        project=project,
        payload=SubmissionCreate(compute_backend="demo", timeout_minutes=30),
        idempotency_key="chain-key",
        user=user,
    )
    by_key = {job.runtime_spec["node_key"]: job for job in jobs}

    # Downstream starts with nothing resolved but the dependency recorded.
    assert by_key["mpnn"].runtime_spec["input_manifest"]["inputs"] == []
    assert by_key["mpnn"].runtime_spec["input_manifest"]["pending_inputs"] == [
        {"port": "backbone", "from_node": "rfd", "from_port": "backbones"}
    ]

    # The upstream job succeeds and registers an output on the 'backbones' port.
    upstream = by_key["rfd"]
    output = Artifact(
        project_id=project.id,
        created_by=user.id,
        artifact_type="backbone_set",
        filename="design_0.pdb",
        content_type="application/vnd.palm",
        object_key=f"jobs/{upstream.id}/attempt-1/outputs/design_0.pdb",
        size_bytes=20,
        checksum_sha256="e" * 64,
        lineage={"job_id": str(upstream.id), "output_port": "backbones"},
    )
    session.add(output)
    session.flush()
    upstream.status = "succeeded"
    session.add(JobEvent(job_id=upstream.id, event_type="job.succeeded", payload={"artifact_ids": [str(output.id)]}))
    session.flush()

    schedule_ready_jobs(session, submission, workflow)

    downstream = session.get(Job, by_key["mpnn"].id)
    assert downstream is not None
    manifest = downstream.runtime_spec["input_manifest"]
    assert manifest["pending_inputs"] == []
    assert [item["artifact_id"] for item in manifest["inputs"]] == [str(output.id)]
    assert manifest["inputs"][0]["port"] == "backbone"
    # And the job is now dispatchable.
    assert ComputeRepository(session).has_outbox_event("job.dispatch", downstream.id)


def test_downstream_fails_when_upstream_produced_nothing(env) -> None:
    session, project, user = env["session"], env["project"], env["user"]
    producer, consumer = env["producer"], env["consumer"]
    workflow = WorkflowRun(
        project_id=project.id,
        name="chain",
        status="draft",
        graph={"nodes": [{"key": "rfd"}, {"key": "mpnn"}], "edges": [{"source": "rfd", "target": "mpnn"}]},
        created_by=user.id,
    )
    session.add(workflow)
    session.flush()
    session.add_all(
        [
            _node(workflow, "rfd", producer, []),
            _node(
                workflow,
                "mpnn",
                consumer,
                [{"port": "backbone", "source": "upstream", "from_node": "rfd", "from_port": "backbones"}],
            ),
        ]
    )
    session.flush()
    submission, jobs = create_submission(
        session,
        workflow=workflow,
        project=project,
        payload=SubmissionCreate(compute_backend="demo", timeout_minutes=30),
        idempotency_key="dry-key",
        user=user,
    )
    by_key = {job.runtime_spec["node_key"]: job for job in jobs}
    upstream = by_key["rfd"]
    upstream.status = "succeeded"
    session.add(JobEvent(job_id=upstream.id, event_type="job.succeeded", payload={"artifact_ids": []}))
    session.flush()

    schedule_ready_jobs(session, submission, workflow)

    downstream = session.get(Job, by_key["mpnn"].id)
    assert downstream is not None
    # Silently running a model without the data it was wired to consume would be worse
    # than failing.
    assert downstream.status == "failed"
    assert downstream.error_code == "upstream_output_missing"


def test_submit_blocks_on_unsatisfied_required_input(env) -> None:
    session, project, user, consumer = env["session"], env["project"], env["user"], env["consumer"]
    workflow = WorkflowRun(
        project_id=project.id, name="bad", status="draft", graph={"nodes": [], "edges": []}, created_by=user.id
    )
    session.add(workflow)
    session.flush()
    session.add(_node(workflow, "mpnn", consumer, []))
    session.flush()

    with pytest.raises(DomainError) as excinfo:
        create_submission(
            session,
            workflow=workflow,
            project=project,
            payload=SubmissionCreate(compute_backend="demo"),
            idempotency_key="blocked-key",
            user=user,
        )
    assert excinfo.value.error_code == "workflow_preflight_failed"
    assert any(item["code"] == "input_binding_unsatisfied" for item in excinfo.value.errors or [])
    # Nothing was persisted for a rejected submission.
    assert session.scalar(select(JobSubmission).where(JobSubmission.workflow_run_id == workflow.id)) is None


def test_collect_creates_compute_input_lineage_edges(env) -> None:
    """compute_input edges existed in code but never fired, because inputs were empty."""
    from backend_v2.app.compute import tasks

    session, project, user, consumer, artifact = (
        env["session"],
        env["project"],
        env["user"],
        env["consumer"],
        env["artifact"],
    )
    workflow = WorkflowRun(project_id=project.id, name="w", status="draft", graph={}, created_by=user.id)
    session.add(workflow)
    session.flush()
    node = _node(
        workflow, "mpnn", consumer, [{"port": "backbone", "source": "artifact", "artifact_id": str(artifact.id)}]
    )
    session.add(node)
    session.flush()
    submission, jobs = create_submission(
        session,
        workflow=workflow,
        project=project,
        payload=SubmissionCreate(compute_backend="demo"),
        idempotency_key="lineage-key",
        user=user,
    )
    job = jobs[0]

    produced = tasks._persist_outputs(
        session,
        job,
        submission,
        [
            {
                "object_key": f"jobs/{job.id}/attempt-1/outputs/out.fa",
                "checksum_sha256": "f" * 64,
                "size_bytes": 12,
                "filename": "out.fa",
                "content_type": "text/x-fasta",
                "artifact_type": "sequence_set",
                "port": "sequences",
                "metadata": {},
            }
        ],
    )
    session.flush()

    edges = list(
        session.scalars(select(ArtifactLineageEdge).where(ArtifactLineageEdge.child_artifact_id == produced[0].id))
    )
    assert [edge.relation for edge in edges] == ["compute_input"]
    assert edges[0].parent_artifact_id == artifact.id
    assert produced[0].lineage["output_port"] == "sequences"


class _Node:
    """Minimal stand-in: binding_blockers only reads node_key and input_bindings."""

    def __init__(self, bindings: list[dict]) -> None:
        self.node_key = "mpnn"
        self.input_bindings = bindings


class _Plugin:
    def __init__(self, input_ports: list[dict]) -> None:
        self.input_ports = input_ports
        self.output_ports = []


ALTERNATIVE_PORTS = [
    {
        "name": "pdb_path",
        "kind": "protein_structure",
        "accepts": ["backbone_set"],
        "required": True,
        "exclusive_group": "backbone_source",
    },
    {
        "name": "jsonl_path",
        "kind": "params",
        "accepts": [],
        "required": True,
        "exclusive_group": "backbone_source",
    },
]


def _codes(bindings: list[dict]) -> list[str]:
    return [item["code"] for item in binding_blockers(_Node(bindings), _Plugin(ALTERNATIVE_PORTS))]


def test_either_alternative_satisfies_the_group() -> None:
    """ProteinMPNN takes a backbone as either a PDB or a parsed JSONL."""
    for port in ("pdb_path", "jsonl_path"):
        assert _codes([{"port": port, "source": "artifact", "artifact_id": str(uuid.uuid4())}]) == []


def test_binding_neither_alternative_blocks_submission() -> None:
    """Both ports optional would let a node with no backbone reach the cluster."""
    codes = _codes([])
    assert codes == ["input_group_unsatisfied"]
    # The per-port required check must not also fire, or the same problem is reported twice.
    assert "input_binding_unsatisfied" not in codes


def test_binding_both_alternatives_is_rejected() -> None:
    codes = _codes(
        [
            {"port": "pdb_path", "source": "artifact", "artifact_id": str(uuid.uuid4())},
            {"port": "jsonl_path", "source": "artifact", "artifact_id": str(uuid.uuid4())},
        ]
    )
    assert codes == ["input_group_exclusive"]


def test_ungrouped_required_ports_still_checked_individually() -> None:
    plugin = _Plugin([{"name": "solo", "kind": "protein_structure", "accepts": [], "required": True}])
    assert [item["code"] for item in binding_blockers(_Node([]), plugin)] == ["input_binding_unsatisfied"]


def test_submission_rejects_a_binding_whose_artifact_vanished(env) -> None:
    """Preflight cannot see storage state, so resolution is the last line of defence.

    A binding can name an artifact that was deleted after the workflow was authored;
    that must fail the submission rather than dispatch a job with a missing input.
    """
    session, project, user, consumer = env["session"], env["project"], env["user"], env["consumer"]
    workflow = WorkflowRun(
        project_id=project.id, name="gone", status="draft", graph={"nodes": [], "edges": []}, created_by=user.id
    )
    session.add(workflow)
    session.flush()
    session.add(
        _node(
            workflow, "mpnn", consumer, [{"port": "backbone", "source": "artifact", "artifact_id": str(uuid.uuid4())}]
        )
    )
    session.flush()

    with pytest.raises(DomainError) as excinfo:
        create_submission(
            session,
            workflow=workflow,
            project=project,
            payload=SubmissionCreate(compute_backend="demo"),
            idempotency_key=f"vanished-{uuid.uuid4().hex}",
            user=user,
        )
    assert excinfo.value.error_code == "input_binding_unsatisfied"
    assert any(item["code"] == "input_artifact_unavailable" for item in excinfo.value.errors or [])


def test_retry_inherits_the_original_budget_and_handles_missing_timestamps() -> None:
    """A retry is the same work, so it gets the same wall-clock budget - not a new one."""
    from datetime import UTC, datetime, timedelta

    from backend_v2.app.compute.service import DEFAULT_JOB_TIMEOUT, _original_timeout

    created = datetime(2026, 1, 1, tzinfo=UTC)

    granted = Job(created_at=created, timeout_at=created + timedelta(minutes=45))
    assert _original_timeout(granted) == timedelta(minutes=45)

    # Naive timestamps come back from SQLite; they must not raise on subtraction.
    naive = Job(created_at=created.replace(tzinfo=None), timeout_at=(created + timedelta(hours=2)).replace(tzinfo=None))
    assert _original_timeout(naive) == timedelta(hours=2)

    assert _original_timeout(Job(created_at=created, timeout_at=None)) == DEFAULT_JOB_TIMEOUT
    assert _original_timeout(Job(created_at=None, timeout_at=created)) == DEFAULT_JOB_TIMEOUT
    # An implausibly short budget is a data defect, not an instruction to retry for 30s.
    assert _original_timeout(Job(created_at=created, timeout_at=created + timedelta(seconds=30))) == (
        DEFAULT_JOB_TIMEOUT
    )


def test_jobs_without_a_plugin_snapshot_resolve_to_no_plugin() -> None:
    """Nodes predating the registry carry no snapshot; that must not raise."""
    from backend_v2.app.compute.service import _job_plugin

    assert _job_plugin(None, Job(runtime_spec={})) is None
    assert _job_plugin(None, Job(runtime_spec={"plugin_snapshot": None})) is None
    assert _job_plugin(None, Job(runtime_spec={"plugin_snapshot": {}})) is None


def test_every_malformed_binding_shape_is_reported() -> None:
    """Each defect gets its own code, so the UI can point at the offending port."""
    multi = _Plugin(
        [
            {"name": "backbone", "kind": "protein_structure", "accepts": [], "required": False},
            {"name": "extra", "kind": "params", "accepts": [], "required": False, "multiple": True},
        ]
    )
    cases = {
        "input_port_unknown": [{"port": "nope", "source": "artifact", "artifact_id": str(uuid.uuid4())}],
        "input_binding_source_invalid": [{"port": "backbone", "source": "telepathy"}],
        "input_binding_artifact_missing": [{"port": "backbone", "source": "artifact"}],
        "input_binding_upstream_incomplete": [{"port": "backbone", "source": "upstream", "from_node": "rfd"}],
        "input_port_not_multiple": [
            {"port": "backbone", "source": "artifact", "artifact_id": str(uuid.uuid4())},
            {"port": "backbone", "source": "artifact", "artifact_id": str(uuid.uuid4())},
        ],
    }
    for code, bindings in cases.items():
        assert code in [item["code"] for item in binding_blockers(_Node(bindings), multi)], code

    # A port declared `multiple` legitimately takes several bindings.
    repeated = [
        {"port": "extra", "source": "artifact", "artifact_id": str(uuid.uuid4())},
        {"port": "extra", "source": "artifact", "artifact_id": str(uuid.uuid4())},
    ]
    assert binding_blockers(_Node(repeated), multi) == []
    assert binding_blockers(_Node([]), _Plugin([])) == []
    # With no registry plugin there are no declared ports, so every binding reads as
    # unknown. Preflight separately reports the missing plugin as the root cause.
    assert [item["code"] for item in binding_blockers(_Node([{"port": "x", "source": "artifact"}]), None)] == [
        "input_port_unknown"
    ]


def test_ported_edges_are_type_checked() -> None:
    """An edge that names ports must connect ports that can actually carry the data."""
    from backend_v2.app.compute.binding import edge_port_blockers

    producer = _Plugin([])
    producer.output_ports = [
        {"name": "backbones", "kind": "protein_structure", "artifact_type": "backbone_set"},
        {"name": "log", "kind": "tabular", "artifact_type": "score_table"},
    ]
    consumer = _Plugin([{"name": "backbone", "kind": "protein_structure", "accepts": ["backbone_set"]}])
    source, target = _Node([]), _Node([])
    source.node_key = "rfd"

    def codes(source_port: str, target_port: str) -> list[str]:
        return [
            item["code"]
            for item in edge_port_blockers(
                source_node=source,
                target_node=target,
                source_plugin=producer,
                target_plugin=consumer,
                source_port=source_port,
                target_port=target_port,
            )
        ]

    assert codes("backbones", "backbone") == []
    assert codes("missing", "backbone") == ["edge_source_port_unknown"]
    assert codes("backbones", "missing") == ["edge_target_port_unknown"]
    # A score table cannot feed a structure port even though both ports exist.
    assert codes("log", "backbone") == ["edge_ports_incompatible"]


def test_upstream_bindings_are_type_checked_without_ported_graph_edges(env) -> None:
    """The binding that submission stages is authoritative, not a decorative edge."""
    from backend_v2.app.workflows.preflight import evaluate_preflight

    session, project, user, producer, consumer = (
        env["session"],
        env["project"],
        env["user"],
        env["producer"],
        env["consumer"],
    )
    consumer.input_ports = [
        {
            "name": "sequences",
            "kind": "protein_sequence",
            "accepts": ["sequence_set"],
            "required": True,
        }
    ]
    workflow = WorkflowRun(
        project_id=project.id,
        name="unported mismatch",
        status="draft",
        graph={"nodes": [], "edges": [{"source": "rfd", "target": "mpnn"}]},
        created_by=user.id,
    )
    session.add(workflow)
    session.flush()
    session.add(_node(workflow, "rfd", producer, []))
    session.add(
        _node(
            workflow,
            "mpnn",
            consumer,
            [
                {
                    "port": "sequences",
                    "source": "upstream",
                    "from_node": "rfd",
                    "from_port": "backbones",
                }
            ],
        )
    )
    session.flush()

    blockers, _, _ = evaluate_preflight(session, workflow)

    assert [item["code"] for item in blockers].count("edge_ports_incompatible") == 1


def test_unknown_upstream_target_port_is_reported_once(env) -> None:
    """Binding validation owns target spelling; direct type checks must not duplicate it."""
    from backend_v2.app.workflows.preflight import evaluate_preflight

    session, project, user, producer, consumer = (
        env["session"],
        env["project"],
        env["user"],
        env["producer"],
        env["consumer"],
    )
    workflow = WorkflowRun(
        project_id=project.id,
        name="unknown target port",
        status="draft",
        graph={"nodes": [], "edges": [{"source": "rfd", "target": "mpnn"}]},
        created_by=user.id,
    )
    session.add(workflow)
    session.flush()
    session.add(_node(workflow, "rfd", producer, []))
    session.add(
        _node(
            workflow,
            "mpnn",
            consumer,
            [
                {
                    "port": "misspelled",
                    "source": "upstream",
                    "from_node": "rfd",
                    "from_port": "backbones",
                }
            ],
        )
    )
    session.flush()

    blockers, _, _ = evaluate_preflight(session, workflow)

    assert [item["code"] for item in blockers].count("input_port_unknown") == 1
    assert not any(item["code"] == "edge_target_port_unknown" for item in blockers)


def test_plugin_warnings_identify_each_declaration_version(env) -> None:
    """The validation action must target an ID, because plugin keys are versioned."""
    from backend_v2.app.workflows.preflight import evaluate_preflight

    session, project, user, consumer, artifact = (
        env["session"],
        env["project"],
        env["user"],
        env["consumer"],
        env["artifact"],
    )
    older = ModelPlugin(
        plugin_key=consumer.plugin_key,
        plugin_version="0.9.0",
        name=consumer.name,
        container_image="mpnn:0.9.0",
        command="run_old_mpnn.sh",
        input_ports=[STRUCTURE_PORT],
        output_ports=[SEQUENCE_OUT],
        enabled=True,
    )
    session.add(older)
    session.flush()
    workflow = WorkflowRun(
        project_id=project.id,
        name="two plugin declarations",
        status="draft",
        graph={"nodes": [], "edges": []},
        created_by=user.id,
    )
    session.add(workflow)
    session.flush()
    binding = [{"port": "backbone", "source": "artifact", "artifact_id": str(artifact.id)}]
    session.add(_node(workflow, "current", consumer, binding))
    session.add(_node(workflow, "older", older, binding))
    session.flush()

    _, warnings, _ = evaluate_preflight(session, workflow)

    declarations = [item for item in warnings if item["code"] == "plugin_unvalidated"]
    assert {item["plugin_id"] for item in declarations} == {str(consumer.id), str(older.id)}
    assert {item["plugin_version"] for item in declarations} == {"1.0.0", "0.9.0"}


def test_output_port_is_inferred_when_the_runner_declares_none(env) -> None:
    """Plugins predating ports emit no port name; the artifact_type must still route."""
    from backend_v2.app.compute.binding import _artifact_output_port
    from backend_v2.app.registry.ports import parse_output_ports

    ports = parse_output_ports(
        [
            {"name": "designs", "kind": "protein_structure", "artifact_type": "backbone_set", "filename_glob": "*.pdb"},
            {"name": "scores", "kind": "tabular", "artifact_type": "score_table", "filename_glob": "*.sc"},
        ]
    )
    project, user = env["project"], env["user"]

    def artifact(artifact_type: str, filename: str, lineage: dict) -> Artifact:
        return Artifact(
            project_id=project.id,
            created_by=user.id,
            artifact_type=artifact_type,
            filename=filename,
            content_type="application/octet-stream",
            object_key=f"k/{uuid.uuid4()}",
            size_bytes=1,
            checksum_sha256="a" * 64,
            lineage=lineage,
        )

    # An explicit port always wins over inference.
    assert _artifact_output_port(artifact("backbone_set", "x.pdb", {"output_port": "declared"}), ports) == "declared"
    assert _artifact_output_port(artifact("backbone_set", "d.pdb", {}), ports) == "designs"
    assert _artifact_output_port(artifact("score_table", "s.sc", {}), ports) == "scores"
    # Unknown artifact type routes nowhere rather than to an arbitrary port.
    assert _artifact_output_port(artifact("mystery", "m.bin", {}), ports) is None


def _manual_node(workflow, key) -> WorkflowNode:
    """A stage that is part of the route but is not run by this platform."""
    return WorkflowNode(
        workflow_run_id=workflow.id,
        node_key=key,
        node_type="target_intake",
        model_plugin="Imported project inputs",
        model_plugin_id=None,
        status="succeeded",
        parameters={},
        input_bindings=[],
        execution_mode="manual",
    )


def test_manual_node_does_not_block_preflight(env) -> None:
    """Target intake and candidate review have no plugin and never will.

    Requiring one made whole workflows unsubmittable, which is why the sweet-protein
    routes ran as hand-written LSF instead of through the platform.
    """
    from backend_v2.app.workflows.preflight import evaluate_preflight

    session, project, user, consumer, artifact = (
        env["session"],
        env["project"],
        env["user"],
        env["consumer"],
        env["artifact"],
    )
    workflow = WorkflowRun(
        project_id=project.id, name="mixed", status="draft", graph={"nodes": [], "edges": []}, created_by=user.id
    )
    session.add(workflow)
    session.flush()
    session.add(_manual_node(workflow, "target_input"))
    session.add(
        _node(workflow, "mpnn", consumer, [{"port": "backbone", "source": "artifact", "artifact_id": str(artifact.id)}])
    )
    session.flush()

    blockers, _, checks = evaluate_preflight(session, workflow)

    assert [item["code"] for item in blockers] == []
    # Counted, not warned about. A manual stage is the intended state for target intake
    # and candidate review; one warning per such node buried the real blockers.
    assert checks["manual_nodes"] == ["target_input"]
    assert checks["dispatch_node_count"] == 1


def test_manual_target_bindings_and_ported_edges_do_not_block_preflight(env) -> None:
    """A review stage can annotate what it reads without becoming a submitted model."""
    from backend_v2.app.workflows.preflight import evaluate_preflight

    session, project, user, producer = (
        env["session"],
        env["project"],
        env["user"],
        env["producer"],
    )
    workflow = WorkflowRun(
        project_id=project.id,
        name="manual review binding",
        status="draft",
        graph={
            "nodes": [],
            "edges": [
                {
                    "source": "rfd",
                    "target": "review",
                    "source_port": "backbones",
                    "target_port": "structures",
                }
            ],
        },
        created_by=user.id,
    )
    session.add(workflow)
    session.flush()
    session.add(_node(workflow, "rfd", producer, []))
    review = _manual_node(workflow, "review")
    review.input_bindings = [
        {
            "port": "structures",
            "source": "upstream",
            "from_node": "rfd",
            "from_port": "backbones",
        }
    ]
    session.add(review)
    session.flush()

    blockers, _, _ = evaluate_preflight(session, workflow)

    assert blockers == []


def test_manual_node_produces_no_job(env) -> None:
    session, project, user, consumer, artifact = (
        env["session"],
        env["project"],
        env["user"],
        env["consumer"],
        env["artifact"],
    )
    workflow = WorkflowRun(
        project_id=project.id, name="mixed", status="draft", graph={"nodes": [], "edges": []}, created_by=user.id
    )
    session.add(workflow)
    session.flush()
    session.add(_manual_node(workflow, "target_input"))
    session.add(
        _node(workflow, "mpnn", consumer, [{"port": "backbone", "source": "artifact", "artifact_id": str(artifact.id)}])
    )
    session.flush()

    _, jobs = create_submission(
        session,
        workflow=workflow,
        project=project,
        payload=SubmissionCreate(compute_backend="demo"),
        idempotency_key="manual-mix-key",
        user=user,
    )

    # One job for the model, none for the human step - dispatching that would report a
    # review stage as a failed cluster job.
    assert [job.model_plugin for job in jobs] == [consumer.plugin_key]


def test_an_all_manual_workflow_is_rejected(env) -> None:
    """Otherwise submission succeeds, creates zero jobs, and reports success."""
    from backend_v2.app.workflows.preflight import evaluate_preflight

    session, project, user = env["session"], env["project"], env["user"]
    workflow = WorkflowRun(
        project_id=project.id, name="all manual", status="draft", graph={"nodes": [], "edges": []}, created_by=user.id
    )
    session.add(workflow)
    session.flush()
    session.add(_manual_node(workflow, "target_input"))
    session.add(_manual_node(workflow, "candidate_review"))
    session.flush()

    blockers, _, _ = evaluate_preflight(session, workflow)

    assert any(item["code"] == "workflow_all_manual" for item in blockers)


def test_explicitly_unready_route_is_rejected_once(env) -> None:
    """Canvas metadata is a real submission interlock, not an advisory label."""
    from backend_v2.app.workflows.preflight import evaluate_preflight

    session, project, user, consumer, artifact = (
        env["session"],
        env["project"],
        env["user"],
        env["consumer"],
        env["artifact"],
    )
    workflow = WorkflowRun(
        project_id=project.id,
        name="missing route artifacts",
        status="draft",
        graph={"nodes": [], "edges": []},
        created_by=user.id,
    )
    session.add(workflow)
    session.flush()
    for key in ("rfd", "mpnn"):
        route_node = _node(
            workflow,
            key,
            consumer,
            [{"port": "backbone", "source": "artifact", "artifact_id": str(artifact.id)}],
        )
        route_node.parameters = {"execution_ready": False}
        session.add(route_node)
    session.flush()

    blockers, _, _ = evaluate_preflight(session, workflow)

    gate = [item for item in blockers if item["code"] == "route_not_execution_ready"]
    assert len(gate) == 1
    assert gate[0]["node_keys"] == ["rfd", "mpnn"]
