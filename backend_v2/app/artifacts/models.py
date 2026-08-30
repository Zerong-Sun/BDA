from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class ArtifactUpload(UUIDVersionMixin, Base):
    __tablename__ = "artifact_uploads"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    artifact_type: Mapped[str] = mapped_column(String(80))
    content_type: Mapped[str] = mapped_column(String(160))
    object_key: Mapped[str] = mapped_column(String(800), unique=True)
    status: Mapped[str] = mapped_column(String(40), default="uploading", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class Artifact(UUIDVersionMixin, Base):
    __tablename__ = "artifacts"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    upload_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifact_uploads.id"), nullable=True, unique=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(80), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(160))
    object_key: Mapped[str] = mapped_column(String(800), index=True)
    status: Mapped[str] = mapped_column(String(40), default="available", index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    lineage: Mapped[dict] = mapped_column(JSON, default=dict)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ArtifactLineageEdge(UUIDVersionMixin, Base):
    __tablename__ = "artifact_lineage_edges"
    __table_args__ = (
        UniqueConstraint("parent_artifact_id", "child_artifact_id", "relation", name="uq_artifact_lineage_edge"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    parent_artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifacts.id", ondelete="CASCADE"), index=True)
    child_artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifacts.id", ondelete="CASCADE"), index=True)
    relation: Mapped[str] = mapped_column(String(80), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
