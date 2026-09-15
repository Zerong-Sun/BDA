from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from backend_v2.app.core.config import get_settings
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import User
from backend_v2.app.identity.service import issue_refresh_token, rotate_refresh_token
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.skipif(
    os.getenv("BDA_V2_RUN_DB_TESTS") != "1", reason="PostgreSQL integration test disabled"
)


def test_refresh_rotation_is_single_use_across_connections() -> None:
    engine = create_engine(get_settings().database_url)
    factory = sessionmaker(engine, autoflush=False, expire_on_commit=False)
    with factory.begin() as session:
        user = User(username=f"refresh-{uuid.uuid4().hex}", display_name="Refresh test", role="researcher")
        session.add(user)
        session.flush()
        raw = issue_refresh_token(session, user)
    queried = Event()

    def rotate_again() -> str:
        with factory.begin() as session:
            connection = session.connection()

            def before_query(_connection, _cursor, statement, *_args):
                if "SELECT" in statement and "refresh_sessions" in statement:
                    queried.set()

            event.listen(connection, "before_cursor_execute", before_query)
            try:
                rotate_refresh_token(session, raw)
            except DomainError as exc:
                return exc.error_code
            return "accepted_twice"

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with factory() as first:
                rotate_refresh_token(first, raw)
                # Do not flush: the read lock must protect the token before the
                # request UoW persists its revocation at commit.
                future = pool.submit(rotate_again)
                try:
                    assert queried.wait(5)
                    with pytest.raises(TimeoutError):
                        future.result(timeout=0.25)
                finally:
                    first.commit()
            assert future.result(timeout=5) == "invalid_refresh_token"
    finally:
        with factory.begin() as session:
            session.delete(session.get(User, user.id))
        engine.dispose()
