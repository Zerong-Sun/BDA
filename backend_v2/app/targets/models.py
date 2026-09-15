from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Index, String, Text
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


class TargetHotspotSet(UUIDVersionMixin, Base):
    """The residues a design should target, and who said so.

    The platform could measure a structure and could run a design against named
    residues - `ppi.hotspot_res` and `target_hotspot_residues` have been in the
    plugin registry since RFdiffusion and BindCraft were registered. Between the
    two there was nothing to point at: the residues lived in a sentence in a
    chat window and were retyped into a parameter box.

    `origin` is the column this table exists for, and it carries the same three
    states as `project_timeline_entries.decided_by`, spelled the same way
    because it is the same question. An operator's set is `agent` and
    `proposed`; a person's own is `human` and `confirmed`; an operator's set a
    person accepted becomes `agent_proposed_human_confirmed`. Only a confirmed
    set may reach a job, which is what makes "propose" safe to give a model.

    Residues are the author numbering a person actually reads - `{chain, seq}`,
    optionally the residue name - because that is what the viewer shows and what
    the design tools take on their command lines.
    """

    __tablename__ = "target_hotspot_sets"
    __table_args__ = (
        CheckConstraint(
            "origin in ('agent', 'human', 'agent_proposed_human_confirmed')",
            name="ck_target_hotspot_set_origin",
        ),
        CheckConstraint(
            "status in ('proposed', 'confirmed', 'rejected')",
            name="ck_target_hotspot_set_status",
        ),
        # The read is "what has been proposed for this target, newest first",
        # and the design path's read is "what is confirmed".
        Index("ix_target_hotspot_sets_target", "target_id", "status", "created_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("targets.id", ondelete="CASCADE"))
    #: The structure the residues were read off. Nullable and SET NULL: a target
    #: can be re-imported, and a set recorded against a superseded coordinate
    #: file is still what somebody decided - losing the row would be worse than
    #: losing the pointer.
    structure_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(200))
    #: `[{chain, seq, name?}]` in the order given, de-duplicated.
    residues: Mapped[list] = mapped_column(JSON, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    #: Artifact, job, result or reference ids the set rests on.
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    origin: Mapped[str] = mapped_column(String(40), default="agent")
    status: Mapped[str] = mapped_column(String(24), default="proposed", index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    #: Who confirmed or rejected it. Separate from `created_by`, because the
    #: whole point is that they are usually not the same actor.
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
