from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.config import Settings, get_settings
from backend_v2.app.core.database import get_session
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.account_schemas import RegisterRequest
from backend_v2.app.identity.models import AccountGrant, Organization, OrganizationMember, User
from backend_v2.app.identity.service import (
    authenticate,
    create_access_token,
    decode_access_token,
    hash_password,
    issue_refresh_token,
    rotate_refresh_token,
)
from backend_v2.app.main import app
from backend_v2.tests._sqlite import enforce_foreign_keys
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def account_env(monkeypatch):
    settings = get_settings()
    for key, value in dict(
        registration_mode="open",
        deployment_kind="public",
        auth_realm="test-public",
        rate_limit_enabled=False,
        writes_enabled=True,
        public_portal_url="http://localhost:5176",
        private_portal_url="http://localhost:5177",
    ).items():
        monkeypatch.setattr(settings, key, value)
    engine = enforce_foreign_keys(
        create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        admin = User(
            username="admin-test", display_name="Admin", role="admin", password_hash=hash_password("Admin-test-123")
        )
        organization = Organization(name="Restricted team")
        db.add_all([admin, organization])
        db.commit()
        ids = admin.id, organization.id

    def override():
        with Session(engine, expire_on_commit=False) as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_session] = override
    with TestClient(app) as client:
        yield client, engine, ids, settings
    app.dependency_overrides.clear()
    engine.dispose()


def signup(username="new-user", **extra):
    return dict(username=username, display_name="New researcher", password="New-pass-123", **extra)


def admin_headers(engine, ids):
    with Session(engine) as db:
        return {"Authorization": "Bearer " + create_access_token(db.get(User, ids[0]))}


def test_public_registration_creates_only_own_workspace(account_env):
    client, engine, ids, settings = account_env
    response = client.post("/api/v2/auth/register", json=signup("  NEW-USER  "))
    assert response.status_code == 201, response.text
    user = response.json()["user"]
    assert user["username"] == "new-user" and user["role"] == "researcher"
    assert settings.refresh_cookie_name in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    with Session(engine) as db:
        memberships = list(
            db.scalars(select(OrganizationMember).where(OrganizationMember.user_id == uuid.UUID(user["id"])))
        )
        assert len(memberships) == 1 and memberships[0].role == "owner"
        assert memberships[0].organization_id != ids[1]
        assert db.get(User, uuid.UUID(user["id"])).password_hash != "New-pass-123"
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    assert len(client.get("/api/v2/organizations", headers=headers).json()) == 1
    assert client.get("/api/v2/auth/grants", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v2/auth/grants",
            headers=headers,
            json=dict(purpose="invitation", username="another", organization_id=str(ids[1])),
        ).status_code
        == 403
    )
    assert client.get("/api/v2/projects", headers=headers).json()["items"] == []
    for illegal in [{"role": "admin"}, {"organization_id": str(ids[1])}, {"enabled": True}]:
        r = client.post("/api/v2/auth/register", json=signup("another", **illegal))
        assert r.status_code == 422 and "New-pass-123" not in r.text
    assert client.post("/api/v2/auth/register", json=signup()).status_code == 409


@pytest.mark.parametrize("username", ["aa", "1abc", "a/b", "a b", "用户名", "a" * 65])
def test_registration_username_validation(username):
    with pytest.raises(ValidationError):
        RegisterRequest(**signup(username))


@pytest.mark.parametrize("mode,code", [("closed", "registration_closed"), ("invite", "invitation_required")])
def test_closed_and_invitation_registration(account_env, monkeypatch, mode, code):
    client, engine, _, settings = account_env
    monkeypatch.setattr(settings, "registration_mode", mode)
    r = client.post("/api/v2/auth/register", json=signup())
    assert r.status_code == 403 and r.json()["error_code"] == code
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1


