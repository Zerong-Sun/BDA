"""Account writes under production RLS and rollback-compatible schema upgrades."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from threading import Event

import pytest
from alembic.config import Config
from backend_v2.app.audit.models import AuditLog
from backend_v2.app.core import config as settings_module
from backend_v2.app.core.database import set_request_rls_context
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity import account_service
from backend_v2.app.identity.account_schemas import AccountGrantCreate, RegisterRequest
from backend_v2.app.identity.models import AccountGrant, Organization, OrganizationMember, RefreshSession, User
from backend_v2.app.identity.service import authenticate, hash_password, issue_refresh_token
from backend_v2.app.projects.models import Project
from sqlalchemy import create_engine, delete, event, inspect, select, text, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from alembic import command

pytestmark = pytest.mark.skipif(os.getenv("BDA_V2_RUN_DB_TESTS") != "1", reason="PostgreSQL integration disabled")


@pytest.fixture
def account_database(monkeypatch):
    """Migrate an isolated database, never change the configured database's schema."""
    settings = settings_module.get_settings()
    source = make_url(settings.database_url)
    name = "bda_account_" + uuid.uuid4().hex
    admin = create_engine(source, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    target = source.set(database=name)
    engine = create_engine(target, poolclass=NullPool)
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "backend_v2/alembic.ini"))
    config.set_main_option("script_location", str(root / "backend_v2/alembic"))
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings.model_copy(update={
        "database_url": target.render_as_string(hide_password=False),
        "maintenance_database_url": None, "maintenance_database_role": None,
    }))
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield engine, config
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()


@pytest.fixture
def account_role(account_database):
    engine, config = account_database
    command.upgrade(config, "head")
    role = "bda_account_api_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
        connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role}"')
        connection.exec_driver_sql(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{role}"')
    try:
        yield engine, role
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql(f'DROP OWNED BY "{role}"')
            connection.exec_driver_sql(f'DROP ROLE "{role}"')


def _api_role(session, role):
    session.execute(text(f'SET LOCAL ROLE "{role}"'))
    assert session.execute(text(
        "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
    )).one() == (False, False)


def _assert_anonymous_fence(session):
    assert not session.scalar(text("SELECT current_setting('bda.account_audit_user_id', true)"))
    assert not session.scalar(text("SELECT current_setting('bda.user_id', true)"))
    assert session.scalar(text("SELECT current_setting('bda.is_global_admin', true)")) != "true"
    assert list(session.scalars(select(Project.id))) == []
    assert list(session.scalars(select(AuditLog.id))) == []


@pytest.mark.parametrize("mode", ["open", "invite"])
def test_verified_account_flows_commit_under_production_role(account_role, monkeypatch, mode):
    engine, role = account_role
    monkeypatch.setattr(account_service.get_settings(), "registration_mode", mode)
    with Session(engine, expire_on_commit=False) as owner:
        admin = User(username="account-admin", display_name="Admin", role="admin", password_hash=hash_password("Old-pass-123"))
        org = Organization(name="Account test team")
        owner.add_all([admin, org])
        owner.flush()
        owner.add(Project(organization_id=org.id, owner_id=admin.id, name="Hidden", project_type="test"))
        code = None
        if mode == "invite":
            _, code = account_service.issue_grant(owner, AccountGrantCreate(
                purpose="invitation", username="new-account", organization_id=org.id, member_role="viewer",
            ), admin)
        owner.commit()
    with Session(engine, expire_on_commit=False) as session:
        _api_role(session, role)
        user = account_service.register_account(session, RegisterRequest(
            username="new-account", display_name="New account", password="Old-pass-123", invitation_token=code,
        ))
        _assert_anonymous_fence(session)
        issue_refresh_token(session, user)
        session.commit()
    with Session(engine) as session:
        _api_role(session, role)
        set_request_rls_context(session, user_id=user.id, is_global_admin=False)
        account_service.change_password(session, user, "Old-pass-123", "Changed-pass-123", user.version)
        assert not session.scalar(text("SELECT current_setting('bda.account_audit_user_id', true)"))
        assert session.scalar(text("SELECT current_setting('bda.user_id', true)")) == str(user.id)
        assert session.scalar(text("SELECT current_setting('bda.is_global_admin', true)")) == "false"
        session.commit()
    # Recovery of even an administrator must never acquire administrator/project
    # access in this otherwise anonymous request.
    for target in (user, admin):
        with Session(engine) as owner:
            grant, recovery = account_service.issue_grant(owner, AccountGrantCreate(
                purpose="password_reset", username=target.username,
            ), admin)
            grant_id = grant.id
            owner.commit()
        with Session(engine) as session:
            _api_role(session, role)
            account_service.reset_password(session, recovery, "Reset-pass-123")
            _assert_anonymous_fence(session)
            session.commit()
        with Session(engine) as owner:
            assert authenticate(owner, target.username, "Reset-pass-123").id == target.id
            assert owner.get(AccountGrant, grant_id).used_at is not None
    with Session(engine) as owner:
        logs = list(owner.scalars(select(AuditLog).where(AuditLog.actor_id == user.id).order_by(AuditLog.created_at)))
        assert [row.action for row in logs] == ["account.register", "account.password.change", "account.password.reset"]
        assert all(row.entity_id == user.id and row.project_id is None for row in logs)
        assert all(row.revoked_at is not None for row in owner.scalars(select(RefreshSession).where(RefreshSession.user_id == user.id)))
        assert owner.get(User, user.id).version == 3


def test_account_policy_is_insert_only_and_rejects_unrelated_rows(account_role, monkeypatch):
    engine, role = account_role
    monkeypatch.setattr(account_service.get_settings(), "registration_mode", "open")
    with Session(engine, expire_on_commit=False) as owner:
        user = account_service.register_account(owner, RegisterRequest(
            username="fenced-account", display_name="Fenced", password="Old-pass-123",
        ))
        other = User(username="other-account", display_name="Other", role="researcher")
        org = Organization(name="Other organization")
        owner.add_all([other, org])
        owner.flush()
        project = Project(organization_id=org.id, owner_id=other.id, name="Other", project_type="test")
        owner.add(project)
        owner.commit()
        own_org = owner.scalar(select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user.id))
    with Session(engine) as session:
        _api_role(session, role)
        # Failed credential verification must leave neither an audit nor context.
        with pytest.raises(DomainError):
            account_service.change_password(session, user, "Wrong-pass-123", "Changed-pass-123", user.version)
        _assert_anonymous_fence(session)
        own_row = dict(actor_id=user.id, entity_id=user.id, entity_type="user", action="account.password.change", trace_id="test")
        with pytest.raises(DBAPIError), session.begin_nested():
            session.execute(AuditLog.__table__.insert().values(**own_row))
        session.execute(text("SELECT set_config('bda.account_audit_user_id', :id, true)"), {"id": str(user.id)})
        for invalid in [
            {"actor_id": other.id}, {"entity_id": other.id}, {"entity_type": "project"},
            {"action": "account.grant.issue"}, {"action": "project.create"},
            {"project_id": project.id}, {"organization_id": own_org},
            {"action": "account.register", "organization_id": org.id},
            {"action": "account.register", "organization_id": None},
        ]:
            with pytest.raises(DBAPIError), session.begin_nested():
                session.execute(AuditLog.__table__.insert().values(**(own_row | invalid)))
        session.execute(AuditLog.__table__.insert().values(**own_row))
        assert list(session.scalars(select(AuditLog.id))) == []
        assert session.execute(update(AuditLog).values(result="tampered")).rowcount == 0
        assert session.execute(delete(AuditLog)).rowcount == 0
        assert list(session.scalars(select(Project.id))) == []
        session.rollback()
        _api_role(session, role)
        _assert_anonymous_fence(session)
    with Session(engine) as owner:
        logs = list(owner.scalars(select(AuditLog).where(AuditLog.actor_id == user.id)))
        assert len(logs) == 1 and logs[0].action == "account.register" and logs[0].result == "success"


