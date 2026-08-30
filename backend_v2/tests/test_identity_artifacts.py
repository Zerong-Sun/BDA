from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections.abc import Generator
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.artifacts import service as artifact_service
from backend_v2.app.artifacts.models import Artifact, ArtifactLineageEdge, ArtifactUpload
from backend_v2.app.artifacts.schemas import ArtifactLineageEdgeCreate, UploadComplete, UploadCreate
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity import deps as identity_deps
from backend_v2.app.identity import service as identity_service
from backend_v2.app.identity.models import Organization, RefreshSession, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import enforce_foreign_keys
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


@pytest.fixture
def service_session() -> Generator[tuple[Session, User, Project]]:
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://"))
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = User(username="service", display_name="Service", role="admin", enabled=True)
        org = Organization(name="Service Org")
        session.add_all([user, org])
        session.flush()
        project = Project(organization_id=org.id, owner_id=user.id, name="Service project", project_type="design")
        session.add(project)
        session.commit()
        yield session, user, project
    engine.dispose()


def test_password_access_and_refresh_rotation(service_session) -> None:
    session, user, _ = service_session
    for weak in ("short", "abcdefgh", "12345678"):
        with pytest.raises(DomainError, match="letters and digits"):
            identity_service.hash_password(weak)
    user.password_hash = identity_service.hash_password("safe-pass-123")
    session.commit()
    assert identity_service.authenticate(session, user.username, "safe-pass-123").id == user.id
    with pytest.raises(DomainError, match="Invalid username"):
        identity_service.authenticate(session, user.username, "wrong")
    token = identity_service.create_access_token(user)
    assert identity_service.decode_access_token(token)["sub"] == str(user.id)
    with pytest.raises(DomainError, match="invalid or expired"):
        identity_service.decode_access_token("bad")
    refresh = identity_service.issue_refresh_token(session, user)
    session.flush()
    rotated_user, replacement = identity_service.rotate_refresh_token(session, refresh)
    assert rotated_user.id == user.id and replacement != refresh
    assert session.scalar(select(RefreshSession).where(RefreshSession.revoked_at.is_not(None)))
    with pytest.raises(DomainError, match="invalid or expired"):
        identity_service.rotate_refresh_token(session, refresh)
    disabled_refresh = identity_service.issue_refresh_token(session, user)
    user.enabled = False
    session.flush()
    with pytest.raises(DomainError, match="unavailable"):
        identity_service.rotate_refresh_token(session, disabled_refresh)


def test_bootstrap_admin_is_idempotent(service_session) -> None:
    session, _, _ = service_session
    first = identity_service.bootstrap_admin(session, username="bootstrap", password="secure-123")
    first.role = "viewer"
    first.enabled = False
    session.flush()
    second = identity_service.bootstrap_admin(session, username="bootstrap", password="replacement-456")
    assert first.id == second.id
    assert second.role == "admin"
    assert second.enabled is True
    assert identity_service.authenticate(session, "bootstrap", "replacement-456").id == second.id
    with pytest.raises(DomainError, match="Invalid username or password"):
        identity_service.authenticate(session, "bootstrap", "secure-123")


def test_authentication_dependencies_enforce_roles(monkeypatch, service_session) -> None:
    session, user, _ = service_session
    with pytest.raises(DomainError, match="required"):
        identity_deps.current_user(None, session)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
    monkeypatch.setattr(identity_deps, "decode_access_token", lambda token: {"sub": str(user.id)})
    assert identity_deps.current_user(credentials, session).id == user.id
    monkeypatch.setattr(identity_deps, "SessionFactory", lambda: nullcontext(session))
    assert identity_deps.streaming_user(credentials).id == user.id
    session.add(user)
    monkeypatch.setattr(identity_deps, "decode_access_token", lambda token: {"sub": "bad"})
    with pytest.raises(DomainError, match="subject"):
        identity_deps.current_user(credentials, session)
    monkeypatch.setattr(identity_deps, "decode_access_token", lambda token: {"sub": str(user.id)})
    user.enabled = False
    session.add(user)
    session.commit()
    with pytest.raises(DomainError, match="unavailable"):
        identity_deps.current_user(credentials, session)
    user.enabled = True
    user.role = "viewer"
    with pytest.raises(DomainError, match="read-only"):
        identity_deps.require_command(user)
    with pytest.raises(DomainError, match="cannot perform"):
        identity_deps.require_roles("admin")(user)
    user.role = "admin"
    assert identity_deps.require_roles("admin")(user) is user
    assert identity_deps.require_command(user) is user


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self):
        return self

    def json(self) -> dict:
        return self.payload


