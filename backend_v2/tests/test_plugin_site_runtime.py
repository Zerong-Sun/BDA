from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import uuid
from dataclasses import replace
from types import SimpleNamespace

import pytest
from backend_v2.app.compute.adapters import LSFAdapter, RuntimeJob
from backend_v2.app.compute.schemas import SubmissionCreate
from backend_v2.app.compute.scripts import ScriptContext, preview_context, render_script
from backend_v2.app.compute.service import create_submission
from backend_v2.app.core.problem import DomainError
from backend_v2.app.registry.runtime_validation import DECLARATION_FIELDS, plugin_declaration_fingerprint
from backend_v2.app.registry.site_runtime import resolve_plugin_runtime
from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun
from backend_v2.tests.test_compute_binding import env as env


def plugin(**overrides):
    fields = dict(
        runtime_mode="module", container_image="site://rosetta/2024.09", runtime_setup=[],
        command='"$BDA_PLUGIN_ROOT/bin/tool"', resources={"cpus": 1, "memory_gb": 2}, input_ports=[],
        site_overrides={"runtime_root": "/opt/rosetta 2024", "module_names": ["gcc/12"], "environment": {"OMP_NUM_THREADS": "1"}},
    )
    return SimpleNamespace(**(fields | overrides))


def adapter():
    value = LSFAdapter.__new__(LSFAdapter)
    value.root, value.default_queue, value.upload_wrapper, value.staging_mode = "/tmp/jobs", "other-queue", "", "ssh"
    return value


def test_preview_matches_frozen_submission_after_site_changes(monkeypatch):
    declaration = plugin()
    node = SimpleNamespace(container_image=None, queue=None, parameters={"pack_separated": False})
    settings = SimpleNamespace(lsf_queue="normal", lsf_remote_root="/tmp/jobs", lsf_upload_wrapper="", lsf_staging_mode="ssh")
    monkeypatch.setattr("backend_v2.app.core.config.get_settings", lambda: settings)
    preview = preview_context(node, declaration, "lsf", declaration.command)
    frozen = resolve_plugin_runtime(declaration, default_queue="normal")
    job = RuntimeJob(id=uuid.uuid4(), attempt_number=1, model_plugin="Rosetta", runtime_spec={
        "command": declaration.command, "parameters": node.parameters,
        "plugin_snapshot": {"resolved_runtime": frozen, "input_ports": []},
    })
    declaration.site_overrides["runtime_root"] = "/changed/not-used"
    declaration.site_overrides["environment"]["OMP_NUM_THREADS"] = "48"
    declaration.resources["cpus"] = 48
    submitted = adapter().script_context(job, {})
    comparable = replace(submitted, job_name=preview.job_name, remote_dir=preview.remote_dir)
    assert render_script(comparable) == render_script(preview)
    text = render_script(submitted)
    assert "export BDA_PLUGIN_ROOT='/opt/rosetta 2024'" in text
    assert "module load gcc/12" in text and "module load site://" not in text
    assert "export OMP_NUM_THREADS=1" in text and "#BSUB -n 1" in text
    assert "changed/not-used" not in text


def test_site_values_are_shell_literals(tmp_path):
    sentinel = tmp_path / "must-not-exist"
    text = f"$(touch {sentinel})`touch {sentinel}`"
    declaration = plugin(site_overrides={"runtime_root": "/opt/" + text, "environment": {"EXTRA": text}})
    runtime = resolve_plugin_runtime(declaration)
    script = render_script(ScriptContext(job_name="test", remote_dir="/tmp", command="printf '%s\\n' \"$BDA_PLUGIN_ROOT\" \"$EXTRA\"", queue="normal", backend="local", runtime_mode="module", container_image=runtime["image"], runtime_setup=runtime["runtime_setup"]))
    output = subprocess.run(["bash", "-c", script], check=True, capture_output=True, text=True)
    assert output.stdout.splitlines() == ["/opt/" + text, text]
    assert not sentinel.exists()


