"""Reading back who is in an organization.

The write side has existed since the beginning; the read side did not, so a
membership could be granted and then never be seen again. What is worth pinning is
the authorization rule, because it is the one thing a listing endpoint can get
wrong in a way nobody notices: a non-member must not learn that an organization
exists, and must not learn who is in it.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.database import get_session
from backend_v2.app.core.models import Base
from backend_v2.app.identity.deps import current_user
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.main import app
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


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
        admin = User(username="org-admin", display_name="Org Admin", role="admin", enabled=True)
        member = User(username="bench-mate", display_name="Bench Mate", role="researcher", enabled=True)
        outsider = User(username="outsider", display_name="Outsider", role="researcher", enabled=True)
        organization = Organization(name="Org One")
        other = Organization(name="Org Two")
        session.add_all([admin, member, outsider, organization, other])
        session.flush()
        session.add_all(
            [
                OrganizationMember(organization_id=organization.id, user_id=admin.id, role="owner"),
                OrganizationMember(organization_id=organization.id, user_id=member.id, role="researcher"),
            ]
        )
        session.commit()
        ids = {
            "admin": admin.id,
            "member": member.id,
            "outsider": outsider.id,
            "organization": organization.id,
            "other": other.id,
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
    try:
        yield TestClient(app, raise_server_exceptions=True), ids, acting
    finally:
        app.dependency_overrides.clear()
        drop_all(engine, Base.metadata)
        engine.dispose()


def test_members_come_back_named_not_just_keyed(client) -> None:
    api, ids, _ = client
    response = api.get(f"/api/v2/organizations/{ids['organization']}/members")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["username"] for item in body] == ["bench-mate", "org-admin"]
    assert {item["role"] for item in body} == {"researcher", "owner"}
    # A UUID alone cannot answer "who is in this organization", which is the question.
    assert all(item["display_name"] for item in body)


def test_a_member_may_read_their_own_organization(client) -> None:
    api, ids, acting = client
    acting["user"] = ids["member"]
    response = api.get(f"/api/v2/organizations/{ids['organization']}/members")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_an_outsider_is_told_it_does_not_exist_rather_than_who_is_in_it(client) -> None:
    api, ids, acting = client
    acting["user"] = ids["outsider"]
    response = api.get(f"/api/v2/organizations/{ids['organization']}/members")
    # 404 rather than 403: a non-member should not learn the organization exists.
    assert response.status_code == 404
    assert response.json()["error_code"] == "organization_not_found"


def test_a_missing_organization_is_a_404(client) -> None:
    api, _, _ = client
    response = api.get(f"/api/v2/organizations/{uuid.uuid4()}/members")
    assert response.status_code == 404