def test_oidc_pkce_and_callback(monkeypatch, service_session) -> None:
    session, _, _ = service_session
    config = {
        "oidc_providers": {
            "test": {
                "issuer": "https://issuer",
                "client_id": "client",
                "redirect_uris": "https://app/callback",
            }
        }
    }
    monkeypatch.setattr(identity_service, "get_settings", lambda: SimpleNamespace(**config))
    discovery = {
        "authorization_endpoint": "https://issuer/authorize",
        "token_endpoint": "https://issuer/token",
        "jwks_uri": "https://issuer/jwks",
        "id_token_signing_alg_values_supported": ["RS256"],
    }
    monkeypatch.setattr(identity_service.httpx, "get", lambda *args, **kwargs: FakeResponse(discovery))
    monkeypatch.setattr(identity_service.httpx, "post", lambda *args, **kwargs: FakeResponse({"id_token": "jwt"}))
    url, state = identity_service.begin_oidc(session, "test", "https://app/callback")
    assert "code_challenge=" in url and state
    session.flush()
    monkeypatch.setattr(
        identity_service.jwt,
        "PyJWKClient",
        lambda _url: SimpleNamespace(get_signing_key_from_jwt=lambda _token: SimpleNamespace(key="key")),
    )
    monkeypatch.setattr(
        identity_service.jwt,
        "decode",
        lambda *args, **kwargs: {"sub": "subject", "email": "person@example.test", "name": "Person"},
    )
    user = identity_service.complete_oidc(session, "test", state, "code")
    assert user.oidc_subject == "subject"
    with pytest.raises(DomainError, match="state is invalid"):
        identity_service.complete_oidc(session, "test", "missing", "code")
    with pytest.raises(DomainError, match="not configured"):
        identity_service.begin_oidc(session, "missing", "https://app/callback")


def _oidc_settings(**provider_overrides) -> SimpleNamespace:
    provider = {
        "issuer": "https://issuer",
        "client_id": "client",
        "redirect_uris": "https://app/callback,https://app/alt-callback",
        **provider_overrides,
    }
    return SimpleNamespace(oidc_providers={"test": provider})


def test_begin_oidc_rejects_a_redirect_uri_outside_the_allowlist(monkeypatch, service_session) -> None:
    """The value is caller-supplied. Passing an arbitrary one to the provider would make
    this service a party to delivering an authorization code somewhere it does not belong."""
    session, _, _ = service_session
    monkeypatch.setattr(identity_service, "get_settings", _oidc_settings)
    monkeypatch.setattr(identity_service.httpx, "get", lambda *a, **k: FakeResponse({}))

    with pytest.raises(DomainError, match="redirect_uri is not permitted"):
        identity_service.begin_oidc(session, "test", "https://attacker.invalid/collect")


def test_id_token_algorithms_come_from_the_allowlist_not_the_discovery_document(
    monkeypatch, service_session
) -> None:
    """A provider advertising HS256 must not be able to select it: the RSA public key
    would then be used as an HMAC secret, which is the algorithm-confusion substitution."""
    session, _, _ = service_session
    monkeypatch.setattr(identity_service, "get_settings", _oidc_settings)
    discovery = {
        "authorization_endpoint": "https://issuer/authorize",
        "token_endpoint": "https://issuer/token",
        "jwks_uri": "https://issuer/jwks",
        "id_token_signing_alg_values_supported": ["HS256", "none", "RS256"],
    }
    monkeypatch.setattr(identity_service.httpx, "get", lambda *a, **k: FakeResponse(discovery))
    monkeypatch.setattr(identity_service.httpx, "post", lambda *a, **k: FakeResponse({"id_token": "jwt"}))
    monkeypatch.setattr(
        identity_service.jwt,
        "PyJWKClient",
        lambda _url: SimpleNamespace(get_signing_key_from_jwt=lambda _token: SimpleNamespace(key="key")),
    )
    seen: dict = {}

    def capture(*args, **kwargs):
        seen.update(kwargs)
        return {"sub": "subject", "email": "person@example.test", "name": "Person"}

    monkeypatch.setattr(identity_service.jwt, "decode", capture)

    _, state = identity_service.begin_oidc(session, "test", "https://app/callback")
    session.flush()
    identity_service.complete_oidc(session, "test", state, "code")

    assert seen["algorithms"] == ["RS256"]


