from __future__ import annotations

import uuid

from sqlalchemy import JSON, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class ExperimentResult(UUIDVersionMixin, Base):
    __tablename__ = "experiment_results"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    candidate_ref: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    batch_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    experiment_type: Mapped[str] = mapped_column(String(120), index=True)
    pass_status: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
