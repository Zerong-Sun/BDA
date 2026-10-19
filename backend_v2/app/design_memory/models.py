"""Append-only design reviews and scoped lessons, independent of assay learning."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class DesignReview(UUIDVersionMixin, Base):
    __tablename__ = "design_reviews"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    fingerprint: Mapped[str] = mapped_column(String(64))
    memory_digest: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)


class DesignLesson(UUIDVersionMixin, Base):
    __tablename__ = "design_lessons"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    review_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("design_reviews.id", ondelete="CASCADE"), index=True)
    item_key: Mapped[str | None] = mapped_column(String(120))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("design_lessons.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
