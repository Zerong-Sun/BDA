import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from backend_v2.app.registry import tasks
from backend_v2.app.registry.health import probe_compute_node


def test_server_registration_never_certifies_local_runtime(monkeypatch):
    assert probe_compute_node(backend="docker", queue=None, server_id=uuid.uuid4(), labels={})[0] == "unverified"


@pytest.mark.parametrize("output,expected", [("QUEUE_NAME PRIO STATUS MAX\nv3-64 30 Open:Active -", "healthy"), ("v3-64 30 Closed:Inact -", "unhealthy"), ("other 30 Open:Active -", "unhealthy")])
def test_lsf_requires_requested_open_queue(monkeypatch, output, expected):
    monkeypatch.setattr("backend_v2.app.registry.health.get_settings", lambda: SimpleNamespace(lsf_ssh_host="fixture"))
    def run(command, **kwargs):
        assert command == "LC_ALL=C bqueues v3-64"
        assert kwargs == {"check": False, "timeout": 20}
        return SimpleNamespace(returncode=0, stdout=output)
    monkeypatch.setattr("backend_v2.app.compute.adapters.LSFAdapter", lambda: SimpleNamespace(transport=SimpleNamespace(run=run)))
    assert probe_compute_node(backend="lsf", queue="v3-64", server_id=None, labels={})[0] == expected


def test_probe_failure_is_not_configuration_success(monkeypatch):
    monkeypatch.setattr("backend_v2.app.registry.health.get_settings", lambda: SimpleNamespace(lsf_ssh_host="fixture"))
    def fail(): raise RuntimeError("sensitive transport details")
    monkeypatch.setattr("backend_v2.app.compute.adapters.LSFAdapter", fail)
    status, error = probe_compute_node(backend="lsf", queue="q", server_id=None, labels={})
    assert status == "unhealthy" and "sensitive" not in error


@pytest.mark.parametrize("enabled,status", [(True,"healthy"),(False,"disabled")])
def test_worker_updates_public_health_fields(monkeypatch, enabled, status):
    node = SimpleNamespace(version=1, enabled=enabled, backend="lsf", queue="q", server_id=None, labels={}, health_status="unknown")
    @contextmanager
    def scope(): yield SimpleNamespace(get=lambda *a, **k: node)
    monkeypatch.setattr(tasks, "session_scope", scope)
    monkeypatch.setattr("backend_v2.app.registry.health.probe_compute_node", lambda **k: ("healthy",None))
    assert tasks.registry_compute_node_health.run(str(uuid.uuid4()))["status"] == status
    assert node.health_status == status and node.health_checked_at and node.version == 2
