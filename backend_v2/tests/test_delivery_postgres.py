"""Real MVCC, RLS and outer-transaction checks in a disposable PostgreSQL schema."""
from __future__ import annotations

import hashlib
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.candidates.models import Candidate, CandidateMetric
from backend_v2.app.core.config import get_settings
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.delivery import bundle, tasks
from backend_v2.app.delivery.models import DeliveryPackage
from backend_v2.app.delivery.schemas import DeliveryCreate
from backend_v2.app.delivery.service import create_delivery
from backend_v2.app.experiments.models import ExperimentResult
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.wetlab.analysis import record_measured_metric
from backend_v2.app.wetlab.service import review_analysis
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(os.getenv("BDA_V2_RUN_DB_TESTS") != "1", reason="Disposable PostgreSQL not configured")


@pytest.fixture
def pg_env():
    url = get_settings().database_url
    admin = create_engine(url)
    schema = "delivery_review_" + uuid.uuid4().hex
    with admin.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        with Session(engine, expire_on_commit=False) as session:
            user = User(username="delivery-owner", display_name="Synthetic reviewer", role="admin")
            other_user = User(username="other-owner", display_name="Synthetic other", role="researcher")
            organization = Organization(name="Synthetic delivery")
            session.add_all([user, other_user, organization])
            session.flush()
            project = Project(organization_id=organization.id, owner_id=user.id, name="Synthetic", project_type="design")
            other_project = Project(organization_id=organization.id, owner_id=other_user.id, name="Other", project_type="design")
            session.add_all([project, other_project])
            session.flush()
            raw = b"synthetic curve"
            artifact = Artifact(project_id=project.id, created_by=user.id, artifact_type="raw",
                                filename="curve.csv", content_type="text/csv", object_key="synthetic/curve",
                                size_bytes=len(raw), checksum_sha256=hashlib.sha256(raw).hexdigest())
            candidate = Candidate(project_id=project.id, candidate_key="A", name="Original")
            foreign = Candidate(project_id=other_project.id, candidate_key="B", name="Foreign")
            session.add_all([artifact, candidate, foreign])
            session.flush()
            result = ExperimentResult(project_id=project.id, created_by=user.id, candidate_id=candidate.id,
                                      source_artifact_id=artifact.id, experiment_type="bli_affinity", value=12.0,
                                      unit="nM", result_metadata={"instrument_qc_review": {"status": "accepted"},
                                      "results": {"quality_control": {"version": "instrument-qc-v1"}}})
            session.add(result)
            session.flush()
            record_measured_metric(session, result)
            session.commit()
            yield {"engine": engine, "admin": admin, "schema": schema, "user": user.id,
                   "project": project.id, "other_project": other_project.id, "other_user": other_user.id,
                   "candidate": candidate.id, "foreign": foreign.id, "result": result.id, "raw": raw}
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


def test_concurrent_qc_rejection_cannot_split_frozen_measurement_and_source(pg_env, monkeypatch):
    metric_read, review_committed = threading.Event(), threading.Event()
    original = bundle._bounded

    def pause_after_metric_read(session, query):
        rows = original(session, query)
        if query.column_descriptions[0]["entity"] is CandidateMetric:
            assert session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
            assert session.scalar(text("SHOW transaction_read_only")) == "on"
            metric_read.set()
            assert review_committed.wait(10), "Concurrent review did not commit"
        return rows

    monkeypatch.setattr(bundle, "_bounded", pause_after_metric_read)

    def freeze():
        with Session(pg_env["engine"]) as session:
            return bundle.snapshot_selection(session, pg_env["project"], {})

    with ThreadPoolExecutor(max_workers=1) as pool:
        frozen = pool.submit(freeze)
        try:
            assert metric_read.wait(10), "Snapshot did not reach metric read"
            with Session(pg_env["engine"]) as session:
                row, recorded = review_analysis(session, session.get(Project, pg_env["project"]),
                    pg_env["result"], session.get(User, pg_env["user"]), expected=1, accept=False,
                    rationale="Synthetic reviewer rejects an unidentifiable fit")
                assert row.result_metadata["instrument_qc_review"]["status"] == "rejected"
                assert not recorded
                session.commit()
        finally:
            review_committed.set()
        snapshot = frozen.result(timeout=10)
    assert len(snapshot["metrics"]) == 1
    assert snapshot["experiment_results"][0]["result_metadata"]["instrument_qc_review"]["status"] == "accepted"
    assert snapshot["consistency"] == "postgresql-repeatable-read-committed"
    with Session(pg_env["engine"]) as session:
        assert not list(session.scalars(select(CandidateMetric)))
        assert session.get(ExperimentResult, pg_env["result"]).result_metadata["instrument_qc_review"]["status"] == "rejected"


