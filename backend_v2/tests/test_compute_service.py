from __future__ import annotations

from collections.abc import Generator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.compute import service as compute_service
from backend_v2.app.compute.models import Job, OutboxEvent
from backend_v2.app.compute.schemas import SubmissionCreate
from backend_v2.app.compute.service import (
    create_submission,
    request_cancel,
    retry_job,
    schedule_ready_jobs,
    transition_job,
)
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.app.registry.models import ModelPlugin
from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun
from backend_v2.tests._sqlite import enforce_foreign_keys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


@pytest.fixture
def compute_session() -> Generator[tuple[Session, User, Project, WorkflowRun]]:
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://"))
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = User(username="compute", display_name="Compute", role="admin", enabled=True)
        org = Organization(name="Compute Org")
        session.add_all([user, org])
        session.flush()
        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
        project = Project(organization_id=org.id, owner_id=user.id, name="Compute project", project_type="design")
        session.add(project)
        session.flush()
        session.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
        workflow = WorkflowRun(
            project_id=project.id,
            name="workflow",
            status="draft",
            graph={"nodes": [{"key": "a"}, {"key": "b"}], "edges": [{"source": "a", "target": "b"}]},
            created_by=user.id,
        )
        session.add(workflow)
        session.flush()
        # Submission now requires every node to reference a registry plugin, so the
        # runtime that executes is always the one that was snapshotted.
        plugin = ModelPlugin(
            plugin_key="demo",
            plugin_version="1.0.0",
            name="Demo",
            container_image="demo:1.0.0",
            command="run.sh",
            enabled=True,
        )
        session.add(plugin)
        session.flush()
        session.add_all(
            [
                WorkflowNode(
                    workflow_run_id=workflow.id,
                    node_key=key,
                    node_type="model",
                    model_plugin="demo",
                    model_plugin_id=plugin.id,
                    status="draft",
                    parameters={},
                )
                for key in ("a", "b")
            ]
        )
        session.commit()
        yield session, user, project, workflow
    engine.dispose()


def test_submission_idempotency_dependency_progress_and_retry(compute_session) -> None:
    session, user, project, workflow = compute_session
    payload = SubmissionCreate(compute_backend="demo", timeout_minutes=10)
    submission, jobs = create_submission(
        session, workflow=workflow, project=project, payload=payload, idempotency_key="key", user=user
    )
    assert len(jobs) == 2
    assert jobs[0].runtime_spec["input_manifest_key"].startswith("jobs/")
    assert len(list(session.scalars(select(OutboxEvent)))) == 1
    same, same_jobs = create_submission(
        session, workflow=workflow, project=project, payload=payload, idempotency_key="key", user=user
    )
    assert same.id == submission.id and len(same_jobs) == 2
    with pytest.raises(DomainError, match="another payload"):
        create_submission(
            session,
            workflow=workflow,
            project=project,
            payload=SubmissionCreate(compute_backend="demo", timeout_minutes=11),
            idempotency_key="key",
            user=user,
        )

    by_node = {job.runtime_spec["node_key"]: job for job in jobs}
    transition_job(session, by_node["a"], "dispatching")
    transition_job(session, by_node["a"], "queued")
    transition_job(session, by_node["a"], "running")
    transition_job(session, by_node["a"], "collecting")
    transition_job(session, by_node["a"], "succeeded")
    schedule_ready_jobs(session, submission, workflow)
    assert len(list(session.scalars(select(OutboxEvent).where(OutboxEvent.topic == "job.dispatch")))) == 2

    transition_job(session, by_node["b"], "failed")
    schedule_ready_jobs(session, submission, workflow)
    assert submission.status == "failed" and workflow.status == "failed"
    retried = retry_job(session, by_node["b"], project, user)
    assert retried.attempt_number == 2
    assert f"attempt-{retried.attempt_number}" in retried.runtime_spec["output_manifest_key"]


def test_background_status_changes_bump_the_workflow_version(compute_session) -> None:
    """The version is the ETag. A background transition that left it alone meant a client
    holding a pre-submit ETag still satisfied If-Match after the run had finished."""
    session, user, project, workflow = compute_session
    draft_version = workflow.version

    submission, jobs = create_submission(
        session,
        workflow=workflow,
        project=project,
        payload=SubmissionCreate(compute_backend="demo"),
        idempotency_key="etag",
        user=user,
    )
    assert workflow.status == "queued"
    queued_version = workflow.version
    assert queued_version > draft_version

    by_node = {job.runtime_spec["node_key"]: job for job in jobs}
    transition_job(session, by_node["a"], "dispatching")
    schedule_ready_jobs(session, submission, workflow)
    assert workflow.status == "running"
    running_version = workflow.version
    assert running_version > queued_version

    # Re-running the scheduler without a status change must not churn the version,
    # or every poll would invalidate every client's ETag.
    schedule_ready_jobs(session, submission, workflow)
    assert workflow.version == running_version

    for step in ("queued", "running", "collecting", "succeeded"):
        transition_job(session, by_node["a"], step)
    transition_job(session, by_node["b"], "dispatching")
    for step in ("queued", "running", "collecting", "succeeded"):
        transition_job(session, by_node["b"], step)
    schedule_ready_jobs(session, submission, workflow)
    assert workflow.status == "succeeded"
    assert workflow.version > running_version


