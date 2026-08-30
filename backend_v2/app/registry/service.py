from __future__ import annotations

from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..core.problem import DomainError
from ..identity.models import User
from .models import ComputeNode, LLMProvider, MethodPlugin, ModelPlugin, RegistryServer, ScriptAsset
from .schemas import RegistryDeactivateResponse, RegistryResourceUpdate, ScriptAssetCreate

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
    for field, value in payload.data.items():
        if field in protected or not hasattr(row, field):
            raise DomainError("invalid_registry_field", f"Registry field is not writable: {field}", status_code=422)
        setattr(row, field, value)
    row.version += 1
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
