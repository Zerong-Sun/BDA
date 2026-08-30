from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class Target(UUIDVersionMixin, Base):
    __tablename__ = "targets"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    sequence: Mapped[str | None] = mapped_column(Text, nullable=True)
    uniprot_accession: Mapped[str | None] = mapped_column(String(32), nullable=True)
    organism: Mapped[str | None] = mapped_column(String(200), nullable=True)
    identity_status: Mapped[str] = mapped_column(String(40), default="unconfirmed")
    # "protein" or "small_molecule". What counts as identified, and whether an uploaded
    # structure is required at all, differs between them.
    target_kind: Mapped[str] = mapped_column(String(40), default="protein")
    # For a small-molecule target: {"ccd": "TCI", "inchikey": ..., "smiles": ...}. Any one
    # of these resolves the molecule; its coordinates come from the component library at
    # run time rather than from an uploaded file.
    chemical_identity: Mapped[dict] = mapped_column(JSON, default=dict)
    structure_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True
    )
    structure_status: Mapped[str] = mapped_column(String(40), default="missing")


class TargetStructureRevision(UUIDVersionMixin, Base):
    __tablename__ = "target_structure_revisions"

    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("targets.id", ondelete="CASCADE"), index=True)
    source_artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifacts.id"), index=True)
    prepared_artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
