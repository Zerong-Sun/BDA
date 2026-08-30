"""Wet-lab bench: the protein library that experiments are run against.

The platform already had the dry half of the loop (targets, workflow runs,
compute jobs, candidates) and a place for measured outcomes
(``experiment_results``, which carries both ``candidate_id`` and
``source_artifact_id``). What it had no place for is the physical material:
the proteins actually expressed and assayed, and the numbers derived from
their sequence that every bench calculation starts from.

Deliberately not a LIMS. There is no inventory, no aliquot tracking, no
sample state machine, no chain of custody - a bench with a handful of
constructs does not need one, and adding it would put management cost in
front of the analysis this table exists to enable.

Raw instrument data does not live here. A BLI sensorgram or an AKTA trace is
uploaded as an artifact and referenced from ``experiment_results``; artifacts
are already write-once and checksummed, which is exactly the immutability the
raw snapshot needs.
"""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class Protein(UUIDVersionMixin, Base):
    """One construct in a project's protein library.

    ``sequence`` is the only plaintext copy and is treated as intellectual
    property: it is stored so that molecular weight, extinction coefficient and
    concentration can be computed locally, and it is never serialised outward.
    ``sequence_sha256`` is what identifies a construct across systems - see
    ``schemas.ProteinRead``, which exposes the fingerprint and omits the
    sequence.
    """

    __tablename__ = "proteins"
    __table_args__ = (
        # The library is always listed within one project and paged by name.
        Index("ix_proteins_project_name", "project_id", "name"),
        # Same construct registered twice in a project is a mistake, not a
        # second construct. Keyed on the digest rather than the sequence so the
        # index stays small and the plaintext is not duplicated into it.
        UniqueConstraint("project_id", "sequence_sha256", name="uq_protein_project_sequence"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    sequence: Mapped[str] = mapped_column(Text)
    #: SHA-256 of the sanitised sequence. The safe public identity of a construct.
    sequence_sha256: Mapped[str] = mapped_column(String(64), index=True)
    length: Mapped[int] = mapped_column(default=0)

    # Derived from the sequence at write time. Stored rather than recomputed per
    # read so a listing does not run ProtParam once per row, and so a value that
    # was used in a recorded calculation stays reproducible.
    molecular_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    ext_coeff_reduced: Mapped[float | None] = mapped_column(Float, nullable=True)
    ext_coeff_oxidized: Mapped[float | None] = mapped_column(Float, nullable=True)

    #: Set when this construct came out of the dry-lab side, so a measured
    #: result can be pushed back onto the design that predicted it.
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True, index=True
    )

    tags: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
