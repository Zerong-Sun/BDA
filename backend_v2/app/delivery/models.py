from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class DeliveryPackage(UUIDVersionMixin, Base):
    __tablename__ = "delivery_packages"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    name: Mapped[str] = mapped_column(String(240))
    selection: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
