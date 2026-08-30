"""A SQLite test engine that behaves like the database this runs against.

SQLite ignores foreign keys unless each connection asks for them. Every test
engine here was created without asking, so `ON DELETE CASCADE` and
`ON DELETE SET NULL` — which the models rely on throughout — did nothing in
tests while doing exactly what they say on Postgres. Delete semantics were, in
effect, untested: a test could assert a child row was gone and pass because
nothing had tried to remove it.

`enforce_foreign_keys(engine)` attaches the pragma to every new connection.
There is no conftest.py in this suite by convention, so tests import this
directly, the same way they import `_research_data`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, event


def enforce_foreign_keys(engine: Engine) -> Engine:
    """Make this engine honour foreign keys, and return it for chaining."""

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def drop_all(engine: Engine, metadata: Any) -> None:
    """Tear a test schema down with foreign keys momentarily off.

    `projects.primary_target_id` and `targets.project_id` reference each other,
    so the table graph has a cycle and no drop order satisfies it while the
    constraints are live. Enforcement matters for what the tests assert, not for
    discarding the schema afterwards.
    """
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        metadata.drop_all(connection)
    # StaticPool keeps the in-memory SQLite connection alive after the schema is
    # dropped. Explicit disposal makes fixture ownership complete and prevents
    # Python 3.13 from reporting the connection later as a ResourceWarning.
    engine.dispose()
