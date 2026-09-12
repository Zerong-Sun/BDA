"""PostgreSQL/psql contract, always in a disposable container, never the app DB.

Enable with BDA_V2_RUN_SCHEDULER_DB_TESTS=1. No host ports are published.
"""
from __future__ import annotations

import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest

SQL = (Path(__file__).resolve().parents[1] / "deploy/postgres/scheduler.sql").read_text()
pytestmark = pytest.mark.skipif(
    os.environ.get("BDA_V2_RUN_SCHEDULER_DB_TESTS") != "1", reason="Opt-in disposable PostgreSQL test"
)


@pytest.fixture
def postgres():
    name = f"bda-scheduler-test-{uuid.uuid4().hex[:10]}"
    subprocess.run([
        "docker", "run", "-d", "--name", name, "--network", "none",
        "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "-e", "POSTGRES_USER=bda",
        "-e", "POSTGRES_DB=bda_v2", "postgres:17-alpine",
    ], check=True, capture_output=True)
    try:
        for _ in range(100):
            # The image's temporary init server accepts socket connections before
            # bda_v2 exists, then shuts down. TCP is enabled only on final startup.
            ready = subprocess.run(["docker", "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "bda", "-d", "bda_v2"],
                                   capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(0.1)
        else:
            pytest.fail("Disposable PostgreSQL did not start")
        yield name
    finally:
        subprocess.run(["docker", "rm", "-f", name], check=True, capture_output=True)


def psql(container, sql, password="x" * 40):
    return subprocess.run([
        "docker", "exec", "-i", container, "sh", "-c",
        'IFS= read -r BDA_V2_SCHEDULER_PASSWORD; export BDA_V2_SCHEDULER_PASSWORD; '
        'exec psql -X -v ON_ERROR_STOP=1 -At -U bda -d bda_v2',
    ], input=password + "\n" + sql, text=True, capture_output=True)


def test_scheduler_sql_rejects_short_password_with_nonzero_exit(postgres):
    result = psql(postgres, SQL, password="short")
    assert result.returncode != 0
    assert "must contain at least 32 characters" in result.stderr
    assert psql(postgres, "select count(*) from pg_roles where rolname='bda_scheduler'").stdout.strip() == "0"


def test_scheduler_sql_permissions_defaults_and_idempotent_reapplication(postgres):
    assert psql(postgres, "create table scheduler_existing_test(id serial primary key)").returncode == 0
    assert psql(postgres, SQL).returncode == 0
    assert psql(postgres, SQL).returncode == 0
    assert psql(postgres, "create table scheduler_future_test(id serial primary key)").returncode == 0
    assert psql(postgres, "alter table scheduler_existing_test enable row level security; "
                "alter table scheduler_existing_test force row level security").returncode == 0
    result = psql(postgres, """
        select rolsuper, rolcreatedb, rolcreaterole, rolbypassrls, rolinherit from pg_roles where rolname='bda_scheduler';
        set role bda_scheduler;
        insert into scheduler_existing_test default values;
        insert into scheduler_future_test default values;
        update scheduler_future_test set id=id;
        select count(*) from scheduler_future_test;
        delete from scheduler_future_test;
        select has_schema_privilege(current_user,'public','CREATE');
    """)
    assert result.returncode == 0, result.stderr
    assert "f|f|f|t|f" in result.stdout
    assert result.stdout.strip().endswith("f")
    denied = psql(postgres, "set role bda_scheduler; create table must_not_exist(id int)")
    assert denied.returncode != 0 and "permission denied" in denied.stderr


def test_scheduler_sql_rejects_existing_elevated_role_without_rotating_password(postgres):
    assert psql(postgres, SQL).returncode == 0
    assert psql(postgres, "alter role bda_scheduler superuser").returncode == 0
    before = psql(postgres, "select rolpassword from pg_authid where rolname='bda_scheduler'").stdout
    result = psql(postgres, SQL, password="different" * 8)
    assert result.returncode != 0 and "unexpected capabilities" in result.stderr
    after = psql(postgres, "select rolpassword from pg_authid where rolname='bda_scheduler'").stdout
    assert before == after