def test_no_acceptable_algorithm_is_refused(monkeypatch, service_session) -> None:
    session, _, _ = service_session
    monkeypatch.setattr(identity_service, "get_settings", _oidc_settings)
    discovery = {
        "authorization_endpoint": "https://issuer/authorize",
        "token_endpoint": "https://issuer/token",
        "jwks_uri": "https://issuer/jwks",
        "id_token_signing_alg_values_supported": ["HS256"],
    }
    monkeypatch.setattr(identity_service.httpx, "get", lambda *a, **k: FakeResponse(discovery))
    monkeypatch.setattr(identity_service.httpx, "post", lambda *a, **k: FakeResponse({"id_token": "jwt"}))

    _, state = identity_service.begin_oidc(session, "test", "https://app/callback")
    session.flush()
    with pytest.raises(DomainError, match="no acceptable ID token signing algorithm"):
        identity_service.complete_oidc(session, "test", state, "code")


def test_unknown_username_still_pays_the_bcrypt_cost(service_session) -> None:
    """Returning early on a miss made a wrong username measurably faster than a wrong
    password, which is enough to enumerate accounts from response time."""
    session, _, _ = service_session
    checked: list[bytes] = []
    original = identity_service.bcrypt.checkpw

    def record(password: bytes, stored: bytes) -> bool:
        checked.append(stored)
        return original(password, stored)

    identity_service.bcrypt.checkpw = record
    try:
        with pytest.raises(DomainError, match="Invalid username or password"):
            identity_service.authenticate(session, "no-such-user", "whatever-123")
    finally:
        identity_service.bcrypt.checkpw = original

    assert checked == [identity_service._DUMMY_PASSWORD_HASH]


class FakeStorage:
    data = b"ATOM      1  CA  GLY A   1      0.000   0.000   0.000\nEND\n"
    promoted: tuple[str, str] | None = None
    fail = False

    def upload_url(self, key: str) -> str:
        return f"https://put/{key}"

    def inspect_and_hash(self, key: str) -> tuple[int, str]:
        if self.fail:
            raise RuntimeError("missing")
        return len(self.data), hashlib.sha256(self.data).hexdigest()

    def read_bytes(self, key: str, *, max_bytes: int) -> bytes:
        return self.data[:max_bytes]

    def remove(self, key: str) -> None:
        return None

    def promote(self, source: str, target: str) -> None:
        self.promoted = (source, target)


def test_two_phase_upload_success_is_idempotent(monkeypatch, service_session) -> None:
    session, user, project = service_session
    monkeypatch.setattr(artifact_service, "ObjectStorage", FakeStorage)
    upload, url = artifact_service.create_upload(
        session,
        project,
        UploadCreate(
            project_id=project.id, filename="result.pdb", artifact_type="structure", content_type="chemical/x-pdb"
        ),
        user,
    )
    assert url.startswith("https://put/")
    checksum = hashlib.sha256(FakeStorage.data).hexdigest()
    artifact = artifact_service.complete_upload(
        session, upload, UploadComplete(checksum_sha256=checksum, lineage={"source": "test"}), project, user
    )
    session.commit()
    assert artifact.status == "available" and artifact.checksum_sha256 == checksum
    assert (
        artifact_service.complete_upload(session, upload, UploadComplete(checksum_sha256=checksum), project, user).id
        == artifact.id
    )


def test_two_phase_upload_failure_paths(monkeypatch, service_session) -> None:
    session, user, project = service_session
    monkeypatch.setattr(artifact_service, "ObjectStorage", FakeStorage)

    def new_upload() -> ArtifactUpload:
        upload = ArtifactUpload(
            project_id=project.id,
            created_by=user.id,
            filename="x",
            artifact_type="data",
            content_type="text/plain",
            object_key=f"staging/{datetime.now(UTC).timestamp()}",
            expires_at=datetime.now(UTC) + timedelta(minutes=1),
        )
        session.add(upload)
        session.commit()
        return upload

    upload = new_upload()
    with pytest.raises(DomainError, match="checksum"):
        artifact_service.complete_upload(session, upload, UploadComplete(checksum_sha256="0" * 64), project, user)
    upload = new_upload()
    FakeStorage.fail = True
    with pytest.raises(DomainError, match="could not be inspected"):
        artifact_service.complete_upload(session, upload, UploadComplete(checksum_sha256="0" * 64), project, user)
    FakeStorage.fail = False
    expired = new_upload()
    expired.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    with pytest.raises(DomainError, match="no longer active"):
        artifact_service.complete_upload(session, expired, UploadComplete(checksum_sha256="0" * 64), project, user)
    upload = new_upload()
    monkeypatch.setattr(
        artifact_service,
        "get_settings",
        lambda: SimpleNamespace(max_upload_bytes=1, upload_url_ttl_seconds=60),
    )
    with pytest.raises(DomainError, match="size limit"):
        artifact_service.complete_upload(
            session,
            upload,
            UploadComplete(checksum_sha256=hashlib.sha256(FakeStorage.data).hexdigest()),
            project,
            user,
        )


