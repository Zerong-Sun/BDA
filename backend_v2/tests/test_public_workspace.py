from __future__ import annotations

import uuid
from contextlib import nullcontext

import pytest
from backend_v2.app.core.config import Settings, get_settings
from backend_v2.app.core.database import get_session
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity import deps, public_workspace
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.main import app
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import enforce_foreign_keys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.requests import Request


@pytest.fixture
def public_env(monkeypatch):
    engine = enforce_foreign_keys(
        create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        viewer = User(username="public-reader", display_name="Public visitor", role="viewer")
        owner = User(username="owner", display_name="Owner", role="admin")
        public = Organization(name="Published research")
        private = Organization(name="Private research")
        db.add_all([viewer, owner, public, private])
        db.flush()
        published = Project(name="Published example", organization_id=public.id, owner_id=owner.id, project_type="test")
        hidden = Project(
            name="Confidential project", organization_id=private.id, owner_id=owner.id, project_type="test"
        )
        db.add_all([published, hidden, OrganizationMember(organization_id=public.id, user_id=viewer.id, role="viewer")])
        db.commit()
        ids = dict(viewer=viewer.id, public=public.id, private=private.id, project=published.id, hidden=hidden.id)
    settings = get_settings()
    for name, value in dict(
        deployment_kind="public",
        public_workspace_user_id=ids["viewer"],
        public_workspace_organization_id=ids["public"],
        rate_limit_enabled=False,
    ).items():
        monkeypatch.setattr(settings, name, value)

    def override():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_session] = override
    with TestClient(app) as client:
        yield client, engine, ids
    app.dependency_overrides.clear()
    engine.dispose()


def test_guest_enters_existing_workspace_without_an_account_or_token(public_env):
    client, _, ids = public_env
    assert client.get("/api/v2/auth/config").json()["public_workspace_enabled"] is True
    response = client.get("/api/v2/auth/me")
    assert response.status_code == 200 and response.json()["role"] == "viewer"
    assert "set-cookie" not in response.headers
    assert client.get("/api/v2/projects").json()["items"][0]["id"] == str(ids["project"])
    access = client.get(f"/api/v2/projects/{ids['project']}/access")
    assert access.status_code == 200, access.text
    assert access.json()["permissions"]["read"] and not access.json()["permissions"]["write"]
    assert client.get(f"/api/v2/projects/{ids['hidden']}").status_code in {403, 404}
    assert client.get("/api/v2/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_guest_cannot_mutate_or_run_bot(public_env):
    client, _, ids = public_env
    assert (
        client.post(
            "/api/v2/projects", json={"organization_id": str(ids["public"]), "name": "No", "project_type": "test"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v2/projects/{ids['project']}", json={"name": "Changed"}, headers={"If-Match": 'W/"1"'}
        ).status_code
        == 403
    )
    assert (
        client.post("/api/v2/copilot/chat", json={"project_id": str(ids["project"]), "message": "run"}).status_code
        == 403
    )
    assert (
        client.post("/api/v2/wetlab/calculations", json={"kind": "protein-properties", "sequence": "MWK"}).status_code
        == 200
    )


def test_private_never_uses_public_viewer(public_env, monkeypatch):
    client, _, _ = public_env
    monkeypatch.setattr(get_settings(), "deployment_kind", "private")
    assert client.get("/api/v2/auth/config").json()["public_workspace_enabled"] is False
    assert client.get("/api/v2/projects").status_code == 401


@pytest.mark.parametrize("bad", ["admin", "disabled", "password", "extra-membership", "wrong-org", "member-role"])
def test_unsafe_reader_configuration_fails_closed(public_env, monkeypatch, bad):
    client, engine, ids = public_env
    with Session(engine) as db:
        user = db.get(User, ids["viewer"])
        if bad == "admin":
            user.role = "admin"
        elif bad == "disabled":
            user.enabled = False
        elif bad == "password":
            user.password_hash = "not-a-guest"
        elif bad == "extra-membership":
            db.add(OrganizationMember(organization_id=ids["private"], user_id=user.id, role="viewer"))
        elif bad == "member-role":
            db.get(OrganizationMember, (ids["public"], user.id)).role = "owner"
        else:
            monkeypatch.setattr(get_settings(), "public_workspace_organization_id", ids["private"])
        db.commit()
    assert client.get("/api/v2/projects").status_code == 503


def test_guest_stream_auth_and_quota(public_env, monkeypatch):
    client, engine, ids = public_env
    with Session(engine) as db:
        monkeypatch.setattr(deps, "SessionFactory", lambda: nullcontext(db))
        user = deps.streaming_user(None, request=Request({"type": "http", "method": "GET", "path": "/events"}))
        assert user.id == ids["viewer"]

    def exceeded(_ip):
        raise DomainError("rate_limit_exceeded", "Quota exceeded", status_code=429)

    monkeypatch.setattr(public_workspace, "enforce_public_workspace_quota", exceeded)
    assert client.get("/api/v2/projects").status_code == 429


def test_public_workspace_requires_explicit_paired_public_configuration():
    with pytest.raises(ValueError, match="both"):
        Settings(_env_file=None, public_workspace_user_id=uuid.uuid4())
    with pytest.raises(ValueError, match="only allowed"):
        Settings(
            _env_file=None,
            deployment_kind="private",
            public_workspace_user_id=uuid.uuid4(),
            public_workspace_organization_id=uuid.uuid4(),
        )
