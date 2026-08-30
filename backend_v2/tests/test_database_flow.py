import json
import os
from pathlib import Path

import pytest
from backend_v2.app.compute.models import OutboxEvent
from backend_v2.app.compute.schemas import SubmissionCreate
from backend_v2.app.compute.service import create_submission, schedule_ready_jobs, transition_job
from backend_v2.app.core.database import SessionFactory
from backend_v2.app.identity.models import Organization
from backend_v2.app.identity.service import bootstrap_admin
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.app.registry.models import ModelPlugin
from backend_v2.app.research.models import ResearchFinding
from backend_v2.app.research.package_import import import_research_package
from backend_v2.app.research.schemas import ResearchPackageImportCreate
from backend_v2.app.workflows.schemas import WorkflowCreate, WorkflowEdgeInput, WorkflowNodeInput
from backend_v2.app.workflows.service import create_workflow
from sqlalchemy import select

pytestmark = pytest.mark.skipif(os.getenv("BDA_V2_RUN_DB_TESTS") != "1", reason="PostgreSQL integration test disabled")


def test_dag_dispatches_only_dependency_ready_jobs() -> None:
    session = SessionFactory()
    transaction = session.begin()
    try:
        user = bootstrap_admin(session, username="integration-admin", password="StrongPass123")
        organization = session.scalar(select(Organization).where(Organization.legacy_id == "bootstrap-default"))
        assert organization is not None
        project = Project(
            organization_id=organization.id,
            owner_id=user.id,
            name="DAG test",
            project_type="discovery",
        )
        session.add(project)
        session.flush()
        session.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
        # Submission requires every node to reference a registry plugin, so the runtime
        # that executes is always the one that was snapshotted.
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
        workflow = create_workflow(
            session,
            project,
            WorkflowCreate(
                name="two steps",
                nodes=[
                    WorkflowNodeInput(
                        key="root", node_type="model", model_plugin="demo", model_plugin_id=plugin.id
                    ),
                    WorkflowNodeInput(
                        key="child", node_type="model", model_plugin="demo", model_plugin_id=plugin.id
                    ),
                ],
                edges=[WorkflowEdgeInput(source="root", target="child")],
            ),
            user,
        )
        submission, jobs = create_submission(
            session,
            workflow=workflow,
            project=project,
            payload=SubmissionCreate(compute_backend="demo"),
            idempotency_key="integration-key",
            user=user,
        )
        root = next(item for item in jobs if item.runtime_spec["node_key"] == "root")
        child = next(item for item in jobs if item.runtime_spec["node_key"] == "child")
        session.flush()
        queued_ids = set(session.scalars(select(OutboxEvent.aggregate_id).where(OutboxEvent.topic == "job.dispatch")))
        assert root.id in queued_ids
        assert child.id not in queued_ids

        for state in ("dispatching", "queued", "running", "collecting", "succeeded"):
            transition_job(session, root, state)
        schedule_ready_jobs(session, submission, workflow)
        session.flush()
        queued_ids = set(session.scalars(select(OutboxEvent.aggregate_id).where(OutboxEvent.topic == "job.dispatch")))
        assert child.id in queued_ids
    finally:
        transaction.rollback()
        session.close()


def test_research_package_import_runs_against_postgresql() -> None:
    package_path = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "public"
        / "research-packages"
        / "pd1-demo-v1.json"
    )
    package = json.loads(package_path.read_text())
    session = SessionFactory()
    transaction = session.begin()
    try:
        user = bootstrap_admin(session, username="package-integration-admin", password="StrongPass123")
        organization = session.scalar(select(Organization).where(Organization.legacy_id == "bootstrap-default"))
        assert organization is not None

        result = import_research_package(
            session,
            ResearchPackageImportCreate(organization_id=organization.id, package=package),
            user,
        )
        session.flush()

        assert result.counts["projects"] == 1
        assert result.counts["candidates"] == 0
        assert result.counts["findings"] == 4
        assert result.counts["reference_links"] == 12
    finally:
        transaction.rollback()
        session.close()


def test_package_import_adopts_a_user_project_with_matching_claim_lineage() -> None:
    package_path = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "public"
        / "research-packages"
        / "pd1-demo-v1.json"
    )
    package = json.loads(package_path.read_text())
    session = SessionFactory()
    transaction = session.begin()
    try:
        user = bootstrap_admin(session, username="claim-lineage-admin", password="StrongPass123")
        organization = session.scalar(select(Organization).where(Organization.legacy_id == "bootstrap-default"))
        assert organization is not None

        # A copilot/user-created project that already carries one of this package's
        # claims (by claim_id, not by name) should be reused rather than duplicated.
        adopted = Project(
            organization_id=organization.id,
            owner_id=user.id,
            name="My own checkpoint project",
            project_type="protein_design",
        )
        session.add(adopted)
        session.flush()
        session.add(ProjectMember(project_id=adopted.id, user_id=user.id, role="owner"))
        session.add(
            ResearchFinding(
                project_id=adopted.id,
                finding_type="claim",
                title="Existing claim",
                content="Captured before the package was imported.",
                evidence={"package_id": package["package_id"], "claim_id": "CL301"},
                created_by=user.id,
            )
        )
        session.flush()

        result = import_research_package(
            session,
            ResearchPackageImportCreate(organization_id=organization.id, package=package),
            user,
        )
        session.flush()

        assert result.counts["projects"] == 1
        pd1_result = next(item for item in result.projects if item.source_project_key == "PD1")
        assert pd1_result.project_id == adopted.id

        session.refresh(adopted)
        assert adopted.name == "My own checkpoint project"
        assert adopted.localized_content.get("adopted_user_project") is True
    finally:
        transaction.rollback()
        session.close()