def test_private_invitation_is_bound_single_use_and_scoped(account_env, monkeypatch):
    client, engine, ids, settings = account_env
    monkeypatch.setattr(settings, "registration_mode", "invite")
    monkeypatch.setattr(settings, "deployment_kind", "private")
    monkeypatch.setattr(settings, "auth_realm", "test-private")
    headers = admin_headers(engine, ids)
    r = client.post(
        "/api/v2/auth/grants",
        headers=headers,
        json=dict(purpose="invitation", username="invited", organization_id=str(ids[1]), member_role="viewer"),
    )
    assert r.status_code == 201, r.text
    issued = r.json()
    code = issued["token"]
    assert r.headers["cache-control"] == "no-store"
    listed = client.get("/api/v2/auth/grants", headers=headers).json()
    assert code not in str(listed) and "token_hash" not in str(listed)
    with Session(engine) as db:
        grant = db.get(AccountGrant, uuid.UUID(issued["grant"]["id"]))
        assert grant.token_hash == hashlib.sha256(code.encode()).hexdigest()
    assert client.post("/api/v2/auth/register", json=signup("wrong-user", invitation_token=code)).status_code == 400
    r = client.post("/api/v2/auth/register", json=signup("invited", invitation_token=code))
    assert r.status_code == 201 and r.json()["user"]["role"] == "viewer"
    assert (
        client.post("/api/v2/auth/register", json=signup("invited", invitation_token=code)).json()["error_code"]
        == "invalid_account_code"
    )
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.username == "invited"))
        assert db.get(OrganizationMember, (ids[1], user.id)).role == "viewer"
        assert db.scalar(select(func.count()).select_from(Organization)) == 1
    assert (
        client.post(
            "/api/v2/auth/grants",
            headers=headers,
            json=dict(purpose="invitation", username="admin-attempt", organization_id=str(ids[1]), member_role="admin"),
        ).status_code
        == 422
    )


def test_invitation_expiry_revocation_conflict_and_cursor(account_env):
    client, engine, ids, _ = account_env
    headers = admin_headers(engine, ids)
    issued = []
    for n in range(3):
        r = client.post(
            "/api/v2/auth/grants",
            headers=headers,
            json=dict(purpose="invitation", username=f"invited-{n}", organization_id=str(ids[1])),
        )
        assert r.status_code == 201
        issued.append(r.json())
    page = client.get("/api/v2/auth/grants?limit=2", headers=headers).json()
    second = client.get("/api/v2/auth/grants", headers=headers, params=dict(limit=2, cursor=page["next_cursor"])).json()
    assert len(page["items"]) == 2 and len(second["items"]) == 1 and not second["next_cursor"]
    assert len({x["id"] for x in page["items"] + second["items"]}) == 3
    path = "/api/v2/auth/grants/" + issued[0]["grant"]["id"] + "/revoke"
    assert client.post(path, headers=headers).status_code == 428
    assert client.post(path, headers={**headers, "If-Match": 'W/"9"'}).status_code == 412
    assert client.post(path, headers={**headers, "If-Match": 'W/"1"'}).status_code == 200
    assert client.post(path, headers={**headers, "If-Match": 'W/"2"'}).status_code == 409
    assert (
        client.post("/api/v2/auth/register", json=signup("invited-0", invitation_token=issued[0]["token"])).status_code
        == 400
    )
    with Session(engine) as db:
        db.get(AccountGrant, uuid.UUID(issued[1]["grant"]["id"])).expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert (
        client.post("/api/v2/auth/register", json=signup("invited-1", invitation_token=issued[1]["token"])).status_code
        == 400
    )


