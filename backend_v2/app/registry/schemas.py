from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegistryServerCreate(BaseModel):
    name: str
    server_type: str
    endpoint: str
    credential_ref: str | None = None
    enabled: bool = True


class RegistryServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    server_type: str
    endpoint: str
    enabled: bool
    health_status: str
    health_checked_at: datetime | None
    health_error: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class ComputeNodeCreate(BaseModel):
    server_id: uuid.UUID | None = None
    name: str
    backend: str
    queue: str | None = None
    labels: dict = Field(default_factory=dict)
    enabled: bool = True


class ComputeNodeResponse(ComputeNodeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    health_status: str
    health_checked_at: datetime | None
    health_error: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class ModelPluginCreate(BaseModel):
    plugin_key: str
    plugin_version: str
    name: str
    container_image: str
    command: str
    parameter_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    input_ports: list[dict] = Field(default_factory=list)
    output_ports: list[dict] = Field(default_factory=list)
    resources: dict = Field(default_factory=dict)
    runtime_mode: str = Field(default="container", pattern="^(container|module|conda|script)$")
    output_parser: str | None = Field(default=None, max_length=80)
    input_adapter: str | None = Field(default=None, max_length=80)
    runtime_setup: list[str] = Field(default_factory=list)
    enabled: bool = True


class ModelPluginResponse(ModelPluginCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    validation_status: str
    validated_at: datetime | None
    validation_errors: list
    # "the declaration is well-formed" and "it has been seen to run" are different claims.
    runtime_validation_status: str = "unproven"
    runtime_validated_at: datetime | None = None
    runtime_validation_evidence: dict = Field(default_factory=dict)
    manifest_id: str | None = None
    manifest_schema_version: str | None = None
    manifest_checksum: str | None = None
    deployment_status: str = "legacy"
    site_overrides: dict = Field(default_factory=dict)
    version: int
    created_at: datetime
    updated_at: datetime


class MethodPluginCreate(BaseModel):
    plugin_key: str
    name: str
    specification: dict = Field(default_factory=dict)
    enabled: bool = True


class MethodPluginResponse(MethodPluginCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime


class LLMProviderCreate(BaseModel):
    name: str
    provider_type: str
    endpoint: str | None = None
    model: str
    credential_ref: str
    config: dict = Field(default_factory=dict)
    enabled: bool = True


class LLMProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    provider_type: str
    endpoint: str | None
    model: str
    config: dict
    enabled: bool
    version: int
    created_at: datetime
    updated_at: datetime


class RegistryServerPage(BaseModel):
    items: list[RegistryServerResponse]
    next_cursor: str | None = None


class ComputeNodePage(BaseModel):
    items: list[ComputeNodeResponse]
    next_cursor: str | None = None


class ModelPluginPage(BaseModel):
    items: list[ModelPluginResponse]
    next_cursor: str | None = None


class PluginManifestDescriptor(BaseModel):
    manifest_id: str
    plugin_key: str
    plugin_version: str
    display_name: str
    schema_version: str
    checksum_sha256: str
    runtime_mode: str


class PluginManifestPage(BaseModel):
    items: list[PluginManifestDescriptor]


class PluginResourceLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu_cores: float | None = Field(default=None, gt=0, le=1024)
    memory_mb: int | None = Field(default=None, ge=16, le=16 * 1024 * 1024)
    gpu_count: int | None = Field(default=None, ge=0, le=128)
    walltime_seconds: int | None = Field(default=None, ge=1, le=31 * 24 * 60 * 60)


class PluginSiteOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime_root: str | None = Field(default=None, min_length=1, max_length=1000)
    module_names: list[str] = Field(default_factory=list, max_length=64)
    environment: dict[str, str] = Field(default_factory=dict)
    queue: str | None = Field(default=None, min_length=1, max_length=128)
    resource_limits: PluginResourceLimits | None = None

    @field_validator("runtime_root")
    @classmethod
    def validate_runtime_root(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("/"):
            raise ValueError("runtime_root must be an absolute site path")
        return value

    @field_validator("module_names")
    @classmethod
    def validate_module_names(cls, value: list[str]) -> list[str]:
        if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/+:-]{0,199}", item) for item in value):
            raise ValueError("module_names contain an invalid module identifier")
        return value

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 64:
            raise ValueError("environment cannot contain more than 64 entries")
        sensitive = re.compile(r"(?:SECRET|TOKEN|PASSWORD|PRIVATE_KEY|ACCESS_KEY)", re.IGNORECASE)
        for key, item in value.items():
            if not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,127}", key):
                raise ValueError(f"invalid environment variable name: {key}")
            if sensitive.search(key):
                raise ValueError(f"secret-like environment variable must use a credential reference: {key}")
            if len(item) > 4000:
                raise ValueError(f"environment variable is too large: {key}")
        return value


class PluginDeploymentCreate(BaseModel):
    manifest_id: str = Field(min_length=3, max_length=240)
    plugin_version: str = Field(min_length=1, max_length=80)
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    enabled: bool = True
    site_overrides: PluginSiteOverrides = Field(default_factory=PluginSiteOverrides)


class MethodPluginPage(BaseModel):
    items: list[MethodPluginResponse]
    next_cursor: str | None = None


class LLMProviderPage(BaseModel):
    items: list[LLMProviderResponse]
    next_cursor: str | None = None


class RegistryResourceUpdate(BaseModel):
    data: dict = Field(default_factory=dict)


class RegistryDeactivateResponse(BaseModel):
    id: uuid.UUID
    enabled: bool = False
    version: int


class RegistryResourceCreate(BaseModel):
    kind: str = Field(pattern="^(server|compute_node|model_plugin|method_plugin|llm_provider)$")
    data: dict


class RegistryResource(BaseModel):
    id: uuid.UUID
    kind: str
    data: dict
    version: int
    created_at: datetime


class RegistryPage(BaseModel):
    items: list[RegistryResource]
    next_cursor: str | None = None


class PluginSnapshot(BaseModel):
    id: uuid.UUID
    plugin_key: str
    plugin_version: str
    container_image: str
    command: str
    parameter_schema: dict
    output_schema: dict
    input_ports: list[dict] = Field(default_factory=list)
    output_ports: list[dict] = Field(default_factory=list)
    resources: dict = Field(default_factory=dict)
    runtime_mode: str = "container"
    output_parser: str | None = None
    input_adapter: str | None = None
    runtime_setup: list[str] = Field(default_factory=list)


class ScriptAssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    artifact_id: uuid.UUID
    runtime: str = Field(min_length=1, max_length=80)


class ScriptAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    artifact_id: uuid.UUID
    checksum_sha256: str
    runtime: str
    created_by: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime


class ParameterCatalogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    plugin_id: uuid.UUID
    name: str
    schema_: dict = Field(validation_alias="schema", serialization_alias="schema")
    defaults: dict
    version: int
    created_at: datetime
    updated_at: datetime


class ScriptAssetPage(BaseModel):
    items: list[ScriptAssetResponse]
    next_cursor: str | None = None


class ParameterCatalogPage(BaseModel):
    items: list[ParameterCatalogResponse]
    next_cursor: str | None = None


class RegistryOperationAccepted(BaseModel):
    operation_id: uuid.UUID
    resource_id: uuid.UUID
    status: str = "pending"
