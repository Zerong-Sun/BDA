from __future__ import annotations

import os
import uuid

import pytest
from backend_v2.app.core.config import get_settings
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.platform.models import Operation
from backend_v2.app.projects.models import Project
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    os.getenv("BDA_V2_RUN_DB_TESTS") != "1",
    reason="PostgreSQL integration test disabled",
)


def test_nobypassrls_role_is_fenced_for_users_and_workers() -> None:
    """Exercise policies as a real non-owner role; owner-backed tests bypass RLS."""
    engine = create_engine(get_settings().database_url)
    role = f"bda_test_rls_{uuid.uuid4().hex}"
    suffix = uuid.uuid4().hex
    with Session(engine, expire_on_commit=False) as owner:
        user = User(username=f"rls-{suffix}", display_name="RLS user", role="researcher")
        organizations = [Organization(name=f"RLS org {suffix}-{index}") for index in range(2)]
        owner.add_all([user, *organizations])
        owner.flush()
        owner.add(OrganizationMember(organization_id=organizations[0].id, user_id=user.id, role="researcher"))
        projects = [
            Project(
                organization_id=organization.id,
                owner_id=user.id,
                name=f"RLS project {suffix}-{index}",
                project_type="test",
            )
            for index, organization in enumerate(organizations)
        ]
        owner.add_all(projects)
        owner.flush()
        operations = [
            Operation(
                project_id=project.id,
                organization_id=project.organization_id,
                created_by=user.id,
                kind="rls.test",
                resource_type="project",
                resource_id=project.id,
            )
            for project in projects
        ]
        owner.add_all(operations)
        owner.commit()

    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOBYPASSRLS'))
            connection.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
            connection.execute(
                text(
                    f'GRANT SELECT, INSERT, UPDATE, DELETE ON projects, operations, '
                    f'organization_members TO "{role}"'
                )
            )

        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text(f'SET LOCAL ROLE "{role}"'))
            assert list(connection.scalars(select(Project.id))) == []
            connection.execute(
                text("select set_config('bda.user_id', :user_id, true)"),
                {"user_id": str(user.id)},
            )
            assert set(connection.scalars(select(Project.id))) == {projects[0].id}
            transaction.rollback()

        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text(f'SET LOCAL ROLE "{role}"'))
            connection.execute(
                text("select set_config('bda.worker_project_id', :project_id, true)"),
                {"project_id": str(projects[1].id)},
            )
            assert set(connection.scalars(select(Operation.id))) == {operations[1].id}
            with pytest.raises(DBAPIError):
                with connection.begin_nested():
                    connection.execute(
                        Operation.__table__.insert().values(
                            project_id=projects[0].id,
                            organization_id=projects[0].organization_id,
                            created_by=user.id,
                            kind="rls.cross_project",
                            resource_type="project",
                            resource_id=projects[0].id,
                        )
                    )
            transaction.rollback()
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP OWNED BY "{role}"'))
            connection.execute(text(f'DROP ROLE "{role}"'))
            connection.execute(
                Operation.__table__.delete().where(Operation.id.in_([operation.id for operation in operations]))
            )
            connection.execute(Project.__table__.delete().where(Project.id.in_([project.id for project in projects])))
            connection.execute(
                OrganizationMember.__table__.delete().where(OrganizationMember.user_id == user.id)
            )
            connection.execute(Organization.__table__.delete().where(Organization.id.in_([o.id for o in organizations])))
            connection.execute(User.__table__.delete().where(User.id == user.id))
