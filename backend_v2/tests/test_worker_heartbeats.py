"""Several queue workers on one machine must not overwrite each other's health."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from backend_v2.app.core import celery_app as worker
from backend_v2.app.platform.models import WorkerHeartbeat
from celery.worker.heartbeat import Heart
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def heartbeat_store(monkeypatch):
    engine = create_engine("sqlite+pysqlite://", poolclass=StaticPool)
    WorkerHeartbeat.__table__.create(engine)
    factory = sessionmaker(engine)
    monkeypatch.setattr(worker, "session_scope", factory.begin)
    monkeypatch.setattr(worker, "gethostname", lambda: "shared-host")
    yield factory
    engine.dispose()


def _publish(monkeypatch, name: str, queues: list[str]) -> None:
    monkeypatch.setattr(worker, "settings", SimpleNamespace(
        worker_queue_list=queues, build_revision="build", schema_revision="schema",
    ))
    # Celery sends the Heart, whose worker identity is on its event dispatcher.
    eventer = SimpleNamespace(hostname=name, on_enabled=set(), on_disabled=set())
    worker._publish_worker_heartbeat(Heart(timer=None, eventer=eventer))


def test_same_host_workers_keep_separate_queue_heartbeats(heartbeat_store, monkeypatch) -> None:
    _publish(monkeypatch, "ops@shared-host", ["dispatch", "scheduler"])
    _publish(monkeypatch, "bots@shared-host", ["research", "copilot"])
    _publish(monkeypatch, "ops@shared-host", ["dispatch", "scheduler"])

    with heartbeat_store() as session:
        rows = {row.instance_id: row for row in session.scalars(select(WorkerHeartbeat))}
        assert set(rows) == {"ops@shared-host", "bots@shared-host"}
        assert rows["ops@shared-host"].queues == ["dispatch", "scheduler"]
        assert rows["bots@shared-host"].queues == ["research", "copilot"]
        assert all(row.build_revision == "build" and row.schema_revision == "schema" for row in rows.values())


def test_unknown_sender_fallback_distinguishes_processes(heartbeat_store, monkeypatch) -> None:
    monkeypatch.setattr(worker, "settings", SimpleNamespace(
        worker_queue_list=["maintenance"], build_revision="build", schema_revision="schema",
    ))
    monkeypatch.setattr(worker, "getpid", lambda: 101, raising=False)
    worker._publish_worker_heartbeat(None)
    monkeypatch.setattr(worker, "getpid", lambda: 202, raising=False)
    worker._publish_worker_heartbeat(None)

    with heartbeat_store() as session:
        assert set(session.scalars(select(WorkerHeartbeat.instance_id))) == {"shared-host:101", "shared-host:202"}


def test_unavailable_heartbeat_storage_does_not_fail_the_worker(monkeypatch) -> None:
    def unavailable():
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(worker, "session_scope", unavailable)
    _publish(monkeypatch, "bots@shared-host", ["copilot"])
