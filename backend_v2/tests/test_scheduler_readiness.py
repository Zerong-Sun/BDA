from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from backend_v2.app.platform import api, service
from fastapi import Response


@pytest.mark.parametrize("scheduler", ["absent", "stale", "wrong_build", "wrong_schema", "valid"])
@pytest.mark.parametrize("paused", [False, True])
def test_readiness_requires_current_scheduler_even_with_legacy_queue_override(monkeypatch, scheduler, paused):
    now = datetime.now(UTC)
    settings = SimpleNamespace(
        required_worker_queue_list=["research"], build_revision="test", schema_revision="head", redis_url="redis://unused",
        scheduler_dispatch_paused=paused,
    )
    rows = [SimpleNamespace(queues=["research"], build_revision="test", schema_revision="head", last_seen_at=now)]
    if scheduler != "absent":
        rows.append(SimpleNamespace(
            queues=["scheduler"],
            build_revision="old" if scheduler == "wrong_build" else "test",
            schema_revision="old" if scheduler == "wrong_schema" else "head",
            last_seen_at=now - timedelta(seconds=120) if scheduler == "stale" else now,
        ))
    repository = SimpleNamespace(
        ping=lambda: None,
        schema_revision=lambda: "head",
        recent_worker_heartbeats=lambda cutoff: [row for row in rows if row.last_seen_at >= cutoff],
    )
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    monkeypatch.setattr(service, "SessionFactory", lambda: nullcontext(None))
    monkeypatch.setattr(service, "PlatformRepository", lambda _: repository)
    monkeypatch.setattr(service, "Redis", SimpleNamespace(from_url=lambda _: SimpleNamespace(ping=lambda: True)))
    monkeypatch.setattr(service, "ObjectStorage", lambda: SimpleNamespace(healthy=lambda: True))
    response = Response()
    result = api.readiness(response)
    assert response.status_code == (200 if scheduler == "valid" and not paused else 503)
    assert result.checks["scheduler_dispatch"] == ("paused" if paused else "ok")
    assert result.checks["scheduler_heartbeat"] == ("ok" if scheduler == "valid" else "missing")
    assert result.checks["worker_heartbeats"] == ("ok" if scheduler == "valid" else "missing")
    assert result.checks["postgresql"] == "ok"


def test_readiness_database_failure_fails_closed(monkeypatch):
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(
        required_worker_queue_list=[], scheduler_dispatch_paused=False, redis_url="redis://unused"))

    def unavailable():
        raise ConnectionError("unavailable")

    monkeypatch.setattr(service, "SessionFactory", unavailable)
    monkeypatch.setattr(service, "Redis", SimpleNamespace(from_url=lambda _: SimpleNamespace(ping=lambda: True)))
    monkeypatch.setattr(service, "ObjectStorage", lambda: SimpleNamespace(healthy=lambda: True))
    response = Response()
    result = api.readiness(response)
    assert response.status_code == 503
    assert result.checks["scheduler_heartbeat"] == "unavailable"
    assert result.checks["worker_heartbeats"] == "unavailable"
    assert result.checks["postgresql"] == "unavailable"
