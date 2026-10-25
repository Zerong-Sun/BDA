"""The real request connection must not bypass or own its tenant tables."""
from __future__ import annotations

import os
import uuid

import pytest
from backend_v2.app.platform.repository import PlatformRepository
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(os.getenv("BDA_V2_RUN_DB_TESTS") != "1", reason="requires isolated PostgreSQL")


def test_request_role_check_rejects_superuser_bypassrls_and_table_ownership():
    engine = create_engine(os.environ["BDA_V2_DATABASE_URL"])
    role = "security_probe_" + uuid.uuid4().hex
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                # Names are generated locally from a fixed prefix and UUID hex.
                connection.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS'))
                connection.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
                connection.execute(text(f'SET LOCAL ROLE "{role}"'))
                with Session(bind=connection) as session:
                    assert PlatformRepository(session).request_role_is_restricted()
                    connection.execute(text('RESET ROLE'))
                    connection.execute(text(f'ALTER ROLE "{role}" BYPASSRLS'))
                    connection.execute(text(f'SET LOCAL ROLE "{role}"'))
                    assert not PlatformRepository(session).request_role_is_restricted()
                    connection.execute(text('RESET ROLE'))
                    connection.execute(text(f'ALTER ROLE "{role}" NOBYPASSRLS'))
                    connection.execute(text(f'CREATE TABLE public."{role}" (id integer)'))
                    connection.execute(text(f'ALTER TABLE public."{role}" OWNER TO "{role}"'))
                    connection.execute(text(f'SET LOCAL ROLE "{role}"'))
                    assert not PlatformRepository(session).request_role_is_restricted()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
