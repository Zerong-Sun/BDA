"""A project's decision record, as rows rather than as a document.

Research reasoning often starts in hand-written notes: which decisions were made, on
what evidence, which ones were later overturned, and what was tried and ruled out.
Unstructured notes cannot be queried or reliably linked to the jobs and candidates
they discuss, and their prose can drift away from the data.

The platform already stores the *outputs* of research (jobs, candidates, metrics,
findings) and the *system's* actions (audit log, job events). What it had no place for is
the chronology of human/agent judgement that connects them - the plan, the problem hit
halfway through, the call made about it, and the result that followed.

The model is deliberately generic: `entry_type` and `outcome` use vocabulary any
wet-lab or computational project can fill, so a future project gets a working timeline
by writing rows, not by adding tables.

Relationship to neighbouring tables:

- ``research_findings`` holds *conclusions* and answers "what do we believe, and was it
  supported or refuted". A timeline entry may point at one, but also covers things that
  are not conclusions at all: a plan, a blocked queue, a tooling fix.
- ``audit_logs`` records that *the system* did something, for compliance. This records
  why *a researcher* did something, for science.
- ``job_events`` are per-job lifecycle events. This is project-level and spans jobs.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin

# What kind of moment this is. Kept small and general on purpose - a longer, more
# specific list would encode one project's habits and force the next project to fight it.
ENTRY_TYPES = (
    "plan",        # what we intended to do, and why this and not the alternative
    "decision",    # a judgement call, with its basis
    "problem",     # something that blocked or threatened the work
    "resolution",  # how a problem was dealt with (links back via caused_by_id)
    "result",      # an observation, including - especially - a negative one
    "method",      # a tooling/protocol change worth recording separately from its result
    "milestone",   # a checkpoint worth finding again later
)

# Same vocabulary as research_findings.outcome, on purpose: "what did we rule out" should
# be answerable across both tables with one query and one set of values.
OUTCOMES = ("supported", "refuted", "inconclusive", "unspecified")

# Which half of the loop a moment belongs to. Three real values plus an explicit
# "not stated": a decision that spans both halves is the interesting case, not an
# awkward one - the sweet-protein D109 used dry re-analysis to revoke a *wet*
# authorisation, and forcing it into one bucket would lose the half that made it
# matter. `unspecified` exists so rows written before this column keep saying what
# they actually said, rather than being silently labelled `dry` in bulk.
LANES = ("dry", "wet", "both", "unspecified")


class ProjectTimelineEntry(UUIDVersionMixin, Base):
    __tablename__ = "project_timeline_entries"
    __table_args__ = (
        # The timeline is always read in time order within one project, and paged with a
        # keyset cursor on (occurred_at, id) - see core/pagination.encode_time_cursor.
        # Without this composite index that read is a scan plus a sort on every page.
        Index("ix_timeline_project_occurred", "project_id", "occurred_at", "id"),
        # "show me phase-2 decisions", "show only the problems" - the filtered reads this
        # table exists to make possible.
        Index("ix_timeline_project_type", "project_id", "entry_type"),
        Index("ix_timeline_project_phase", "project_id", "phase"),
        # Seeders own their rows by (project, entry_key), so re-running one updates in
        # place instead of appending a second copy of the same history. Entries created
        # through the API leave entry_key NULL, and Postgres treats NULLs as distinct -
        # so the constraint disciplines scripted history without constraining hand entry.
        UniqueConstraint("project_id", "entry_key", name="uq_timeline_entry_key"),
        # Deliberately NOT adding single-column indexes on project_id / occurred_at /
        # entry_type / phase: each is already the leading column of a composite above, so
        # a separate index would be dead weight on every write and buy nothing on read.
        # `outcome` keeps its own index because "what did we rule out" is asked across
        # projects, where project_id is not in the predicate at all.
        #
        # One row per numbered decision, per project. This is what makes a coverage
        # check possible at all: without it, "is D064 recorded" has no answer, and two
        # rows could each claim to be the record of it. NULL for the majority of
        # entries, which are not numbered decisions, and Postgres treats NULLs as
        # distinct - so the constraint disciplines the numbered ones without forcing a
        # number onto every observation.
        UniqueConstraint("project_id", "decision_ref", name="uq_timeline_decision_ref"),
        # No index on `lane`: it is only ever filtered inside one project, where
        # ix_timeline_project_occurred already leads with project_id, and the row count
        # per project is small. Same reasoning as the single-column indexes above.
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    # Stable caller-chosen identifier for scripted history, e.g.
    # ``phase-1-sequence-design-no-fixed-positions``. NULL for entries a person created
    # through the API, which have no natural key and are never re-seeded.
    entry_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # When it actually happened, which is NOT created_at: the record is often written
    # afterwards, and a timeline written from notes would otherwise collapse into the
    # moment it was typed up. Ordering and paging both use this.
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry_type: Mapped[str] = mapped_column(String(40), default="decision")
    # Free-text grouping ("phase-1", "phase-2", "pilot"). Not an enum: what counts as a
    # phase is the project's business, and a closed list would need a migration per project.
    phase: Mapped[str] = mapped_column(String(80), default="")
    title: Mapped[str] = mapped_column(String(300))
    # One paragraph, for the collapsed timeline view.
    summary: Mapped[str] = mapped_column(Text, default="")
    # Full reasoning, markdown. The part that would otherwise only exist in a doc.
    body: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str] = mapped_column(String(40), default="unspecified", index=True)
    # The project's own decision number, e.g. "D064" - the identifier the researchers
    # actually use in submission scripts, docs and conversation. Stored in a column
    # rather than mentioned in `body`, because a number that only exists in prose is a
    # number nothing can check: the sweet-protein project lost D080-D099 exactly that
    # way, with cluster scripts citing numbers the repository had never heard of.
    decision_ref: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Dry (computational), wet (bench), both, or not stated. See LANES.
    lane: Mapped[str] = mapped_column(String(16), default="unspecified")
    # The branches that were NOT taken: [{"option": ..., "rejected_because": ...}].
    # A record that only shows the path taken is a flowchart; what makes it a decision
    # is the option it closed off, and that is the part that gets re-opened later by
    # someone who cannot see why it was closed.
    alternatives: Mapped[list] = mapped_column(JSON, default=list)
    # Identifiers, not names mentioned in prose - the same discipline research_findings
    # applies: {"job_ids": [...], "candidate_ids": [...], "artifact_ids": [...],
    # "workflow_run_ids": [...], "finding_ids": [...], "external_refs": [...]}.
    # external_refs carries things the platform does not own, e.g. an LSF job id.
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    # Which scripts/modules this step actually used: [{"path": ..., "role": ...}].
    # Separate from provenance because "what code produced this" is a question asked on
    # its own - most often as "is that script still correct, and what else relied on it".
    code_refs: Mapped[list] = mapped_column(JSON, default=list)
    # A superseded entry stays in the record. Overturned reasoning is evidence about how
    # the project actually went, and deleting it is how a project forgets its own mistakes.
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_timeline_entries.id", ondelete="SET NULL"), nullable=True
    )
    # Links a resolution back to the problem it answers, so the pair can be read together.
    caused_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_timeline_entries.id", ondelete="SET NULL"), nullable=True
    )
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
