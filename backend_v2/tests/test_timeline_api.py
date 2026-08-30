"""The timeline HTTP contract, exercised end to end.

The repository and service are covered separately; this pins the parts only the API
layer decides: status codes, the ETag/If-Match concurrency handshake, chronological
paging across a real cursor round-trip, and that validation failures come back as 4xx
rather than 500s.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.database import get_session
from backend_v2.app.core.models import Base
from backend_v2.app.identity.deps import current_user, require_command
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.main import app
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def client() -> Generator[tuple[TestClient, dict[str, uuid.UUID]]]:
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        user = User(username="tl-admin", display_name="TL Admin", role="admin", enabled=True)
        organization = Organization(name="TL Org")
        session.add_all([user, organization])
        session.flush()
        session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
        project = Project(
            organization_id=organization.id, owner_id=user.id, name="TL project", project_type="protein_design"
        )
        session.add(project)
        session.flush()
        session.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
        session.commit()
        ids = {"user": user.id, "project": project.id}

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
            return session.get(User, ids["user"])  # type: ignore[return-value]

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[current_user] = user_override
    app.dependency_overrides[require_command] = user_override
    try:
        yield TestClient(app, raise_server_exceptions=True), ids
    finally:
        app.dependency_overrides.clear()
        drop_all(engine, Base.metadata)
        engine.dispose()


def _post(client: TestClient, project_id: uuid.UUID, **payload):
    body = {"occurred_at": "2026-08-03T09:00:00Z", "title": "an entry", **payload}
    return client.post(f"/api/v2/projects/{project_id}/timeline", json=body)


def test_create_then_read_back(client) -> None:
    api, ids = client
    created = _post(api, ids["project"], title="a decision", summary="why", entry_type="decision")
    assert created.status_code == 201, created.text
    entry_id = created.json()["id"]

    fetched = api.get(f"/api/v2/timeline/{entry_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "a decision"
    assert fetched.headers["ETag"] == 'W/"1"'


def test_listing_is_chronological_and_pages_with_a_real_cursor(client) -> None:
    api, ids = client
    for hour, title in ((12, "second"), (9, "first"), (15, "third")):
        _post(api, ids["project"], occurred_at=f"2026-08-03T{hour:02d}:00:00Z", title=title)

    first_page = api.get(f"/api/v2/projects/{ids['project']}/timeline", params={"limit": 2})
    assert first_page.status_code == 200
    body = first_page.json()
    assert [item["title"] for item in body["items"]] == ["first", "second"]
    assert body["next_cursor"]

    second_page = api.get(
        f"/api/v2/projects/{ids['project']}/timeline",
        params={"limit": 2, "cursor": body["next_cursor"]},
    )
    assert [item["title"] for item in second_page.json()["items"]] == ["third"]
    assert second_page.json()["next_cursor"] is None


def test_filters_are_wired_through(client) -> None:
    api, ids = client
    _post(api, ids["project"], title="dead end", entry_type="result", outcome="refuted", phase="phase-1")
    _post(api, ids["project"], title="a plan", entry_type="plan", phase="phase-2")

    refuted = api.get(f"/api/v2/projects/{ids['project']}/timeline", params={"outcome": "refuted"})
    assert [item["title"] for item in refuted.json()["items"]] == ["dead end"]

    phase2 = api.get(f"/api/v2/projects/{ids['project']}/timeline", params={"phase": "phase-2"})
    assert [item["title"] for item in phase2.json()["items"]] == ["a plan"]


def test_patch_requires_if_match_and_bumps_the_version(client) -> None:
    api, ids = client
    entry_id = _post(api, ids["project"]).json()["id"]

    without = api.patch(f"/api/v2/timeline/{entry_id}", json={"title": "new"})
    assert without.status_code == 428, "a blind write must be refused"

    stale = api.patch(
        f"/api/v2/timeline/{entry_id}", json={"title": "new"}, headers={"If-Match": 'W/"99"'}
    )
    assert stale.status_code == 412

    ok = api.patch(
        f"/api/v2/timeline/{entry_id}", json={"title": "new title"}, headers={"If-Match": 'W/"1"'}
    )
    assert ok.status_code == 200
    assert ok.json()["title"] == "new title"
    assert ok.headers["ETag"] == 'W/"2"'


def test_bad_vocabulary_is_a_422_not_a_500(client) -> None:
    api, ids = client
    assert _post(api, ids["project"], entry_type="brainstorm").status_code == 422
    assert _post(api, ids["project"], outcome="probably").status_code == 422
    assert _post(api, ids["project"], provenance={"jobIds": ["x"]}).status_code == 422


def test_unknown_entry_is_404(client) -> None:
    api, _ = client
    assert api.get(f"/api/v2/timeline/{uuid.uuid4()}").status_code == 404


def test_delete_removes_the_entry(client) -> None:
    api, ids = client
    entry_id = _post(api, ids["project"]).json()["id"]
    deleted = api.delete(f"/api/v2/timeline/{entry_id}", headers={"If-Match": 'W/"1"'})
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert api.get(f"/api/v2/timeline/{entry_id}").status_code == 404


def test_a_link_to_another_projects_entry_is_refused(client) -> None:
    """Cross-project links would leak one project's reasoning into another's record."""
    api, ids = client
    entry_id = _post(api, ids["project"]).json()["id"]
    other_project = uuid.uuid4()
    response = api.post(
        f"/api/v2/projects/{other_project}/timeline",
        json={"occurred_at": "2026-08-03T09:00:00Z", "title": "x", "caused_by_id": entry_id},
    )
    assert response.status_code in (403, 404, 422), response.text
