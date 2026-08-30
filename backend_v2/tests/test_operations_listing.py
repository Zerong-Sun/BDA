"""Listing asynchronous work.

Until this endpoint existed an operation was only ever a local variable in whichever
component started it, so navigating away lost the handle to work that kept running.

What is pinned here is the visibility fence, because a listing endpoint is where an
authorization rule goes wrong quietly: the per-operation check refuses a project the
caller cannot read and refuses a project-less operation to anyone but an administrator,
and the listing has to refuse exactly the same set rather than approximately.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.database import get_session
from backend_v2.app.core.models import Base
from backend_v2.app.identity.deps import current_user, require_command
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.main import app
from backend_v2.app.platform.models import Operation
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

NOW = datetime.now(UTC)


@pytest.fixture
def client() -> Generator[tuple[TestClient, dict[str, uuid.UUID], dict[str, uuid.UUID]]]:
    engine = enforce_foreign_keys(
        create_engine(
            "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    acting: dict[str, uuid.UUID] = {}

    with factory() as session:
        admin = User(username="ops-admin", display_name="Ops Admin", role="admin", enabled=True)
        member = User(username="ops-member", display_name="Ops Member", role="researcher", enabled=True)
        outsider = User(username="ops-outsider", display_name="Outsider", role="researcher", enabled=True)
        organization = Organization(name="Ops Org")
        other_org = Organization(name="Other Org")
        session.add_all([admin, member, outsider, organization, other_org])
        session.flush()
        session.add_all(
            [
                OrganizationMember(organization_id=organization.id, user_id=admin.id, role="owner"),
                OrganizationMember(organization_id=organization.id, user_id=member.id, role="researcher"),
                OrganizationMember(organization_id=other_org.id, user_id=outsider.id, role="researcher"),
            ]
        )
        mine = Project(organization_id=organization.id, owner_id=admin.id, name="Ours", project_type="protein_design")
        theirs = Project(
            organization_id=other_org.id, owner_id=outsider.id, name="Theirs", project_type="protein_design"
        )
        session.add_all([mine, theirs])
        session.flush()
        session.add_all(
            [
                ProjectMember(project_id=mine.id, user_id=admin.id, role="owner"),
                ProjectMember(project_id=mine.id, user_id=member.id, role="researcher"),
                ProjectMember(project_id=theirs.id, user_id=outsider.id, role="owner"),
            ]
        )

        def operation(**kwargs) -> Operation:
            row = Operation(
                created_by=kwargs.pop("created_by", admin.id),
                kind=kwargs.pop("kind", "literature.search"),
                resource_type="project",
                resource_id=uuid.uuid4(),
                **kwargs,
            )
            session.add(row)
            return row

        readable = operation(project_id=mine.id, status="succeeded")
        readable_by_member = operation(project_id=mine.id, created_by=member.id, kind="delivery.build")
        unreadable = operation(project_id=theirs.id, created_by=outsider.id)
        platform_level = operation(project_id=None, kind="project.prompt_generate")
        session.flush()
        # Old enough to fall outside the default window, and only that.
        old = operation(project_id=mine.id, kind="intelligence.run")
        session.flush()
        old.created_at = NOW - timedelta(days=90)
        session.commit()
        ids = {
            "admin": admin.id,
            "member": member.id,
            "outsider": outsider.id,
            "project": mine.id,
            "other_project": theirs.id,
            "readable": readable.id,
            "member_operation": readable_by_member.id,
            "unreadable": unreadable.id,
            "platform_level": platform_level.id,
            "old": old.id,
        }
    acting["user"] = ids["admin"]

    def session_override() -> Generator[Session]:
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def user_override() -> User:
        with factory() as session:
            return session.get(User, acting["user"])  # type: ignore[return-value]

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[current_user] = user_override
    app.dependency_overrides[require_command] = user_override
    try:
        yield TestClient(app, raise_server_exceptions=True), ids, acting
    finally:
        app.dependency_overrides.clear()
        drop_all(engine, Base.metadata)
        engine.dispose()


def listed(response) -> set[str]:
    return {item["id"] for item in response.json()["items"]}


def test_an_administrator_sees_project_less_operations_too(client) -> None:
    api, ids, _ = client
    response = api.get("/api/v2/operations")
    assert response.status_code == 200, response.text
    seen = listed(response)
    assert str(ids["platform_level"]) in seen
    assert str(ids["unreadable"]) in seen


def test_a_member_sees_only_projects_they_can_read_and_never_a_project_less_one(client) -> None:
    api, ids, acting = client
    acting["user"] = ids["member"]
    seen = listed(api.get("/api/v2/operations"))
    assert str(ids["readable"]) in seen
    # The two the per-operation check would refuse.
    assert str(ids["unreadable"]) not in seen
    assert str(ids["platform_level"]) not in seen


def test_an_outsider_sees_none_of_ours(client) -> None:
    api, ids, acting = client
    acting["user"] = ids["outsider"]
    seen = listed(api.get("/api/v2/operations"))
    assert seen == {str(ids["unreadable"])}


def test_mine_filters_to_the_caller(client) -> None:
    api, ids, acting = client
    acting["user"] = ids["member"]
    seen = listed(api.get("/api/v2/operations", params={"mine": True}))
    assert seen == {str(ids["member_operation"])}


def test_the_default_window_hides_a_ninety_day_old_row_until_since_widens_it(client) -> None:
    api, ids, _ = client
    assert str(ids["old"]) not in listed(api.get("/api/v2/operations"))
    widened = api.get("/api/v2/operations", params={"since": (NOW - timedelta(days=365)).isoformat()})
    assert str(ids["old"]) in listed(widened)


def test_kind_and_status_narrow_the_listing(client) -> None:
    api, ids, _ = client
    assert listed(api.get("/api/v2/operations", params={"status": "succeeded"})) == {str(ids["readable"])}
    assert listed(api.get("/api/v2/operations", params={"kind": "delivery.build"})) == {
        str(ids["member_operation"])
    }


def test_asking_for_a_project_you_cannot_read_is_refused_not_silently_empty(client) -> None:
    api, ids, acting = client
    acting["user"] = ids["member"]
    response = api.get("/api/v2/operations", params={"project_id": str(ids["other_project"])})
    # Silently returning an empty page would read as "that project has no activity".
    assert response.status_code == 403


def test_paging_walks_the_whole_listing_without_repeating_a_row(client) -> None:
    api, _, _ = client
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(10):
        page = api.get("/api/v2/operations", params={"limit": 1, **({"cursor": cursor} if cursor else {})})
        assert page.status_code == 200
        body = page.json()
        seen.extend(item["id"] for item in body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen))
    assert len(seen) == 4  # everything inside the default window
