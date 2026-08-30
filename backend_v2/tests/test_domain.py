import uuid
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.compute.models import Job, JobSubmission
from backend_v2.app.compute.service import transition_job
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.deps import require_command
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun
from backend_v2.app.workflows.schemas import WorkflowCreate, WorkflowEdgeInput, WorkflowNodeInput
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def session() -> Iterator[Session]:
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as opened:
        yield opened
    drop_all(engine, Base.metadata)


def test_workflow_graph_rejects_cycles() -> None:
    nodes = [
        WorkflowNodeInput(key="a", node_type="model", model_plugin="one"),
        WorkflowNodeInput(key="b", node_type="model", model_plugin="two"),
    ]
    with pytest.raises(ValueError, match="acyclic"):
        WorkflowCreate(
            name="cycle",
            nodes=nodes,
            edges=[WorkflowEdgeInput(source="a", target="b"), WorkflowEdgeInput(source="b", target="a")],
        )


def _owner_and_project(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    """The rows a workflow run cannot exist without.

    These used to be invented ids pointing at nothing. With foreign keys
    unenforced that inserted fine, so the tests were exercising orphan rows the
    real database would reject.
    """
    user = User(username=f"domain-{uuid.uuid4().hex[:8]}", display_name="D", role="admin", enabled=True)
    organization = Organization(name=f"Domain Org {uuid.uuid4().hex[:8]}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name="domain", project_type="protein_design"
    )
    session.add(project)
    session.flush()
    return project.id, user.id


def _node_and_job(session: Session, *, attempt_number: int = 1) -> tuple[WorkflowNode, Job]:
    project_id, user_id = _owner_and_project(session)
    workflow_run = WorkflowRun(
        project_id=project_id, name="domain run", status="draft", created_by=user_id
    )
    session.add(workflow_run)
    session.flush()
    workflow_run_id = workflow_run.id
    node = WorkflowNode(
        id=uuid.uuid4(),
        workflow_run_id=workflow_run_id,
        node_key="design",
        node_type="model",
        model_plugin="demo",
        status="draft",
        version=1,
    )
    session.add(node)
    session.flush()
    submission = JobSubmission(
        workflow_run_id=workflow_run_id,
        project_id=project_id,
        created_by=user_id,
        status="pending",
        compute_backend="demo",
    )
    session.add(submission)
    session.flush()
    job = Job(
        id=uuid.uuid4(),
        submission_id=submission.id,
        workflow_run_id=workflow_run_id,
        workflow_node_id=node.id,
        project_id=project_id,
        compute_backend="demo",
        model_plugin="demo",
        status="pending",
        attempt_number=attempt_number,
        version=1,
    )
    session.add(job)
    session.flush()
    return node, job


def test_job_state_machine_rejects_illegal_transition(session: Session) -> None:
    _, job = _node_and_job(session)
    transition_job(session, job, "dispatching")
    assert job.status == "dispatching"
    with pytest.raises(DomainError, match="cannot transition"):
        transition_job(session, job, "succeeded")


def test_job_transition_mirrors_status_onto_its_node(session: Session) -> None:
    """The node column used to stay 'draft' forever, so the canvas and the Copilot's
    project context both reported finished work as not started."""
    node, job = _node_and_job(session)
    assert node.status == "draft"

    transition_job(session, job, "dispatching")
    assert node.status == "dispatching"
    assert node.version == 2

    job.error_code = "compute_failed"
    job.error_message = "boom"
    transition_job(session, job, "failed")
    assert node.status == "failed"
    assert node.error_message == "boom"


def test_node_status_follows_the_newest_attempt_not_the_replaced_one(session: Session) -> None:
    """A retry must not be overwritten by the failed attempt it replaced."""
    node, first = _node_and_job(session, attempt_number=1)
    transition_job(session, first, "dispatching")
    transition_job(session, first, "failed")
    assert node.status == "failed"

    retry = Job(
        id=uuid.uuid4(),
        submission_id=first.submission_id,
        workflow_run_id=first.workflow_run_id,
        workflow_node_id=node.id,
        project_id=first.project_id,
        compute_backend="demo",
        model_plugin="demo",
        status="pending",
        attempt_number=2,
        version=1,
    )
    session.add(retry)
    session.flush()
    transition_job(session, retry, "dispatching")
    assert node.status == "dispatching"

    # The superseded attempt may still emit terminal transitions; they must not win.
    stale = session.get(Job, first.id)
    assert stale is not None
    stale.status = "collecting"
    transition_job(session, stale, "succeeded")
    assert node.status == "dispatching"


def test_viewer_cannot_execute_commands() -> None:
    viewer = User(username="viewer", display_name="Viewer", role="viewer")
    with pytest.raises(DomainError, match="read-only"):
        require_command(viewer)