@pytest.mark.parametrize("context_kind", ["user", "admin", "worker"])
def test_snapshot_inherits_effective_role_search_path_and_rls_context(pg_env, context_kind):
    role = "delivery_reader_" + uuid.uuid4().hex
    schema = pg_env["schema"]
    access = """(
        current_setting('bda.is_global_admin', true) = 'true'
        OR project_id::text = current_setting('bda.worker_project_id', true)
        OR project_id IN (SELECT id FROM projects WHERE owner_id::text = current_setting('bda.user_id', true))
    )"""
    try:
        with pg_env["engine"].begin() as connection:
            connection.exec_driver_sql(f'CREATE ROLE "{role}" NOLOGIN NOBYPASSRLS')
            connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
            connection.exec_driver_sql(f'GRANT SELECT ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"')
            for table in ("candidates", "artifacts", "experiment_results"):
                connection.exec_driver_sql(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
                connection.exec_driver_sql(f"CREATE POLICY delivery_scope ON {table} USING ({access})")
            connection.exec_driver_sql("ALTER TABLE candidate_metrics ENABLE ROW LEVEL SECURITY")
            connection.exec_driver_sql("CREATE POLICY delivery_scope ON candidate_metrics USING "
                                       "(candidate_id IN (SELECT id FROM candidates))")
        # Deliberately use the engine without schema options. Both search_path and
        # the non-owner role must be copied from the live outer transaction.
        with Session(pg_env["admin"]) as session:
            session.execute(text("SELECT set_config('search_path', :schema, true)"), {"schema": schema})
            session.execute(text(f'SET LOCAL ROLE "{role}"'))
            session.execute(text("""SELECT set_config('bda.user_id', :user_id, true),
                set_config('bda.is_global_admin', :is_admin, true),
                set_config('bda.worker_project_id', :project_id, true)"""), {
                    "user_id": str(pg_env["user"]) if context_kind == "user" else "",
                    "is_admin": "true" if context_kind == "admin" else "false",
                    "project_id": str(pg_env["project"]) if context_kind == "worker" else "",
                })
            snapshot = bundle.snapshot_selection(session, pg_env["project"], {})
            assert [row["id"] for row in snapshot["candidates"]] == [str(pg_env["candidate"])]
            assert len(snapshot["metrics"]) == len(snapshot["experiment_results"]) == len(snapshot["artifacts"]) == 1
            if context_kind != "admin":
                with pytest.raises(DomainError, match="unavailable"):
                    bundle.snapshot_selection(session, pg_env["other_project"], {"candidate_ids": [str(pg_env["foreign"])]})
            assert session.scalar(text("SELECT current_user")) == role
            assert session.in_transaction()
    finally:
        with pg_env["engine"].begin() as connection:
            connection.exec_driver_sql(f'DROP OWNED BY "{role}"')
            connection.exec_driver_sql(f'DROP ROLE "{role}"')


@pytest.mark.parametrize("flush", [False, True])
def test_uncommitted_changes_are_rejected_without_committing_or_rolling_back(pg_env, flush):
    with Session(pg_env["engine"]) as session:
        row = session.get(Candidate, pg_env["candidate"])
        row.name = "Not committed"
        if flush:
            session.flush()
        with pytest.raises(DomainError) as error:
            bundle.snapshot_selection(session, pg_env["project"], {})
        assert error.value.error_code == "delivery_uncommitted_changes"
        assert session.in_transaction() and session.is_active
        assert row.name == "Not committed"
        with Session(pg_env["engine"]) as other:
            assert other.get(Candidate, row.id).name == "Original"
    with Session(pg_env["engine"]) as session:
        assert session.get(Candidate, pg_env["candidate"]).name == "Original"


def test_locked_legacy_worker_exports_committed_rows_and_duplicate_is_ignored(pg_env, monkeypatch):
    with Session(pg_env["engine"]) as session:
        package = DeliveryPackage(project_id=pg_env["project"], created_by=pg_env["user"], name="Legacy", selection={})
        session.add(package)
        session.commit()
        identifier = package.id

    class Storage:
        def read_bytes(self, key, *, max_bytes):
            assert key == "synthetic/curve" and len(pg_env["raw"]) <= max_bytes
            return pg_env["raw"]

        def put_bytes(self, key, data, content_type):
            assert data[:2] == b"PK"

    @contextmanager
    def scope():
        with Session(pg_env["engine"]) as session:
            yield session
            session.commit()

    monkeypatch.setattr(tasks, "session_scope", scope)
    monkeypatch.setattr(tasks, "ObjectStorage", Storage)
    assert tasks.build_delivery_package.run(str(identifier))["status"] == "available"
    assert tasks.build_delivery_package.run(str(identifier))["status"] == "ignored"
    with Session(pg_env["engine"]) as session:
        package = session.get(DeliveryPackage, identifier)
        assert package.selection["_snapshot"]["consistency"] == "postgresql-repeatable-read-committed"


def test_request_freeze_does_not_commit_the_outer_package_transaction(pg_env):
    with Session(pg_env["engine"]) as session:
        package, _ = create_delivery(session, session.get(Project, pg_env["project"]),
            DeliveryCreate(name="Rolled back request"), session.get(User, pg_env["user"]))
        identifier = package.id
        assert package.selection["consistency"] == "postgresql-repeatable-read-committed"
        assert session.in_transaction()
        with Session(pg_env["engine"]) as other:
            assert other.get(DeliveryPackage, identifier) is None
        # Simulate an API exception after the domain service returned.
        session.rollback()
    with Session(pg_env["engine"]) as other:
        assert other.get(DeliveryPackage, identifier) is None
