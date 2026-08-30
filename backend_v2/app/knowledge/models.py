from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class KnowledgeEntry(UUIDVersionMixin, Base):
    __tablename__ = "knowledge_entries"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    entry_type: Mapped[str] = mapped_column(String(80), default="note", index=True)
    source: Mapped[dict] = mapped_column(JSON, default=dict)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
