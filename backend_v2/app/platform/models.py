from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin, utcnow


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    instance_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    service: Mapped[str] = mapped_column(String(80), index=True)
    queues: Mapped[list[str]] = mapped_column(JSON, default=list)
    build_revision: Mapped[str] = mapped_column(String(80), index=True)
    schema_revision: Mapped[str] = mapped_column(String(80), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Operation(UUIDVersionMixin, Base):
    __tablename__ = "operations"

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(120), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), index=True)
    resource_id: Mapped[uuid.UUID] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MigrationRun(UUIDVersionMixin, Base):
    __tablename__ = "migration_runs"

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    rehearsal: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(32), index=True)
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    checksums: Mapped[dict] = mapped_column(JSON, default=dict)
    id_map_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rejection_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    report_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True
    )
