"""Cross-connection checks: row locks must survive credential races."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Barrier, Event

import pytest
from backend_v2.app.core.config import get_settings
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity import account_service
from backend_v2.app.identity.account_schemas import AccountGrantCreate, RegisterRequest
from backend_v2.app.identity.models import AccountGrant, Organization, User
from backend_v2.app.identity.service import hash_password, issue_refresh_token, rotate_refresh_token
from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.skipif(os.getenv("BDA_V2_RUN_DB_TESTS") != "1", reason="PostgreSQL integration disabled")


@pytest.fixture
def accounts(monkeypatch):
    monkeypatch.setattr(get_settings(), "registration_mode", "invite")
    engine = create_engine(get_settings().database_url)
    factory = sessionmaker(engine, autoflush=False, expire_on_commit=False)
    prefix = f"account-race-{uuid.uuid4().hex[:12]}"
    with factory.begin() as session:
        admin = User(username=prefix, display_name="Test", role="admin", password_hash=hash_password("Test-pass-123"))
        org = Organization(name=prefix)
        session.add_all([admin, org])
        session.flush()
    yield engine, factory, admin, org, prefix
    with factory.begin() as session:
        session.execute(delete(AccountGrant).where(AccountGrant.created_by == admin.id))
        session.execute(delete(User).where(User.username.startswith(prefix)))
        session.execute(delete(Organization).where(Organization.id == org.id))
    engine.dispose()


def test_invitation_is_consumed_once_across_connections(accounts):
    _, factory, admin, org, prefix = accounts
    with factory.begin() as session:
        _, code = account_service.issue_grant(
            session, AccountGrantCreate(purpose="invitation", username=prefix + "-new", organization_id=org.id), admin
        )
    barrier = Barrier(2)

    def register():
        barrier.wait(5)
        with factory.begin() as session:
            try:
                account_service.register_account(
                    session,
                    RegisterRequest(
                        username=prefix + "-new", display_name="Test", password="Test-pass-123", invitation_token=code
                    ),
                )
            except DomainError as exc:
                return exc.error_code
            return "created"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(register), pool.submit(register)
        assert sorted([first.result(10), second.result(10)]) == ["created", "invalid_account_code"]
    with factory() as session:
        assert len(list(session.scalars(select(User).where(User.username == prefix + "-new")))) == 1


@pytest.mark.parametrize("action", ["logout", "password"])
def test_credential_change_cannot_race_refresh_into_a_valid_session(accounts, action):
    _, factory, user, _, _ = accounts
    with factory.begin() as session:
        raw = issue_refresh_token(session, user)
    queried = Event()

    def mutate():
        with factory.begin() as session:

            def before_query(_connection, _cursor, statement, *_args):
                if "SELECT" in statement and "users" in statement:
                    queried.set()

            event.listen(session.connection(), "before_cursor_execute", before_query)
            if action == "logout":
                account_service.logout(session, raw)
            else:
                account_service.change_password(session, user, "Test-pass-123", "Updated-pass-123", user.version)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with factory() as session:
            _, rotated = rotate_refresh_token(session, raw)
            future = pool.submit(mutate)
            try:
                assert queried.wait(5)
                with pytest.raises(TimeoutError):
                    future.result(0.25)
            finally:
                session.commit()
        future.result(10)
    with factory.begin() as session, pytest.raises(DomainError, match="invalid or expired"):
        rotate_refresh_token(session, rotated)
