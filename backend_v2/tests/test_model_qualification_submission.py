"""An explicit checkpoint/use restriction reaches the actual submission gate."""
from __future__ import annotations

import pytest
from backend_v2.app.compute.models import Job, JobSubmission
from backend_v2.app.compute.schemas import SubmissionCreate
from backend_v2.app.compute.service import create_submission
from backend_v2.app.core.problem import DomainError
from backend_v2.app.workflows.models import WorkflowRun
from backend_v2.app.workflows.preflight import evaluate_preflight
from backend_v2.tests.test_compute_binding import _node
from backend_v2.tests.test_compute_binding import env as binding_env
from backend_v2.tests.test_extension_readiness import _review
from sqlalchemy import func, select


@pytest.fixture(name="env")
def configured_environment():
    yield from binding_env.__wrapped__()


def _workflow(env):
    session = env["session"]
    workflow = WorkflowRun(project_id=env["project"].id, name="Qualification gate", created_by=env["user"].id,
                           graph={"nodes": [{"key": "model"}], "edges": []})
    session.add(workflow)
    session.flush()
    session.add(_node(workflow, "model", env["producer"], []))
    session.flush()
    return workflow


def test_legacy_missing_qualification_remains_warning_and_can_create_demo_submission(env):
    workflow = _workflow(env)
    blockers, warnings, _ = evaluate_preflight(env["session"], workflow, compute_backend="demo")
    assert not blockers
    assert "model_qualification_missing" in {item["code"] for item in warnings}
    submission, jobs = create_submission(env["session"], workflow=workflow, project=env["project"],
                                        payload=SubmissionCreate(compute_backend="demo"),
                                        idempotency_key="legacy-with-warning", user=env["user"])
    assert submission.id and len(jobs) == 1


@pytest.mark.parametrize("overrides,expected", [
    ({"review_status": "pending"}, "model_qualification_not_approved"),
    ({"license_mode": "research_only", "intended_use": "commercial", "allowed_uses": ["commercial"]}, "model_qualification_research_only"),
])
def test_explicit_checkpoint_restriction_blocks_preflight_and_creates_no_jobs(env, overrides, expected):
    session, plugin = env["session"], env["producer"]
    plugin.resources = {"scientific_qualification": _review(plugin_key=plugin.plugin_key, plugin_version=plugin.plugin_version, **overrides)}
    session.flush()
    workflow = _workflow(env)
    blockers, _, _ = evaluate_preflight(session, workflow, compute_backend="demo")
    assert expected in {item["code"] for item in blockers}
    with pytest.raises(DomainError) as failure:
        create_submission(session, workflow=workflow, project=env["project"],
                          payload=SubmissionCreate(compute_backend="demo"), idempotency_key="must-block", user=env["user"])
    assert failure.value.error_code == "workflow_preflight_failed"
    assert expected in {item["code"] for item in failure.value.errors}
    assert session.scalar(select(func.count(JobSubmission.id))) == 0
    assert session.scalar(select(func.count(Job.id))) == 0