def test_transition_cancel_terminal_and_failure_propagation(compute_session) -> None:
    session, user, project, workflow = compute_session
    submission, jobs = create_submission(
        session,
        workflow=workflow,
        project=project,
        payload=SubmissionCreate(compute_backend="demo"),
        idempotency_key="second",
        user=user,
    )
    first, second = jobs
    with pytest.raises(DomainError, match="cannot transition"):
        transition_job(session, first, "succeeded")
    assert request_cancel(session, first, project, user) is first
    transition_job(session, first, "failed")
    schedule_ready_jobs(session, submission, workflow)
    assert second.status == "failed" and second.error_code == "upstream_failed"
    assert request_cancel(session, first, project, user) is first
    with pytest.raises(DomainError, match="Only failed"):
        retry_job(session, Job(status="running"), project, user)


def test_empty_workflow_is_rejected(compute_session) -> None:
    session, user, project, _workflow = compute_session
    empty = WorkflowRun(project_id=project.id, name="empty", status="draft", graph={}, created_by=user.id)
    session.add(empty)
    session.flush()
    with pytest.raises(DomainError, match="no executable nodes"):
        create_submission(
            session,
            workflow=empty,
            project=project,
            payload=SubmissionCreate(compute_backend="demo"),
            idempotency_key="empty",
            user=user,
        )


def test_lsf_submission_requires_configured_ssh_host(monkeypatch, compute_session) -> None:
    session, user, project, workflow = compute_session
    monkeypatch.setattr(
        compute_service,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {"compute_backend": "docker", "is_production": False, "lsf_ssh_host": ""},
        )(),
    )
    with pytest.raises(DomainError, match="configured SSH host"):
        create_submission(
            session,
            workflow=workflow,
            project=project,
            payload=SubmissionCreate(compute_backend="lsf"),
            idempotency_key="lsf-unconfigured",
            user=user,
        )


def test_plugin_snapshot_production_guard_and_terminal_success(monkeypatch, compute_session) -> None:
    session, user, project, workflow = compute_session
    node = session.scalar(select(WorkflowNode).where(WorkflowNode.workflow_run_id == workflow.id))
    plugin = ModelPlugin(
        plugin_key="safe-model",
        plugin_version="1",
        name="Safe model",
        container_image="registry/model:1",
        command="run",
        parameter_schema={},
        output_schema={},
        enabled=True,
    )
    session.add(plugin)
    session.flush()
    assert node is not None
    node.model_plugin_id = plugin.id
    submission, jobs = create_submission(
        session,
        workflow=workflow,
        project=project,
        payload=SubmissionCreate(compute_backend="demo"),
        idempotency_key="plugin",
        user=user,
    )
    assert jobs[0].runtime_spec["plugin_snapshot"]["key"] == "safe-model"
    for job in jobs:
        job.status = "succeeded"
    schedule_ready_jobs(session, submission, workflow)
    assert submission.status == "succeeded"
    jobs[0].status = "running"
    jobs[1].status = "pending"
    schedule_ready_jobs(session, submission, workflow)
    assert submission.status == "running"

    monkeypatch.setattr(compute_service, "get_settings", lambda: type("S", (), {"is_production": True})())
    fresh = WorkflowRun(project_id=project.id, name="prod", status="draft", graph={}, created_by=user.id)
    session.add(fresh)
    session.flush()
    session.add(
        WorkflowNode(
            workflow_run_id=fresh.id,
            node_key="prod",
            node_type="model",
            model_plugin="demo",
            status="draft",
            parameters={},
        )
    )
    session.flush()
    with pytest.raises(DomainError, match="production"):
        create_submission(
            session,
            workflow=fresh,
            project=project,
            payload=SubmissionCreate(compute_backend="demo"),
            idempotency_key="prod",
            user=user,
        )


def test_every_terminal_state_emits_an_event_not_only_success(compute_session) -> None:
    """Success-only emission left every consumer polling.

    A campaign round whose job failed stayed "running" until some other job in
    the same submission happened to succeed, and an agent waiting on a job that
    died had nothing to wake it. The wait is now on the terminal transition
    itself, which is symmetric across succeeded, failed and cancelled.
    """
    session, user, project, workflow = compute_session
    submission, jobs = create_submission(
        session,
        project=project,
        workflow=workflow,
        payload=SubmissionCreate(compute_backend="docker"),
        idempotency_key="terminal-events",
        user=user,
    )
    first, second = jobs[0], jobs[1]

    transition_job(session, first, "failed")
    transition_job(session, second, "cancelled")

    settled = list(session.scalars(select(OutboxEvent).where(OutboxEvent.topic == "job.settled")))
    assert {event.aggregate_id for event in settled} == {first.id, second.id}
    assert {event.payload["status"] for event in settled} == {"failed", "cancelled"}
    assert {event.payload["project_id"] for event in settled} == {str(project.id)}


def test_a_non_terminal_transition_emits_nothing(compute_session) -> None:
    session, user, project, workflow = compute_session
    submission, jobs = create_submission(
        session,
        project=project,
        workflow=workflow,
        payload=SubmissionCreate(compute_backend="docker"),
        idempotency_key="non-terminal",
        user=user,
    )
    transition_job(session, jobs[0], "dispatching")
    transition_job(session, jobs[0], "queued")

    assert not list(session.scalars(select(OutboxEvent).where(OutboxEvent.topic == "job.settled")))
