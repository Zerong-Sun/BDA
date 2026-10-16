"""Live PostgreSQL lock scope test. Uses random advisory keys, no table writes."""

import os
import uuid

import pytest
from backend_v2.app.copilot.records import _lock_record, _record_lock_key
from backend_v2.app.core.config import get_settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DATABASE_URL = os.getenv("BDA_GATE_TEST_DATABASE_URL") or (
    get_settings().database_url if os.getenv("BDA_V2_RUN_DB_TESTS") == "1" else None
)
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="PostgreSQL not configured")


def test_same_bot_serializes_without_blocking_other_operators_or_ordinary_reads():
    engine = create_engine(DATABASE_URL)
    project_id = uuid.uuid4()
    try:
        with Session(engine) as first, Session(engine) as second:
            second.execute(text("SET LOCAL lock_timeout = '1s'"))
            _lock_record(first, project_id, "conductor")
            own_key = _record_lock_key(project_id, "conductor")
            assert second.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": own_key}) is False
            _lock_record(second, project_id, "runner")
            _lock_record(second, uuid.uuid4(), "conductor")
            assert second.scalar(text("SELECT 1")) == 1
            # The projection holds no row/table locks: a project update cannot
            # conflict with it. Source writes have their own existing locks.
            relation_locks = first.scalar(
                text(
                    "SELECT count(*) FROM pg_locks WHERE pid=pg_backend_pid() AND locktype='relation' AND mode IN ('RowExclusiveLock','RowShareLock')"
                )
            )
            assert relation_locks == 0
            first.commit()
            assert second.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": own_key}) is True
    finally:
        engine.dispose()
