from __future__ import annotations

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.app.projects.service import require_project, require_project_permission
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def test_project_permissions_are_deny_first_and_capped_by_organization_role() -> None:
    engine = enforce_foreign_keys(
        create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    )
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as session:
            organization = Organization(name="Permission Org")
            admin = User(username="global-admin", display_name="Admin", role="admin")
            viewer_owner = User(username="viewer-owner", display_name="Viewer Owner", role="researcher")
            narrowed = User(username="narrowed", display_name="Narrowed", role="researcher")
            researcher = User(username="org-researcher", display_name="Researcher", role="researcher")
            outsider = User(username="project-only", display_name="Project Only", role="researcher")
            session.add_all([organization, admin, viewer_owner, narrowed, researcher, outsider])
            session.flush()
            session.add_all(
                [
                    OrganizationMember(organization_id=organization.id, user_id=viewer_owner.id, role="viewer"),
                    OrganizationMember(organization_id=organization.id, user_id=narrowed.id, role="researcher"),
                    OrganizationMember(organization_id=organization.id, user_id=researcher.id, role="researcher"),
                ]
            )
            project = Project(
                organization_id=organization.id,
                owner_id=viewer_owner.id,
                name="Permission Project",
                project_type="protein_design",
            )
            session.add(project)
            session.flush()
            session.add_all(
                [
                    ProjectMember(project_id=project.id, user_id=viewer_owner.id, role="owner"),
                    ProjectMember(project_id=project.id, user_id=narrowed.id, role="viewer"),
                    ProjectMember(project_id=project.id, user_id=outsider.id, role="owner"),
                ]
            )
            session.flush()

            assert require_project_permission(session, project.id, admin, "manage") is project
            assert require_project_permission(session, project.id, viewer_owner, "read") is project
            assert require_project_permission(session, project.id, researcher, "compute") is project

            for user, action in (
                (viewer_owner, "write"),
                (viewer_owner, "autopilot"),
                (narrowed, "artifact"),
                (researcher, "manage"),
            ):
                with pytest.raises(DomainError, match="Project permission"):
                    require_project_permission(session, project.id, user, action)

            with pytest.raises(DomainError, match="cannot access"):
                require_project(session, project.id, outsider)
    finally:
        drop_all(engine, Base.metadata)