def _legacy_refresh_insert(connection, user_id):
    identifier = uuid.uuid4()
    connection.execute(text("""
        INSERT INTO refresh_sessions (id, user_id, token_hash, expires_at, created_at)
        VALUES (:id, :user_id, :hash, now() + interval '1 day', now())
    """), {"id": identifier, "user_id": user_id, "hash": identifier.hex})
    return identifier


@pytest.mark.parametrize("previous", ["0074_research_decision_contract", "0075_account_access"])
def test_legacy_refresh_writers_survive_atomic_upgrade_and_migration_reversal(account_database, previous):
    engine, config = account_database
    command.upgrade(config, "0074_research_decision_contract")
    with Session(engine, expire_on_commit=False) as owner:
        user = User(username="legacy-account", display_name="Legacy", role="researcher")
        owner.add(user)
        owner.commit()
    with engine.begin() as connection:
        existing = _legacy_refresh_insert(connection, user.id)
    command.upgrade(config, previous)
    # A pre-upgrade hook holds PostgreSQL's DDL lock until both 0075 and 0076
    # commit. An old image's concurrent insert must wait, then see the default.
    attempted = Event()
    future = None

    def old_api_writer():
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == previous
            attempted.set()
            return _legacy_refresh_insert(connection, user.id)

    with ThreadPoolExecutor(max_workers=1) as pool:
        def during_upgrade(_conn, _cursor, statement, *_args):
            nonlocal future
            if "CREATE POLICY audit_logs_verified_account_insert" in statement:
                future = pool.submit(old_api_writer)
                assert attempted.wait(5)
                with pytest.raises(TimeoutError):
                    future.result(0.1)

        event.listen(Engine, "before_cursor_execute", during_upgrade)
        try:
            command.upgrade(config, "head")
        finally:
            event.remove(Engine, "before_cursor_execute", during_upgrade)
        assert future is not None
        concurrent = future.result(10)
    with engine.begin() as connection:
        after = _legacy_refresh_insert(connection, user.id)
        rows = connection.execute(text("SELECT id, family_id, realm FROM refresh_sessions")).all()
        assert {row.id for row in rows} == {existing, concurrent, after}
        assert next(row.family_id for row in rows if row.id == existing) == existing
        assert len({row.family_id for row in rows}) == 3
        assert all(row.realm == "bda" for row in rows)
    command.check(config)
    command.downgrade(config, "0075_account_access")
    with engine.connect() as connection:
        columns = {column["name"]: column for column in inspect(connection).get_columns("refresh_sessions")}
        assert columns["family_id"]["default"] is None
        assert connection.scalar(text("SELECT count(*) FROM refresh_sessions")) == 3
        assert not connection.scalar(text("SELECT count(*) FROM pg_policies WHERE policyname = 'audit_logs_verified_account_insert'"))
        assert connection.scalar(text("SELECT count(*) FROM pg_policies WHERE policyname = 'audit_logs_project_fence'")) == 1
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