@pytest.mark.parametrize("overrides", [
    {}, {"runtime_root": "relative"}, {"module_names": ["gcc; touch /tmp/x"]},
    {"module_names": ["site://rosetta/2024.09"]},
    {"runtime_root": "/opt/x", "queue": "normal\n#BSUB -n 48"},
    {"runtime_root": "/opt/x", "environment": {"BDA_INPUT_DIR": "/other"}},
])
def test_invalid_or_unresolved_site_fails_before_dispatch(overrides):
    with pytest.raises(DomainError):
        resolve_plugin_runtime(plugin(site_overrides=overrides))


def test_root_only_and_modules_only_are_resolved_without_uri_activation():
    for overrides in [{"runtime_root": "/opt/x"}, {"module_names": ["rosetta/2024.09"]}]:
        result = resolve_plugin_runtime(plugin(site_overrides=overrides))
        assert result["image"] is None
        assert "site://" not in "\n".join(result["runtime_setup"])
    conda = resolve_plugin_runtime(plugin(runtime_mode="conda", site_overrides={"runtime_root": "/opt/env"}))
    assert "conda activate /opt/env" in conda["runtime_setup"]


def test_site_limits_reject_excess_without_silently_lowering_cpu_request():
    declaration = plugin(site_overrides={"runtime_root": "/opt/x", "queue": "cpu", "resource_limits": {"cpu_cores": 1}})
    assert resolve_plugin_runtime(declaration)["queue"] == "cpu"
    assert resolve_plugin_runtime(declaration, queue="chosen")["queue"] == "chosen"
    declaration.resources["cpus"] = 2
    with pytest.raises(DomainError, match="cpu_cores"):
        resolve_plugin_runtime(declaration)


def test_legacy_snapshot_keeps_physical_module_behaviour():
    job = RuntimeJob(id=uuid.uuid4(), attempt_number=1, model_plugin="legacy", runtime_spec={
        "command": "legacy-tool", "queue": "normal",
        "plugin_snapshot": {"runtime_mode": "module", "image": "rosetta/2024", "resources": {"cpus": 2}},
    })
    before = copy.deepcopy(job.runtime_spec)
    script = render_script(adapter().script_context(job, {}))
    assert "module load rosetta/2024" in script and "#BSUB -n 2" in script
    assert job.runtime_spec == before


def test_runtime_proof_tracks_site_changes_but_empty_legacy_fingerprint_is_unchanged():
    declaration = plugin(site_overrides={})
    original = hashlib.sha256(json.dumps({f: getattr(declaration, f, None) for f in DECLARATION_FIELDS}, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    assert plugin_declaration_fingerprint(declaration) == original
    declaration.site_overrides = {"runtime_root": "/one"}
    first = plugin_declaration_fingerprint(declaration)
    declaration.site_overrides["runtime_root"] = "/two"
    assert plugin_declaration_fingerprint(declaration) != first


def test_actual_submission_freezes_site_resolution(env):
    session, project, user, declaration = env["session"], env["project"], env["user"], env["producer"]
    declaration.runtime_mode = "module"
    declaration.container_image = "site://example/1"
    declaration.site_overrides = {"runtime_root": "/original", "environment": {"OMP_NUM_THREADS": "1"}}
    declaration.resources = {"cpus": 1}
    workflow = WorkflowRun(project_id=project.id, name="freeze", status="draft", graph={"nodes": [{"key": "one"}], "edges": []}, created_by=user.id)
    session.add(workflow)
    session.flush()
    session.add(WorkflowNode(workflow_run_id=workflow.id, node_key="one", node_type="model", model_plugin=declaration.plugin_key, model_plugin_id=declaration.id, parameters={}, input_bindings=[], status="draft"))
    session.flush()
    _, jobs = create_submission(session, workflow=workflow, project=project, payload=SubmissionCreate(compute_backend="demo", timeout_minutes=30), idempotency_key="site-freeze", user=user)
    snapshot = jobs[0].runtime_spec["plugin_snapshot"]
    assert snapshot["site_overrides"]["runtime_root"] == "/original"
    assert snapshot["resolved_runtime"]["runtime_setup"][0] == "export BDA_PLUGIN_ROOT=/original"
    checksum = snapshot["checksum_sha256"]
    material = {k: v for k, v in snapshot.items() if k != "checksum_sha256"}
    assert checksum == hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    declaration.site_overrides = {"runtime_root": "/changed"}
    session.flush()
    assert snapshot["resolved_runtime"]["site_overrides"]["runtime_root"] == "/original"
