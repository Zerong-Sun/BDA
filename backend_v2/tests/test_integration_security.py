"""Adversarial egress, compute transport and provider-selection regressions."""
from __future__ import annotations

import subprocess
import uuid
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest
from backend_v2.app.compute import adapters
from backend_v2.app.compute.scripts import ScriptContext, render_script
from backend_v2.app.compute.ssh_transport import KeySSHTransport, PasswordSSHTransport
from backend_v2.app.copilot import endpoint_policy, provider, provider_selection
from backend_v2.app.copilot.models import CopilotConfig
from backend_v2.app.core.config import Settings
from backend_v2.app.core.problem import DomainError
from backend_v2.app.registry.models import LLMProvider
from backend_v2.tests.test_compute_service import compute_session as compute_session  # noqa: F401
from backend_v2.tests.test_config import _production_database_settings


@pytest.mark.parametrize("endpoint", [
    "http://169.254.169.254/latest/meta-data", "https://127.0.0.1/v1",
    "https://[::1]/v1", "https://internal.cluster/v1", "https://api.trusted.test.evil/v1",
    "https://api.trusted.test:444/v1",
])
def test_unapproved_endpoints_are_rejected_before_loading_secrets(monkeypatch, endpoint):
    monkeypatch.setattr(endpoint_policy, "get_settings", lambda: Settings(
        llm_allowed_endpoint_origins="https://api.trusted.test", _env_file=None))
    monkeypatch.setattr(provider, "credential_value", lambda _: pytest.fail("Credential must not be read"))
    configured = SimpleNamespace(endpoint=endpoint, model="test", config={}, credential_ref="file:/secrets/key")
    with pytest.raises(DomainError) as error:
        provider.completion_message(configured, [{"role": "user", "content": "private sequence"}])
    assert error.value.error_code == "llm_endpoint_not_approved"


@pytest.mark.parametrize("endpoint", [
    "https://api.trusted.test@evil.test/v1", "https://key:secret@api.trusted.test/v1",
    "https://api.trusted.test/v1?token=secret", "https://api.trusted.test/v1#fragment",
    "file:///etc/passwd", "https://api.trusted.test:0/v1", "https://api.trusted.test\\@evil.test/v1",
])
def test_endpoint_parser_rejects_ambiguous_or_credential_bearing_urls(endpoint):
    with pytest.raises(DomainError) as error:
        endpoint_policy.validate_llm_endpoint(endpoint)
    assert error.value.error_code == "llm_endpoint_invalid"


def test_empty_policy_disables_egress_and_explicit_local_gateway_requires_https_in_production(monkeypatch):
    monkeypatch.setattr(endpoint_policy, "get_settings", lambda: Settings(_env_file=None))
    with pytest.raises(DomainError, match="administrator"):
        endpoint_policy.validate_llm_endpoint("https://api.trusted.test/v1")
    monkeypatch.setattr(endpoint_policy, "get_settings", lambda: Settings(
        llm_allowed_endpoint_origins="http://127.0.0.1:8101", _env_file=None))
    endpoint_policy.validate_llm_endpoint("http://127.0.0.1:8101/v1")
    monkeypatch.setattr(endpoint_policy, "get_settings", lambda: SimpleNamespace(
        is_production=True, llm_allowed_endpoint_origins="http://127.0.0.1:8101"))
    with pytest.raises(DomainError, match="HTTPS"):
        endpoint_policy.validate_llm_endpoint("http://127.0.0.1:8101/v1")


def test_public_production_can_boot_without_a_default_provider():
    settings = _production_database_settings(deployment_kind="public", llm_default_provider_ref=None)
    assert settings.llm_default_provider_ref is None


def test_production_docker_cannot_disable_certificate_verification():
    with pytest.raises(ValueError, match="certificate verification"):
        _production_database_settings(compute_backend="docker", docker_tls_ca="/ca", docker_tls_cert="/cert",
                                      docker_tls_key="/key", docker_tls_verify=False)


def test_public_provider_selection_requires_explicit_project_choice(compute_session, monkeypatch):
    session, _, project, _ = compute_session
    shared = LLMProvider(name="Operator model", provider_type="openai_compatible", endpoint="https://operator.test/v1",
                         model="operator-model", credential_ref="env:OPERATOR_KEY", config={"platform_default": True}, enabled=True)
    session.add(shared)
    session.flush()
    monkeypatch.setattr(provider_selection, "get_settings", lambda: SimpleNamespace(
        deployment_kind="public", llm_default_provider_ref="env:OPERATOR_KEY"))
    assert provider_selection.select_provider(session, project_id=project.id) is None
    assert provider_selection.select_provider(session, shared.id, project_id=project.id) is shared
    session.add(CopilotConfig(project_id=project.id, llm_provider_id=shared.id))
    session.flush()
    assert provider_selection.select_provider(session, project_id=project.id) is shared


