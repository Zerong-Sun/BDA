"""Compute outcomes, not manual success claims, advance supervised campaigns."""

from contextlib import contextmanager

import pytest
from backend_v2.app.autopilot import adapters, tasks
from backend_v2.app.autopilot.models import AutopilotLedgerEntry
from backend_v2.app.compute.models import Job, JobSubmission
from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun
from backend_v2.tests.test_autopilot_lifecycle import _campaign, _stages
from backend_v2.tests.test_autopilot_lifecycle import session as session  # noqa: F401
from sqlalchemy import select


def _execution(session, monkeypatch):
    campaign, project, user = _campaign(session, stage_keys=["compute", "review"])
    stage, review = _stages(session, campaign)
    adapters.ensure_stage_resource(session, campaign, stage)
    stage.status = "ready"
    run = session.get(WorkflowRun, stage.resource_id)
    run.status = "running"
    submission = JobSubmission(
        workflow_run_id=run.id, project_id=project.id, created_by=user.id, compute_backend="demo"
    )
    node = WorkflowNode(workflow_run_id=run.id, node_key="fixture", node_type="model", model_plugin="fixture")
    session.add_all([submission, node])
    session.flush()
    job = Job(
        submission_id=submission.id,
        workflow_run_id=run.id,
        workflow_node_id=node.id,
        project_id=project.id,
        compute_backend="demo",
        model_plugin="fixture",
        status="succeeded",
    )
    session.add(job)
    session.flush()

    @contextmanager
    def scope():
        yield session
        session.flush()

    monkeypatch.setattr(tasks, "session_scope", scope)
    return campaign, stage, review, run, job


def test_all_branches_must_finish_and_delivery_is_idempotent(session, monkeypatch):
    _, stage, review, run, job = _execution(session, monkeypatch)
    assert tasks.workflow_stage_settled.run(str(job.id))["status"] == "waiting_for_workflow"
    assert stage.status == "ready" and review.status == "pending"
    run.status = "succeeded"
    session.flush()
    result = tasks.workflow_stage_settled.run(str(job.id))
    assert result["settled_stage_ids"] == [str(stage.id)]
    assert stage.status == "succeeded" and review.status == "ready"
    assert tasks.workflow_stage_settled.run(str(job.id))["settled_stage_ids"] == []
    events = list(
        session.scalars(select(AutopilotLedgerEntry).where(AutopilotLedgerEntry.event_type == "stage.settled"))
    )
    assert len(events) == 1


@pytest.mark.parametrize("outcome", ["failed", "cancelled"])
def test_failed_or_cancelled_compute_does_not_advance_to_review(session, monkeypatch, outcome):
    _, stage, review, run, job = _execution(session, monkeypatch)
    run.status = outcome
    session.flush()
    tasks.workflow_stage_settled.run(str(job.id))
    assert stage.status == outcome and review.status == "pending"


@pytest.mark.parametrize("status", ["cancelled", "manual_takeover"])
def test_takeover_and_cancel_stop_late_workflow_events(session, monkeypatch, status):
    campaign, stage, review, run, job = _execution(session, monkeypatch)
    campaign.status, run.status = status, "succeeded"
    session.flush()
    assert tasks.workflow_stage_settled.run(str(job.id))["settled_stage_ids"] == []
    assert stage.status == "ready" and review.status == "pending"


def test_cancel_requests_cancellation_for_submitted_workflow_jobs(session, monkeypatch):
    from backend_v2.app.autopilot.service import cancel_campaign
    from backend_v2.app.compute.models import OutboxEvent
    from backend_v2.app.identity.models import User

    campaign, stage, _, _, job = _execution(session, monkeypatch)
    job.status = "running"
    session.flush()
    user = session.get(User, campaign.created_by)
    cancel_campaign(session, campaign, user)
    session.flush()
    assert job.status == "cancel_requested" and stage.status == "cancelled"
    events = list(session.scalars(select(OutboxEvent).where(OutboxEvent.topic == "job.cancel")))
    assert len(events) == 1 and events[0].payload["job_id"] == str(job.id)
