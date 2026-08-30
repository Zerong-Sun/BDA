from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.problem import DomainError


class PluginRuntime(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["container", "module", "conda", "script"]
    reference: str = Field(min_length=1, max_length=500)
    image_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    setup: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_reference(self) -> PluginRuntime:
        if self.mode == "container":
            if self.image_digest is None:
                raise ValueError("container plugin manifests require an immutable image_digest")
            if ":latest" in self.reference or self.reference.endswith("latest"):
                raise ValueError("container plugin manifests cannot reference latest")
        elif not self.reference.startswith("site://"):
            raise ValueError("non-container runtime references must use a site:// logical reference")
        return self


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    manifest_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,239}$")
    plugin_key: str = Field(min_length=1, max_length=200)
    plugin_version: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=240)
    command_template: str = Field(min_length=1)
    parameter_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    inputs: list[dict] = Field(default_factory=list)
    outputs: list[dict] = Field(default_factory=list)
    resources: dict = Field(default_factory=dict)
    runtime: PluginRuntime
    output_parser: str | None = Field(default=None, max_length=80)
    input_adapter: str | None = Field(default=None, max_length=80)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_checksum(self) -> PluginManifest:
        actual = plugin_manifest_checksum(self.model_dump(mode="json"))
        if actual != self.checksum_sha256:
            raise ValueError(f"plugin manifest checksum mismatch: expected {self.checksum_sha256}, got {actual}")
        return self


def plugin_manifest_checksum(value: dict) -> str:
    payload = dict(value)
    payload.pop("checksum_sha256", None)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class PluginManifestCatalog:
    def __init__(self, root: Path) -> None:
        self.root = root

    def manifests(self) -> list[PluginManifest]:
        rows: list[PluginManifest] = []
        manifest_identities: set[tuple[str, str]] = set()
        deployment_identities: set[tuple[str, str]] = set()
        for path in sorted(self.root.glob("*.json")):
            try:
                manifest = PluginManifest.model_validate_json(path.read_text())
            except (OSError, ValueError) as exc:
                raise DomainError(
                    "plugin_manifest_invalid",
                    f"Invalid plugin manifest {path.name}: {exc}",
                    status_code=500,
                ) from exc
            identity = (manifest.manifest_id, manifest.plugin_version)
            deployment_identity = (manifest.plugin_key, manifest.plugin_version)
            if identity in manifest_identities:
                raise DomainError(
                    "plugin_manifest_duplicate",
                    f"Duplicate plugin manifest identity: {identity[0]}@{identity[1]}",
                    status_code=500,
                )
            if deployment_identity in deployment_identities:
                raise DomainError(
                    "plugin_manifest_duplicate",
                    f"Duplicate plugin deployment identity: {deployment_identity[0]}@{deployment_identity[1]}",
                    status_code=500,
                )
            manifest_identities.add(identity)
            deployment_identities.add(deployment_identity)
            rows.append(manifest)
        return rows

    def require(self, manifest_id: str, version: str, checksum: str) -> PluginManifest:
        manifest = next(
            (
                item
                for item in self.manifests()
                if item.manifest_id == manifest_id and item.plugin_version == version
            ),
            None,
        )
        if manifest is None:
            raise DomainError("plugin_manifest_not_found", "Plugin manifest was not found", status_code=404)
        if manifest.checksum_sha256 != checksum:
            raise DomainError("plugin_manifest_checksum_mismatch", "Plugin manifest checksum does not match", status_code=409)
        return manifest