def test_password_change_and_recovery_revoke_prior_credentials(account_env):
    client, engine, ids, _ = account_env
    first = client.post("/api/v2/auth/register", json=signup()).json()
    access = {"Authorization": "Bearer " + first["access_token"]}
    old_cookie = dict(client.cookies)
    recovery = client.post(
        "/api/v2/auth/grants",
        headers=admin_headers(engine, ids),
        json=dict(purpose="password_reset", username="new-user", expires_in_hours=168),
    ).json()
    expires = datetime.fromisoformat(recovery["grant"]["expires_at"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    assert timedelta(minutes=59) < expires - datetime.now(UTC) <= timedelta(hours=1)
    payload = dict(current_password="Wrong-pass-123", new_password="Changed-pass-456")
    assert (
        client.post("/api/v2/auth/password", headers={**access, "If-Match": 'W/"1"'}, json=payload).status_code == 401
    )
    payload["current_password"] = "New-pass-123"
    assert client.post("/api/v2/auth/password", headers=access, json=payload).status_code == 428
    assert (
        client.post("/api/v2/auth/password", headers={**access, "If-Match": 'W/"9"'}, json=payload).status_code == 412
    )
    assert (
        client.post("/api/v2/auth/password", headers={**access, "If-Match": 'W/"1"'}, json=payload).status_code == 204
    )
    assert client.get("/api/v2/auth/account", headers=access).status_code == 401
    client.cookies.update(old_cookie)
    assert client.post("/api/v2/auth/refresh", json={}).status_code == 401
    assert (
        client.post(
            "/api/v2/auth/password/reset", json=dict(token=recovery["token"], new_password="Recovery-pass-789")
        ).status_code
        == 400
    )
    fresh = client.post(
        "/api/v2/auth/grants",
        headers=admin_headers(engine, ids),
        json=dict(purpose="password_reset", username="new-user"),
    ).json()
    assert (
        client.post(
            "/api/v2/auth/password/reset", json=dict(token=fresh["token"], new_password="Recovery-pass-789")
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/v2/auth/password/reset", json=dict(token=fresh["token"], new_password="Recovery-pass-789")
        ).status_code
        == 400
    )
    assert (
        client.post("/api/v2/auth/token", json=dict(username="new-user", password="Recovery-pass-789")).status_code
        == 200
    )
    assert (
        client.post("/api/v2/auth/token", json=dict(username="new-user", password="Changed-pass-456")).status_code
        == 401
    )


def test_logout_revokes_rotated_family_but_preserves_other_login(account_env):
    client, engine, _, _ = account_env
    first = client.post("/api/v2/auth/register", json=signup()).json()
    cookie_before = dict(client.cookies)
    assert client.post("/api/v2/auth/refresh", json={}).status_code == 200
    cookie_after = dict(client.cookies)
    with Session(engine) as db:
        user = authenticate(db, "new-user", "New-pass-123")
        independent = issue_refresh_token(db, user)
        db.commit()
    client.cookies.clear()
    client.cookies.update(cookie_before)
    assert client.post("/api/v2/auth/logout").status_code == 204
    client.cookies.update(cookie_after)
    assert client.post("/api/v2/auth/refresh", json={}).status_code == 401
    with Session(engine) as db:
        assert rotate_refresh_token(db, independent)[0].username == "new-user"
    assert first["access_token"]


def test_realm_isolation_cookie_origin_and_validation_redaction(account_env, monkeypatch):
    client, engine, ids, settings = account_env
    registered = client.post("/api/v2/auth/register", json=signup())
    access = registered.json()["access_token"]
    raw_cookie = next(iter(client.cookies.values()))
    grant = client.post(
        "/api/v2/auth/grants",
        headers=admin_headers(engine, ids),
        json=dict(purpose="invitation", username="other-user", organization_id=str(ids[1])),
    ).json()
    monkeypatch.setattr(settings, "auth_realm", "test-private")
    assert settings.refresh_cookie_name == "bda_v2_test-private_refresh"
    with pytest.raises(DomainError):
        decode_access_token(access)
    assert client.post("/api/v2/auth/refresh", json=dict(refresh_token=raw_cookie)).status_code == 401
    assert (
        client.post("/api/v2/auth/register", json=signup("other-user", invitation_token=grant["token"])).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v2/auth/token",
            headers={"Origin": "https://untrusted.example"},
            json=dict(username="new-user", password="New-pass-123"),
        ).status_code
        == 403
    )
    assert client.post("/api/v2/auth/logout", headers={"Origin": "https://untrusted.example"}).status_code == 403
    bad = client.post(
        "/api/v2/auth/register", json=dict(username="new", display_name=" ", password="private-secret-123")
    )
    assert bad.status_code == 422 and "private-secret-123" not in bad.text


@pytest.mark.parametrize(
    "options",
    [
        dict(deployment_kind="private", registration_mode="open"),
        dict(public_portal_url="javascript:alert(1)"),
        dict(private_portal_url="https://user:password@example.test"),
        dict(private_portal_url="http://example.test"),
        dict(public_portal_url="https://example.test/?token=bad"),
        dict(public_portal_url="https://example.test:wrong"),
        dict(public_portal_url="https://example.test:0"),
        dict(private_portal_url="https://:443"),
    ],
)
def test_unsafe_portal_settings_rejected(options):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **options)


def test_write_gate_blocks_signup_but_allows_logout(account_env, monkeypatch):
    client, _, _, settings = account_env
    monkeypatch.setattr(settings, "writes_enabled", False)
    assert client.get("/api/v2/auth/config").json()["registration_mode"] == "closed"
    assert client.post("/api/v2/auth/register", json=signup()).status_code == 503
    assert (
        client.post("/api/v2/auth/password/reset", json=dict(token="x" * 43, new_password="New-pass-123")).status_code
        == 503
    )
    assert client.post("/api/v2/auth/logout").status_code == 204


def test_other_portal_origin_cannot_use_ambient_refresh_cookie(account_env, monkeypatch):
    client, _, _, settings = account_env
    monkeypatch.setattr(settings, "cors_origins", "http://localhost:5176,http://localhost:5177")
    for path in ["/api/v2/auth/logout", "/api/v2/auth/refresh"]:
        result = client.post(path, headers={"Origin": "http://localhost:5177"}, json={})
        assert result.status_code == 403
    assert (
        client.post("/api/v2/auth/register", headers={"Origin": "http://127.0.0.1:5176"}, json=signup()).status_code
        == 201
    )
