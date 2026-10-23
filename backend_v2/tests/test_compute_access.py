from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from backend_v2.app.compute.access import lsf_access_blocker, lsf_target_snapshot, require_lsf_access
from backend_v2.app.compute.adapters import RuntimeJob
from backend_v2.app.compute.ssh_transport import KeySSHTransport
from backend_v2.app.compute.tasks import _job_adapter
from backend_v2.app.core.config import Settings
from backend_v2.app.core.problem import DomainError


def test_project_roles_and_public_administrator_do_not_implicitly_grant_the_deployment_account(monkeypatch):
    from backend_v2.app.compute import access
    settings = Settings(deployment_kind="public", lsf_submitter_user_ids=[])
    monkeypatch.setattr(access, "get_settings", lambda: settings)
    for role in ("admin", "researcher", "viewer"):
        user = SimpleNamespace(id=uuid.uuid4(), role=role)
        assert lsf_access_blocker(user)["code"] == "lsf_account_not_assigned"
        with pytest.raises(DomainError) as failure:
            require_lsf_access(user, "lsf")
        assert failure.value.status_code == 403
        require_lsf_access(user, "demo")


def test_explicit_allowlist_does_not_match_another_user_or_widen_administrator_access(monkeypatch):
    from backend_v2.app.compute import access
    owner, other = uuid.uuid4(), uuid.uuid4()
    settings = Settings(deployment_kind="private", lsf_submitter_user_ids=[owner])
    monkeypatch.setattr(access, "get_settings", lambda: settings)
    assert lsf_access_blocker(SimpleNamespace(id=owner, role="researcher")) is None
    assert lsf_access_blocker(SimpleNamespace(id=other, role="admin"))
    settings.lsf_submitter_user_ids = []
    assert lsf_access_blocker(SimpleNamespace(id=other, role="admin")) is None
    assert lsf_access_blocker(SimpleNamespace(id=other, role="researcher"))


def test_job_lifecycle_keeps_the_original_cluster_after_deployment_configuration_changes(monkeypatch):
    from backend_v2.app.compute import access, tasks
    settings = Settings(lsf_ssh_host="first.example", lsf_remote_root="/scratch/first", lsf_ssh_user="alice",
                        lsf_ssh_key_path="/run/secrets/alice-key", lsf_queue="first-queue")
    monkeypatch.setattr(access, "get_settings", lambda: settings)
    target = lsf_target_snapshot()
    runtime = RuntimeJob(uuid.uuid4(), 1, "test", {"lsf_target": target})
    settings.lsf_ssh_host = "second.example"
    settings.lsf_ssh_user = "bob"
    seen = []
    monkeypatch.setattr(tasks, "adapter_for", lambda name, target=None: seen.append((name, target)) or "adapter")
    assert _job_adapter(runtime, "lsf") == "adapter"
    assert seen[0][1]["lsf_ssh_host"] == "first.example"
    assert seen[0][1]["lsf_ssh_user"] == "alice"
    assert seen[0][1]["lsf_ssh_key_path"] == "/run/secrets/alice-key"
    assert "password" not in target


def test_partial_site_snapshot_cannot_fall_back_to_the_current_account(monkeypatch):
    from backend_v2.app.compute import tasks
    called = []
    monkeypatch.setattr(tasks, "adapter_for", lambda *args, **kwargs: called.append(args))
    runtime = RuntimeJob(uuid.uuid4(), 1, "test", {"lsf_target": {"lsf_ssh_host": "first.example"}})
    with pytest.raises(ValueError, match="lsf_target_snapshot_invalid"):
        _job_adapter(runtime, "lsf")
    assert not called


def test_key_transport_honors_the_reviewed_ssh_username_without_connecting():
    transport = KeySSHTransport("cluster.example", key_path=None, connect_timeout=10, username="student")
    assert transport._argv()[-2:] == ["-l", "student"]
    assert "BatchMode=yes" in transport._argv()


def test_identical_scripts_require_fresh_review_when_the_execution_account_changes(monkeypatch):
    from backend_v2.app.compute import access, review
    from backend_v2.app.workflows import assistance

    settings = Settings(lsf_ssh_host='cluster.example', lsf_remote_root='/scratch/shared', lsf_ssh_user='alice')
    monkeypatch.setattr(access, 'get_settings', lambda: settings)
    monkeypatch.setattr(assistance, 'node_command', lambda *_args: 'run')
    monkeypatch.setattr(review, 'preview_context', lambda *_args: None)
    monkeypatch.setattr(review, 'render_script', lambda *_args: '#!/bin/sh\nrun')
    node = SimpleNamespace(id=uuid.uuid4())
    first = review.render_review(node, None, 'lsf', {'parameters': {}})
    settings.lsf_ssh_user = 'bob'
    second = review.render_review(node, None, 'lsf', {'parameters': {}})
    assert first[0] == second[0]
    assert first[1] != second[1]
