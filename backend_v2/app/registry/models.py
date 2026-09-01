from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class RegistryServer(UUIDVersionMixin, Base):
    __tablename__ = "registry_servers"
    name: Mapped[str] = mapped_column(String(200), unique=True)
    server_type: Mapped[str] = mapped_column(String(40))
    endpoint: Mapped[str] = mapped_column(String(500))
    credential_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    health_status: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    health_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ComputeNode(UUIDVersionMixin, Base):
    __tablename__ = "compute_nodes"
    server_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("registry_servers.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    backend: Mapped[str] = mapped_column(String(40))
    queue: Mapped[str | None] = mapped_column(String(120), nullable=True)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    health_status: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    health_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ModelPlugin(UUIDVersionMixin, Base):
    __tablename__ = "model_plugins"
    __table_args__ = (UniqueConstraint("plugin_key", "plugin_version", name="uq_model_plugin_version"),)
    plugin_key: Mapped[str] = mapped_column(String(200))
    plugin_version: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(240))
    container_image: Mapped[str] = mapped_column(String(500))
    command: Mapped[str] = mapped_column(Text)
    parameter_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    # Declarative I/O contract: what this plugin consumes and produces. Ports make
    # workflow edges type-checkable and let the scheduler wire upstream outputs into
    # downstream inputs without a per-plugin wrapper.
    input_ports: Mapped[list] = mapped_column(JSON, default=list)
    output_ports: Mapped[list] = mapped_column(JSON, default=list)
    resources: Mapped[dict] = mapped_column(JSON, default=dict)
    # container | module | conda | script — LSF sites rarely run Docker, so a plugin
    # must be able to declare a non-container runtime.
    runtime_mode: Mapped[str] = mapped_column(String(20), default="container")
    output_parser: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Synthesises inputs the model needs but a workflow cannot bind directly
    # (AlphaFold 3 takes its sequences inside a JSON job specification).
    input_adapter: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Shell lines emitted before the command. HPC installations genuinely need arbitrary
    # preparation - sourcing a conda profile that is not on PATH, module load, exporting
    # a dependency directory - and declaring it keeps that site knowledge as data rather
    # than as a per-model Python module.
    runtime_setup: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Is the DECLARATION well-formed: image tag, non-empty command, schemas, ports. Set by
    # registry_model_plugin_validate, which executes nothing.
    validation_status: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validation_errors: Mapped[list] = mapped_column(JSON, default=list)
    # Has it ever been OBSERVED to run correctly: "unproven" | "proven" | "failed". A
    # rendered script that passes `bash -n` is not evidence that the model honours its
    # parameters - two real bugs (US-align's -dir1 segfault, pdb2pqr rejecting backbone
    # input) were only ever visible on execution.
    # server_default, not just default: migration 0002 builds this table from live model
    # metadata, so on a fresh database the column exists from 0002 onward while the raw
    # INSERTs in 0021-0034 - written before it existed - do not name it. Without a
    # database-side default those inserts violate NOT NULL and no new environment can
    # migrate. Existing databases get the same default from 0037.
    runtime_validation_status: Mapped[str] = mapped_column(
        String(32), default="unproven", server_default="unproven", index=True
    )
    runtime_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # {job_id, evidence: [...], checked_parameters: [...]} - what was observed, not a bare
    # "it exited zero". A zero exit code is compatible with conditioning never applying.
    # Plain literal, not "'{}'::json": the cast is PostgreSQL-only and the model metadata
    # also builds the SQLite schema the tests run on, where it fails to parse. Postgres
    # coerces the literal to json for a json column anyway, so both dialects are satisfied.
    runtime_validation_evidence: Mapped[dict] = mapped_column(
        JSON, default=dict, server_default=text("'{}'")
    )
    # New definitions are installed from a checksum-pinned manifest. Rows without a
    # checksum are explicitly legacy and may be used during the compatibility window,
    # but cannot be presented as immutable catalog deployments.
    manifest_id: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    manifest_schema_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    manifest_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    deployment_status: Mapped[str] = mapped_column(String(32), default="legacy", server_default="legacy")
    site_overrides: Mapped[dict] = mapped_column(JSON, default=dict, server_default=text("'{}'"))


class MethodPlugin(UUIDVersionMixin, Base):
    __tablename__ = "method_plugins"
    plugin_key: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(240))
    specification: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ParameterCatalog(UUIDVersionMixin, Base):
    __tablename__ = "parameter_catalog"
    plugin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_plugins.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    schema: Mapped[dict] = mapped_column(JSON, default=dict)
    defaults: Mapped[dict] = mapped_column(JSON, default=dict)


class ScriptAsset(UUIDVersionMixin, Base):
    __tablename__ = "script_assets"
    name: Mapped[str] = mapped_column(String(240))
    artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifacts.id"))
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    runtime: Mapped[str] = mapped_column(String(80))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class LLMProvider(UUIDVersionMixin, Base):
    __tablename__ = "llm_providers"
    name: Mapped[str] = mapped_column(String(200), unique=True)
    provider_type: Mapped[str] = mapped_column(String(80))
    endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model: Mapped[str] = mapped_column(String(200))
    credential_ref: Mapped[str] = mapped_column(String(300))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
