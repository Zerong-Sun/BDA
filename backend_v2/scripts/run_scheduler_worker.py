"""Start only the scheduler consumer after checking its database capability.

An empty/misconfigured scheduler env file must never fall back to the shared
application login. Do not print connection errors: they can contain credentials.
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

WORKER_COMMAND = [
    "celery", "-A", "backend_v2.app.compute.tasks.celery_app", "worker", "-Q", "scheduler",
    "--loglevel=info", "--concurrency=1", "--prefetch-multiplier=1",
]


def validate_database(url: str) -> None:
    try:
        parsed = make_url(url)
    except (ArgumentError, ValueError):
        raise ValueError("scheduler_database_url_invalid") from None
    if (parsed.drivername not in {"postgresql", "postgresql+psycopg"} or parsed.username != "bda_scheduler"
            or not parsed.password or not parsed.host or not parsed.database):
        raise ValueError("scheduler_database_login_required")
    engine = create_engine(url, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as connection:
            row = connection.execute(text("""
                SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole,
                       has_schema_privilege(current_user, 'public', 'CREATE') AS schema_create,
                       has_table_privilege(current_user, 'outbox_events', 'SELECT')
                         AND has_table_privilege(current_user, 'outbox_events', 'UPDATE') AS outbox_access,
                       has_table_privilege(current_user, 'worker_heartbeats', 'SELECT')
                         AND has_table_privilege(current_user, 'worker_heartbeats', 'INSERT')
                         AND has_table_privilege(current_user, 'worker_heartbeats', 'UPDATE') AS heartbeat_access
                FROM pg_roles WHERE rolname = current_user
            """)).mappings().one()
            if (row["rolsuper"] or row["rolcreatedb"] or row["rolcreaterole"] or row["schema_create"]
                    or not row["rolbypassrls"] or not row["outbox_access"] or not row["heartbeat_access"]):
                raise ValueError("scheduler_database_capabilities_invalid")
    finally:
        engine.dispose()


def main() -> int:
    if len(sys.argv) != 1:
        print("Scheduler startup does not accept queue/command overrides", file=sys.stderr)
        return 1
    try:
        validate_database(os.environ.get("BDA_V2_DATABASE_URL", ""))
    except Exception:
        print("Scheduler database configuration or permissions invalid; refusing startup", file=sys.stderr)
        return 1
    os.environ["BDA_V2_WORKER_QUEUES"] = "scheduler"
    os.execvp(WORKER_COMMAND[0], WORKER_COMMAND)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
