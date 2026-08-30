from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
