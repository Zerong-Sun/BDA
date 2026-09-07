"""Submission concurrency requires real row locks, not a SQLite substitute."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from backend_v2.app.compute.models import Job, JobSubmission, OutboxEvent
from backend_v2.app.compute.schemas import SubmissionCreate
from backend_v2.app.compute.service import create_submission
from backend_v2.app.core.database import SessionFactory
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.registry.models import ModelPlugin
from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun
from sqlalchemy import delete, func, select

pytestmark = pytest.mark.skipif(os.getenv("BDA_V2_RUN_DB_TESTS") != "1", reason="PostgreSQL integration test disabled")


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_submissions_create_one_submission_and_dispatch(same_key):
    token = uuid.uuid4().hex
    with SessionFactory.begin() as session:
        user = User(username="guided-" + token, display_name="Guided review", role="admin", enabled=True)
        org = Organization(name="Guided review " + token)
        session.add_all([user, org])
        session.flush()
        project = Project(organization_id=org.id, owner_id=user.id, name="Concurrency test", project_type="design")
        plugin = ModelPlugin(
            plugin_key="test-" + token,
            plugin_version="1",
            name="Concurrent test " + token,
            command="true",
            container_image="test:1",
            enabled=True,
        )
        session.add_all([project, plugin])
        session.flush()
        workflow = WorkflowRun(
            project_id=project.id,
            created_by=user.id,
            name="Concurrent submit",
            status="draft",
            graph={"nodes": [{"key": "only"}], "edges": []},
        )
        session.add(workflow)
        session.flush()
        session.add(
            WorkflowNode(
                workflow_run_id=workflow.id,
                node_key="only",
                node_type="model",
                model_plugin=plugin.name,
                model_plugin_id=plugin.id,
                parameters={},
                status="draft",
            )
        )
        ids = user.id, project.id, workflow.id
    barrier = Barrier(2)

    def submit(index):
        with SessionFactory() as session:
            user, project, workflow = (
                session.get(model, key) for model, key in zip((User, Project, WorkflowRun), ids, strict=True)
            )
            version = workflow.version
            barrier.wait(timeout=15)
            try:
                submission, _ = create_submission(
                    session,
                    workflow=workflow,
                    project=project,
                    user=user,
                    payload=SubmissionCreate(compute_backend="demo", workflow_version=version),
                    idempotency_key=token if same_key else f"{token}-{index}",
                )
                session.commit()
                return str(submission.id)
            except DomainError as exc:
                session.rollback()
                assert exc.status_code in {409, 412}
                return "rejected"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, range(2)))
        if same_key:
            assert results[0] == results[1] != "rejected"
        else:
            assert results.count("rejected") == 1
        with SessionFactory() as session:
            assert (
                session.scalar(
                    select(func.count()).select_from(JobSubmission).where(JobSubmission.workflow_run_id == ids[2])
                )
                == 1
            )
            jobs = list(session.scalars(select(Job).where(Job.workflow_run_id == ids[2])))
            assert len(jobs) == 1
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(OutboxEvent)
                    .where(OutboxEvent.aggregate_id == jobs[0].id, OutboxEvent.topic == "job.dispatch")
                )
                == 1
            )
    finally:
        # Reuse the schema's cascading project teardown; this test only owns its fixture.
        with SessionFactory.begin() as session:
            job_ids = select(Job.id).where(Job.workflow_run_id == ids[2])
            session.execute(delete(OutboxEvent).where(OutboxEvent.aggregate_id.in_(job_ids)))
            session.execute(delete(Project).where(Project.id == ids[1]))
            session.execute(delete(ModelPlugin).where(ModelPlugin.plugin_key == "test-" + token))
            session.execute(delete(User).where(User.id == ids[0]))
            session.execute(delete(Organization).where(Organization.name == "Guided review " + token))
