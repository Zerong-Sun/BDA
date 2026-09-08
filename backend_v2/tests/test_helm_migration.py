from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from backend_v2.app.core.config import Settings

pytestmark = pytest.mark.skipif(shutil.which("helm") is None, reason="Helm is required for chart rendering")
CHART = Path(__file__).resolve().parents[1] / "helm"


@pytest.fixture
def migration_pod():
    rendered = subprocess.run([
        "helm", "template", "audit", str(CHART),
        "--set", "config.lsf.sshHost=cluster.example.invalid",
        "--set", "config.lsf.remoteRoot=/srv/bda-audit",
        "--set", "lsfCredentials.keyFile=id_audit",
    ], check=True, capture_output=True, text=True)
    job = next(item for item in yaml.safe_load_all(rendered.stdout) if item and item["kind"] == "Job")
    return job["spec"]["template"]["spec"]


def test_migration_hook_is_hardened_and_has_writable_temp_storage(migration_pod) -> None:
    security = migration_pod["securityContext"]
    assert security["runAsNonRoot"] and security["runAsUser"] == 10001
    assert security["seccompProfile"]["type"] == "RuntimeDefault"
    container = migration_pod["containers"][0]
    assert container["securityContext"]["readOnlyRootFilesystem"]
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]
    assert {"name": "tmp", "mountPath": "/tmp"} in container["volumeMounts"]
    assert {"name": "tmp", "emptyDir": {}} in migration_pod["volumes"]


def test_preinstall_migration_boots_with_only_documented_secrets(migration_pod) -> None:
    # These match the keys documented in the two pre-existing Secrets. A Helm
    # pre-install hook cannot depend on the release's not-yet-created ConfigMap.
    values = {
        "database_url": "postgresql+psycopg://api:fixture@postgres/bda",
        "maintenance_database_url": "postgresql+psycopg://migration:fixture@postgres/bda",
        "jwt_secret": "x" * 40,
        "cors_origins": "https://bda.example.invalid",
        "minio_secret_key": "x" * 20,
        "oidc_providers_json": '{"test":{"issuer":"https://idp.example.invalid","client_id":"bda","redirect_uris":"https://bda.example.invalid/callback"}}',
        "llm_default_provider_ref": "file:/var/lib/bda/secrets/default.key",
        "external_research_sources_json": '{"test":{"base_url":"https://example.invalid"}}',
        "otel_endpoint": "http://otel.example.invalid:4318",
    }
    container = migration_pod["containers"][0]
    assert all("configMapRef" not in entry for entry in container["envFrom"])
    values.update({entry["name"].removeprefix("BDA_V2_").lower(): entry["value"] for entry in container["env"]})
    settings = Settings(**values, _env_file=None)
    assert settings.is_production and settings.require_maintenance_database_url
    assert settings.lsf_ssh_host == "cluster.example.invalid"