def test_model_request_ignores_ambient_proxy_and_never_follows_redirects(monkeypatch):
    from backend_v2.app.copilot import call_guard

    # Isolate this transport-policy regression from the independently tested
    # durable spending guard. Production still reserves before every send.
    monkeypatch.setattr(call_guard, "reserve_call", lambda *_: ("offline", "offline"))
    captured = {}

    class Client:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, endpoint, **kwargs):
            return httpx.Response(302, headers={"Location": "http://169.254.169.254/"}, request=httpx.Request("POST", endpoint))

    monkeypatch.setattr(endpoint_policy, "get_settings", lambda: Settings(
        llm_allowed_endpoint_origins="https://api.trusted.test", _env_file=None))
    monkeypatch.setattr(provider.httpx, "AsyncClient", Client)
    monkeypatch.setattr(provider, "credential_value", lambda _: "fixture-key")
    with pytest.raises(httpx.HTTPStatusError):
        provider.completion_message(SimpleNamespace(endpoint="https://api.trusted.test/v1", config={}, model="test", credential_ref="fixture"), [])
    assert captured == {"trust_env": False, "follow_redirects": False}


@pytest.mark.parametrize("host", ["-oProxyCommand=touch /tmp/exploit", "-F/tmp/evil", "host\nother", "host;whoami", ""])
def test_ssh_option_or_shell_payload_never_reaches_subprocess(host):
    with pytest.raises(ValueError, match="destination"):
        KeySSHTransport(host, key_path=None, connect_timeout=5)
    with pytest.raises(ValueError, match="destination"):
        PasswordSSHTransport(host, username="worker", password="fixture")


def test_key_transport_pins_host_keys_and_uses_configured_username(monkeypatch):
    captured = []
    monkeypatch.setattr(subprocess, "run", lambda argv, **kwargs: (
        captured.extend(argv) or subprocess.CompletedProcess(argv, 0, "", "")))
    KeySSHTransport("cluster.internal", key_path="/key", connect_timeout=5, username="tenant-worker").run("true")
    assert "StrictHostKeyChecking=yes" in captured
    assert captured[captured.index("-l") + 1] == "tenant-worker"


@pytest.mark.parametrize("port", ["../other-project", "/etc", "..", "a/b", "a\nexport SECRET=bad"])
def test_lsf_input_port_cannot_escape_job_staging(monkeypatch, port):
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: SimpleNamespace(stream=lambda _: pytest.fail("No input should be read")))
    adapter = adapters.LSFAdapter.__new__(adapters.LSFAdapter)
    adapter._ssh = lambda *args: None
    job = adapters.RuntimeJob(uuid.uuid4(), 1, "fixture", {"input_manifest": {"inputs": [
        {"port": port, "filename": "sequence.fasta", "object_key": "project/input"}]}})
    with pytest.raises(ValueError, match="port_invalid"):
        adapter._stage_inputs(job, "/shared/job")


def test_lsf_directives_cannot_inject_an_extra_shell_line():
    context = ScriptContext(job_name="bda-safe", remote_dir="/shared/job", command="true", queue="normal", backend="lsf")
    for mutated in [replace(context, queue="normal\ntouch /tmp/unsafe"),
                    replace(context, job_name="safe\n#BSUB -q private"),
                    replace(context, remote_dir="/shared\ntouch /tmp/unsafe"),
                    replace(context, resources={"gpu": True, "gpu_count": '1"\ntouch /tmp/unsafe'})]:
        with pytest.raises(ValueError):
            render_script(mutated)


@pytest.mark.parametrize("replace_output_root", [False, True])
def test_output_manifest_emitter_rejects_symlinks_into_another_project(tmp_path, replace_output_root):
    private = tmp_path / "other-project-secret"
    private.write_text("private sequence")
    output = tmp_path / "outputs"
    if replace_output_root:
        foreign_output = tmp_path / "foreign-outputs"
        foreign_output.mkdir()
        (foreign_output / "leaked.txt").write_text("private sequence")
        output.symlink_to(foreign_output, target_is_directory=True)
    else:
        output.mkdir()
        (output / "leaked.txt").symlink_to(private)
    context = ScriptContext(job_name="bda-safe", remote_dir=str(tmp_path), command="true", queue="normal", backend="lsf", staging_mode="ssh")
    script = tmp_path / "submit.sh"
    script.write_text(render_script(context))
    result = subprocess.run(["bash", str(script)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "output_symlinks_forbidden" in result.stderr
    assert not (tmp_path / "output-manifest.json").exists()


def test_docker_compute_drops_capabilities_and_forbids_privilege_escalation(monkeypatch):
    import docker

    monkeypatch.setattr(adapters, "_manifest_environment", lambda _: {})

    def missing(_name):
        raise docker.errors.NotFound("fixture missing")

    captured = {}
    adapter = adapters.DockerAdapter.__new__(adapters.DockerAdapter)
    adapter.client = SimpleNamespace(containers=SimpleNamespace(get=missing, run=lambda **kwargs: (
        captured.update(kwargs) or SimpleNamespace(id="fixture-container"))))
    job = adapters.RuntimeJob(uuid.uuid4(), 1, "fixture:1", {})
    assert adapter.ensure_submitted(job) == "fixture-container"
    assert captured["cap_drop"] == ["ALL"]
    assert captured["security_opt"] == ["no-new-privileges:true"]
    assert captured["pids_limit"] == 512
