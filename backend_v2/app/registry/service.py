from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..core.problem import DomainError
from ..identity.models import User
from .models import ComputeNode, LLMProvider, MethodPlugin, ModelPlugin, RegistryServer, ScriptAsset
from .plugin_manifest import PluginManifest
from .schemas import PluginDeploymentCreate, RegistryDeactivateResponse, RegistryResourceUpdate, ScriptAssetCreate

MODELS = {
    "server": RegistryServer,
    "compute_node": ComputeNode,
    "model_plugin": ModelPlugin,
    "method_plugin": MethodPlugin,
    "llm_provider": LLMProvider,
}


def create_resource(session: Session, kind: str, data: dict):
    model = MODELS.get(kind)
    if model is None:
        raise DomainError("registry_kind_invalid", "Unsupported registry resource kind", status_code=422)
    try:
        row = model(**data)
    except TypeError as exc:
        raise DomainError("registry_payload_invalid", str(exc), status_code=422) from exc
    session.add(row)
    session.flush()
    return row


def public_data(row) -> dict:
    excluded = {"_sa_instance_state", "credential_ref", "legacy_id"}
    return {
        key: value
        for key, value in row.__dict__.items()
        if key not in excluded and key not in {"id", "version", "created_at", "updated_at"}
    }


def update_resource(row, payload: RegistryResourceUpdate, expected_version: int):
    if row.version != expected_version:
        raise DomainError("version_conflict", "Registry resource was modified", status_code=412)
    protected = {"id", "version", "created_at", "updated_at"}
    if isinstance(row, ModelPlugin) and row.manifest_checksum:
        protected.update(
            {
                "plugin_key",
                "plugin_version",
                "name",
                "container_image",
                "command",
                "parameter_schema",
                "output_schema",
                "input_ports",
                "output_ports",
                "resources",
                "runtime_mode",
                "output_parser",
                "input_adapter",
                "runtime_setup",
                "manifest_id",
                "manifest_schema_version",
                "manifest_checksum",
            }
        )
    for field, value in payload.data.items():
        if field in protected or not hasattr(row, field):
            raise DomainError("invalid_registry_field", f"Registry field is not writable: {field}", status_code=422)
        setattr(row, field, value)
    row.version += 1
    return row


def deploy_plugin_manifest(
    session: Session,
    manifest: PluginManifest,
    payload: PluginDeploymentCreate,
) -> ModelPlugin:
    row = session.scalar(
        select(ModelPlugin).where(
            ModelPlugin.plugin_key == manifest.plugin_key,
            ModelPlugin.plugin_version == manifest.plugin_version,
        )
    )
    runtime_reference = manifest.runtime.reference
    if manifest.runtime.image_digest:
        runtime_reference = f"{runtime_reference}@{manifest.runtime.image_digest}"
    definition = {
        "plugin_key": manifest.plugin_key,
        "plugin_version": manifest.plugin_version,
        "name": manifest.display_name,
        "container_image": runtime_reference,
        "command": manifest.command_template,
        "parameter_schema": manifest.parameter_schema,
        "output_schema": manifest.output_schema,
        "input_ports": manifest.inputs,
        "output_ports": manifest.outputs,
        "resources": manifest.resources,
        "runtime_mode": manifest.runtime.mode,
        "output_parser": manifest.output_parser,
        "input_adapter": manifest.input_adapter,
        "runtime_setup": manifest.runtime.setup,
        "manifest_id": manifest.manifest_id,
        "manifest_schema_version": manifest.schema_version,
        "manifest_checksum": manifest.checksum_sha256,
        "enabled": payload.enabled,
        "deployment_status": "installed" if payload.enabled else "disabled",
        "site_overrides": payload.site_overrides.model_dump(exclude_none=True),
    }
    if row is None:
        row = ModelPlugin(**definition)
        session.add(row)
    elif row.manifest_checksum and row.manifest_checksum != manifest.checksum_sha256:
        raise DomainError(
            "plugin_manifest_immutable",
            "The deployed plugin version is pinned to a different manifest checksum",
            status_code=409,
        )
    else:
        changes = {field: value for field, value in definition.items() if getattr(row, field) != value}
        for field, value in changes.items():
            setattr(row, field, value)
        if changes:
            row.version += 1
    session.flush()
    return row


def disable_resource(row, expected_version: int) -> RegistryDeactivateResponse:
    if not hasattr(row, "enabled"):
        raise DomainError("registry_resource_not_disableable", "Registry resource cannot be disabled", status_code=409)
    if row.version != expected_version:
        raise DomainError("version_conflict", "Registry resource was modified", status_code=412)
    row.enabled = False
    row.version += 1
    return RegistryDeactivateResponse(id=row.id, version=row.version)


def create_script_asset(
    session: Session, payload: ScriptAssetCreate, artifact: Artifact, user: User
) -> ScriptAsset:
    row = ScriptAsset(
        name=payload.name,
        artifact_id=artifact.id,
        checksum_sha256=artifact.checksum_sha256,
        runtime=payload.runtime,
        created_by=user.id,
    )
    session.add(row)
    session.flush()
    return row
