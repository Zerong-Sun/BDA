"""Opt-in real PostgreSQL migration, locking, RLS and worker lifecycle verification.

Set BDA_GATE_TEST_DATABASE_URL to an isolated disposable PostgreSQL database.
Each test creates and drops only its own randomly named schema/role.
"""

from __future__ import annotations

import importlib
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from backend_v2.app.core.config import get_settings
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project
from backend_v2.app.registry.models import ModelPlugin
from backend_v2.app.workflows.gate_runtime import run_gate
from backend_v2.app.workflows.gate_schemas import GateRelease
from backend_v2.app.workflows.gate_service import release_gate
from backend_v2.app.workflows.models import GateEvaluation
from backend_v2.tests.test_workflow_gates import runtime_fixture
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

DATABASE_URL = os.getenv("BDA_GATE_TEST_DATABASE_URL") or (
    get_settings().database_url if os.getenv("BDA_V2_RUN_DB_TESTS") == "1" else None
)
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="Disposable PostgreSQL not configured")


@pytest.fixture
def pg_env():
    assert DATABASE_URL is not None
    url = DATABASE_URL
    admin = create_engine(url)
    schema = "gate_review_" + uuid.uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        # Exercise the actual migration from the preceding table shape.
        migration = importlib.import_module("backend_v2.alembic.versions.0056_workflow_gates")
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE workflow_gate_evaluations, workflow_results")
            connection.exec_driver_sql("ALTER TABLE workflow_nodes DROP COLUMN configuration")
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
        with Session(engine, expire_on_commit=False) as s:
            user, org = (
                User(username="review", display_name="Review", role="admin"),
                Organization(name="Synthetic review"),
            )
            s.add_all([user, org])
            s.flush()
            s.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
            project = Project(organization_id=org.id, owner_id=user.id, name="Synthetic gate", project_type="design")
            producer = ModelPlugin(
                plugin_key="review-source",
                plugin_version="1",
                name="Source",
                command="true",
                container_image="synthetic:1",
            )
            consumer = ModelPlugin(
                plugin_key="review-target",
                plugin_version="1",
                name="Target",
                command="true",
                container_image="synthetic:1",
            )
            s.add_all([project, producer, consumer])
            s.flush()
            yield {
                "session": s,
                "user": user,
                "project": project,
                "producer": producer,
                "consumer": consumer,
                "engine": engine,
                "schema": schema,
            }
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_concurrent_release_is_idempotent_and_rls_is_enforced(pg_env):
    from backend_v2.app.compute.models import OutboxEvent

    s, w, _, _, _, gate, storage = runtime_fixture(pg_env, mode="review")
    run_gate(s, gate, storage)
    ids = [d["id"] for d in gate.decisions if d["passed"]]
    expected = gate.version
    s.commit()

    def release():
        with Session(pg_env["engine"]) as session:
            result = release_gate(
                w.id,
                gate.id,
                GateRelease(version=expected, selected_ids=ids),
                session,
                session.get(User, pg_env["user"].id),
            )
            session.commit()
            return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: release(), range(2)))
    assert results[0]["version"] == results[1]["version"] == expected + 1
    with Session(pg_env["engine"]) as session:
        assert len(list(session.scalars(select(OutboxEvent).where(OutboxEvent.topic == "gate.resume")))) == 1
    role = "gate_reader_" + uuid.uuid4().hex
    try:
        with pg_env["engine"].begin() as c:
            c.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOBYPASSRLS'))
            c.execute(text(f'GRANT USAGE ON SCHEMA "{pg_env["schema"]}" TO "{role}"'))
            c.execute(
                text(
                    f'GRANT SELECT ON workflow_gate_evaluations, workflow_results, projects, organization_members TO "{role}"'
                )
            )
        with pg_env["engine"].begin() as c:
            c.execute(text(f'SET LOCAL ROLE "{role}"'))
            assert list(c.scalars(select(GateEvaluation.id))) == []
            c.execute(text("SELECT set_config('bda.worker_project_id', :id, true)"), {"id": str(w.project_id)})
            assert list(c.scalars(select(GateEvaluation.id))) == [gate.id]
            c.execute(text("SELECT set_config('bda.worker_project_id', :id, true)"), {"id": str(uuid.uuid4())})
            assert list(c.scalars(select(GateEvaluation.id))) == []
    finally:
        with pg_env["engine"].begin() as c:
            c.execute(text(f'DROP OWNED BY "{role}"'))
            c.execute(text(f'DROP ROLE "{role}"'))


def test_worker_publishes_evaluating_and_reentry_does_not_duplicate_dispatch(pg_env, monkeypatch):
    from backend_v2.app.compute.models import OutboxEvent
    from backend_v2.app.workflows.gate_runtime import execute_gate

    s, _, _, _, target, gate, storage = runtime_fixture(pg_env)
    s.commit()

    @contextmanager
    def scope():
        with Session(pg_env["engine"], expire_on_commit=False) as session:
            yield session
            session.commit()

    monkeypatch.setattr("backend_v2.app.core.database.session_scope", scope)

    def checked_run(session, row):
        with Session(pg_env["engine"]) as reader:
            assert reader.get(GateEvaluation, gate.id).status == "evaluating"
        run_gate(session, row, storage)

    monkeypatch.setattr("backend_v2.app.workflows.gate_runtime.run_gate", checked_run)
    execute_gate(str(gate.id))
    monkeypatch.setattr(
        "backend_v2.app.workflows.gate_runtime.run_gate", lambda session, row: run_gate(session, row, storage)
    )
    execute_gate(str(gate.id))
    with Session(pg_env["engine"]) as session:
        assert session.get(GateEvaluation, gate.id).status == "released"
        dispatches = list(
            session.scalars(
                select(OutboxEvent).where(OutboxEvent.topic == "job.dispatch", OutboxEvent.aggregate_id == target.id)
            )
        )
        assert len(dispatches) == 1
