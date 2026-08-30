from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class Project(UUIDVersionMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "source_package_id",
            "source_project_key",
            name="uq_project_research_package_source",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    project_type: Mapped[str] = mapped_column(String(80))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    source_package_id: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    source_project_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    localized_content: Mapped[dict] = mapped_column(JSON, default=dict)
    primary_target_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("targets.id", name="fk_projects_primary_target", use_alter=True), nullable=True, index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), default="researcher")


class ProjectPromptDraft(UUIDVersionMixin, Base):
    """An LLM-drafted design prompt, generated before the project it will belong to exists.

    Not scoped to a project (there isn't one yet), so authorization is by ``created_by``
    rather than project membership — see ``require_project_prompt_draft``.
    """

    __tablename__ = "project_prompt_drafts"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    request: Mapped[dict] = mapped_column(JSON, default=dict)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
