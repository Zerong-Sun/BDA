from __future__ import annotations

import uuid

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class Candidate(UUIDVersionMixin, Base):
    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("project_id", "candidate_key", name="uq_candidate_project_key"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    candidate_key: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(240))
    candidate_kind: Mapped[str] = mapped_column(String(40), default="design_candidate", index=True)
    status: Mapped[str] = mapped_column(String(40), default="proposed", index=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    structure_artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    complex_artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    source_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)


class CandidateMetric(UUIDVersionMixin, Base):
    """One number a method produced about one candidate.

    ``Candidate.scores`` is a JSON blob: it cannot be indexed, cannot answer "every
    design with pLDDT above 90 and ipTM above 0.8", and records neither which run nor
    which model produced a number. It also silently loses metrics when a second method
    scores a candidate that already exists - the common case, since AlphaFold2 folds
    designs ProteinMPNN already registered.

    Each metric therefore gets a row carrying its own provenance. ``scores`` stays as
    the denormalised view the UI already reads.
    """

    __tablename__ = "candidate_metrics"
    __table_args__ = (
        # Re-collecting an attempt must update a metric rather than duplicate it. The
        # variant is part of the key because AlphaFold2 legitimately reports the same
        # metric once per model/seed, and the condition is part of it because the same
        # method legitimately reports the same metric once per assay condition - one
        # ipTM per ligand when a design is screened against a panel. Without it the
        # second ligand overwrote the first and a selectivity panel could not be stored.
        UniqueConstraint(
            "candidate_id",
            "metric_key",
            "method",
            "model_variant",
            "condition",
            name="uq_candidate_metric_source",
        ),
        # Supports the range queries this table exists for.
        Index("ix_candidate_metrics_key_value", "metric_key", "value"),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    # Normalised across methods ("plddt", "ptm", "pae", "pae_interaction") so a filter
    # does not need to know which tool produced the number.
    metric_key: Mapped[str] = mapped_column(String(60), index=True)
    value: Mapped[float] = mapped_column(Float)
    # The tool and its configuration, e.g. "alphafold2_superfold" / "model_4_ptm_seed_0".
    method: Mapped[str] = mapped_column(String(60), index=True)
    model_variant: Mapped[str] = mapped_column(String(120), default="")
    # A confidence score is a prediction, never evidence. Keeping this explicit stops a
    # predicted number being read as a measurement downstream.
    evidence_kind: Mapped[str] = mapped_column(String(20), default="predicted", index=True)
    # Who produced the number, which `method` alone cannot say: the same model is a
    # design model in one workflow and an independent check in another. A design model
    # scoring its own output is self-assessment and must not be read as independent
    # corroboration.
    assessor: Mapped[str] = mapped_column(String(24), default="unknown", index=True)
    # What the value is about beyond the candidate itself - the ligand a design was
    # scored against, the binding partner, the temperature. Part of the unique key, so a
    # panel of conditions accumulates instead of overwriting.
    condition: Mapped[str] = mapped_column(String(120), default="")
    unit: Mapped[str] = mapped_column(String(24), default="")
    # Run detail that qualifies the value without being worth a column (recycles, tol).
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    source_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    # Where a *measured* number came from. A computed metric traces to a job; a
    # bench measurement traces to the experiment result that recorded it, which
    # in turn points at the instrument file it was read from. Without this a
    # measured row would be the only kind here with no provenance at all.
    source_experiment_result_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiment_results.id", ondelete="SET NULL"), nullable=True, index=True
    )