@pytest.mark.parametrize(
    ("filename", "content_type", "body"),
    [
        ("model.pdb", "chemical/x-pdb", b"ATOM      1  CA  GLY A   1\n"),
        ("model.cif", "chemical/x-mmcif", b"data_model\n#\n"),
        ("sequence.fasta", "text/plain", b">candidate\nMKT\n"),
        ("manifest.json", "application/json", json.dumps({"outputs": []}).encode()),
        ("results.csv", "text/csv", b"name,score\na,1\n"),
        ("report.pdf", "application/pdf", b"%PDF-1.7\n"),
    ],
)
def test_artifact_format_validation_accepts_supported_content(filename, content_type, body) -> None:
    artifact_service._validate_artifact_content(filename, content_type, body)


def test_artifact_format_validation_accepts_nonempty_archives() -> None:
    body = io.BytesIO()
    with zipfile.ZipFile(body, "w") as archive:
        archive.writestr("result.txt", "ok")
    artifact_service._validate_artifact_content("results.xlsx", "application/octet-stream", body.getvalue())


def test_artifact_format_validation_rejects_empty_archive() -> None:
    body = io.BytesIO()
    with zipfile.ZipFile(body, "w"):
        pass
    with pytest.raises(ValueError, match="archive_empty"):
        artifact_service._validate_artifact_content("results.zip", "application/zip", body.getvalue())


def test_complete_upload_records_structured_lineage(monkeypatch, service_session) -> None:
    session, user, project = service_session
    monkeypatch.setattr(artifact_service, "ObjectStorage", FakeStorage)
    parent = Artifact(
        project_id=project.id,
        created_by=user.id,
        artifact_type="structure",
        filename="parent.pdb",
        content_type="chemical/x-pdb",
        object_key="projects/parent",
        size_bytes=len(FakeStorage.data),
        checksum_sha256="1" * 64,
        lineage={},
    )
    upload = ArtifactUpload(
        project_id=project.id,
        created_by=user.id,
        filename="child.pdb",
        artifact_type="structure",
        content_type="chemical/x-pdb",
        object_key="staging/child",
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    session.add_all([parent, upload])
    session.commit()
    child = artifact_service.complete_upload(
        session,
        upload,
        UploadComplete(
            checksum_sha256=hashlib.sha256(FakeStorage.data).hexdigest(),
            lineage_edges=[
                ArtifactLineageEdgeCreate(
                    parent_artifact_id=parent.id, relation="derived_from", details={"step": "refine"}
                )
            ],
        ),
        project,
        user,
    )
    edge = session.scalar(select(ArtifactLineageEdge).where(ArtifactLineageEdge.child_artifact_id == child.id))
    assert edge is not None and edge.parent_artifact_id == parent.id


@pytest.mark.parametrize(
    ("filename", "content_type", "body"),
    [
        ("model.pdb", "chemical/x-pdb", b"HEADER only\n"),
        ("model.cif", "chemical/x-mmcif", b"loop_\n"),
        ("sequence.fasta", "text/plain", b"MKT\n"),
        ("manifest.json", "application/json", b"{"),
        ("results.csv", "text/csv", b""),
        ("report.pdf", "application/pdf", b"not a pdf"),
    ],
)
def test_artifact_format_validation_rejects_invalid_content(filename, content_type, body) -> None:
    with pytest.raises((ValueError, json.JSONDecodeError)):
        artifact_service._validate_artifact_content(filename, content_type, body)


def test_complete_upload_rejects_invalid_declared_format(monkeypatch, service_session) -> None:
    session, user, project = service_session

    class InvalidPdbStorage(FakeStorage):
        data = b"HEADER without coordinates\n"
        removed: str | None = None

        def remove(self, key: str) -> None:
            type(self).removed = key

    monkeypatch.setattr(artifact_service, "ObjectStorage", InvalidPdbStorage)
    upload = ArtifactUpload(
        project_id=project.id,
        created_by=user.id,
        filename="invalid.pdb",
        artifact_type="structure",
        content_type="chemical/x-pdb",
        object_key="staging/invalid",
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    session.add(upload)
    session.commit()
    checksum = hashlib.sha256(InvalidPdbStorage.data).hexdigest()

    with pytest.raises(DomainError, match="declared format"):
        artifact_service.complete_upload(session, upload, UploadComplete(checksum_sha256=checksum), project, user)
    session.refresh(upload)
    assert upload.status == "failed"
    assert upload.error == "artifact_format_invalid"
    assert InvalidPdbStorage.removed == "staging/invalid"
