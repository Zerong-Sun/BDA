from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class ResearchBrief(UUIDVersionMixin, Base):
    __tablename__ = "research_briefs"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(40), default="draft")
    content: Mapped[str] = mapped_column(Text, default="")
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class ResearchFinding(UUIDVersionMixin, Base):
    __tablename__ = "research_findings"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    brief_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_briefs.id", ondelete="SET NULL"), nullable=True
    )
    finding_type: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    # How the question resolved: "supported", "refuted", "inconclusive", or "unspecified"
    # for rows that predate the column. Indexed because "what did we rule out" is a
    # question worth asking, and prose cannot answer it.
    outcome: Mapped[str] = mapped_column(String(40), default="unspecified", index=True)
    # The finding this one replaces. A conclusion that was later overturned is part of the
    # record, not something to delete.
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_findings.id", ondelete="SET NULL"), nullable=True
    )
    # {"job_ids": [...], "candidate_ids": [...], "artifact_ids": [...]} - what the finding
    # rests on, as identifiers rather than as names mentioned in the text.
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)


class ResearchGeneration(UUIDVersionMixin, Base):
    __tablename__ = "research_generations"

    source_project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("copilot_conversations.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    request: Mapped[dict] = mapped_column(JSON, default=dict)
    draft: Mapped[dict] = mapped_column(JSON, default=dict)
    validation: Mapped[dict] = mapped_column(JSON, default=dict)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    imported_project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


# Research goals: the layer the platform was missing.
#
# `research_findings` answers "what do we believe"; `project_timeline_entries`
# answers "what happened, and what did we decide". Neither answers "what are we
# trying to find out, and how does this piece of work serve it" - a goal that
# decomposes into sub-goals, gathers the experiments run against it, and is
# closed by a conclusion that in turn raises the next goal.
#
# Ported in concept from the protein-lab workbench's research trace, with its
# central rule kept: a trace is a *by-product* of doing the work, not a module
# to maintain. Saving a result asks which goal it belongs to and accepts "not
# now" without friction.
#
# Single-parent tree, not a DAG. One experiment supporting several goals and one
# conclusion drawn from several experiments are both covered by
# `ResearchGoalLink` being many-to-many, which is what those cases actually
# need; a real graph would add cycle handling and edge ordering for no gain here.

#: Where a goal stands. Kept to three: anything finer becomes bookkeeping.
GOAL_STATUSES = ("open", "answered", "abandoned")

#: What a goal can gather. Values match the owning table, so a link resolves
#: without a discriminator column per resource type.
GOAL_LINK_TYPES = ("experiment_result", "finding", "candidate", "job", "protein")


class ResearchGoal(UUIDVersionMixin, Base):
    __tablename__ = "research_goals"
    __table_args__ = (
        # A project's goal tree is read whole, ordered within each parent.
        Index("ix_research_goals_project_parent", "project_id", "parent_id", "sort_order"),
        Index("ix_research_goals_project_status", "project_id", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    # Self-referential: NULL is a root goal, and a project may have several.
    # Cascading on delete removes a subtree with its parent, which is the
    # behaviour a tree edit expects; the links hanging off it cascade in turn,
    # while the resources they point at are untouched.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_goals.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)


class ResearchGoalLink(UUIDVersionMixin, Base):
    """Attaches a piece of work to a goal, from either side of the loop.

    Deliberately many-to-many: a single assay can be evidence for more than one
    goal, and re-running it should not force a choice between them.

    `resource_type` + `resource_id` rather than one nullable foreign key per
    kind - the same shape `operations` uses. The cost is no database-level
    referential integrity on `resource_id`; the service checks existence on
    write, and a link whose target was deleted reads as a dangling reference
    rather than blocking the delete, which is the right trade for a trace that
    must survive its evidence being reorganised.
    """

    __tablename__ = "research_goal_links"
    __table_args__ = (
        # Attaching the same thing to the same goal twice is a double-click,
        # not a second piece of evidence.
        UniqueConstraint("goal_id", "resource_type", "resource_id", name="uq_goal_link_resource"),
        # "which goals does this result serve" - the reverse lookup.
        Index("ix_goal_links_resource", "resource_type", "resource_id"),
    )

    goal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_goals.id", ondelete="CASCADE"), index=True
    )
    resource_type: Mapped[str] = mapped_column(String(40), index=True)
    resource_id: Mapped[uuid.UUID] = mapped_column(index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
