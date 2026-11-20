from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class UUIDVersionMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    legacy_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    @declared_attr.directive
    def __mapper_args__(cls) -> dict:
        return {"version_id_col": cls.version, "version_id_generator": False}


def update_versioned(row: object, **values: object) -> bool:
    """Assign only the values that differ; bump the version once if any did.

    A row that has not been flushed yet keeps its initial version.
    """
    changed = False
    for field, value in values.items():
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed = True
    if changed and getattr(row, "id", None) is not None:
        row.version += 1  # type: ignore[attr-defined]
    return changed
