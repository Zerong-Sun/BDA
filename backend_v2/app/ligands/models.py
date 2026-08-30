from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class LigandImport(UUIDVersionMixin, Base):
    __tablename__ = "ligand_imports"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    ligand_id: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(40), default="pending")
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
