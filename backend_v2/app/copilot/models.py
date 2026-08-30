from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class CopilotConversation(UUIDVersionMixin, Base):
    __tablename__ = "copilot_conversations"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(240), default="New conversation")
    status: Mapped[str] = mapped_column(String(40), default="active")


class CopilotMessage(UUIDVersionMixin, Base):
    __tablename__ = "copilot_messages"
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("copilot_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    citations: Mapped[list] = mapped_column(JSON, default=list)
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class CopilotConfig(UUIDVersionMixin, Base):
    __tablename__ = "copilot_configs"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), unique=True)
    llm_provider_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("llm_providers.id"), nullable=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled_skills: Mapped[list] = mapped_column(JSON, default=list)


# --- Durable agent runs ------------------------------------------------------
#
# A chat turn answers in seconds. An agent that submits a GPU job and reasons
# about the result cannot: the work outlives the request, the worker, and often
# the day. Holding that in memory means a restart loses it silently.
#
# So the transcript is the state. Every turn is a row, a tool that starts long
# work suspends the run instead of blocking, and resuming reloads the turns and
# continues. Nothing is held between them but the database.
#
# Ported in shape from the archived copilot-binder-agent branch, whose durable
# turn loop was the part worth keeping (see docs/refactor/COPILOT_DESIGN_REFERENCE.md).

#: Where a run is. `awaiting_tasks` is the state that makes this durable: the
#: run is alive but nothing is executing, and a poller will wake it.
AGENT_RUN_STATUSES = (
    "running",
    "awaiting_tasks",
    "succeeded",
    "failed",
    "cancelled",
)

#: What a run is waiting on. Each resolves elsewhere - in compute, in another
#: run, or in whichever worker drains the operation - which is why the run has
#: to be able to sleep at all.
#:
#: `operation` covers everything queued through the platform's operation
#: lifecycle: a literature search, a target intelligence run, a gap repair. They
#: were the awkward case before it existed, because the agent could start them
#: and then had nothing to do but report "queued" and stop.
AGENT_TASK_KINDS = ("gpu_job", "subagent", "operation")

AGENT_TASK_STATUSES = ("running", "succeeded", "failed", "cancelled")


class CopilotAgentRun(UUIDVersionMixin, Base):
    __tablename__ = "copilot_agent_runs"
    __table_args__ = (
        # The poller asks one question: which runs are asleep and might now be
        # able to continue.
        Index("ix_copilot_agent_runs_status", "status", "updated_at"),
        Index("ix_copilot_agent_runs_project", "project_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("copilot_conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)

    #: What the run was asked to do, kept verbatim. A resumed run re-reads this
    #: rather than trusting a summary of it.
    goal: Mapped[str] = mapped_column(Text, default="")
    # No index=True: `status` leads the composite index above, so a separate
    # single-column one would cost every write and answer nothing new.
    status: Mapped[str] = mapped_column(String(24), default="running")

    #: Subagents are one level deep and no more. Enforced in the service, and
    #: recorded here so a cancel can walk down to its children.
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("copilot_agent_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )

    #: The closed tool vocabulary this run may use. A restriction that lives in
    #: data rather than in a branch, so a subagent cannot widen its own reach.
    allowed_tools: Mapped[list] = mapped_column(JSON, default=list)

    #: Budget, checked before each provider call rather than after, so an
    #: overrun stops the run instead of being noticed once it is paid for.
    max_turns: Mapped[int] = mapped_column(Integer, default=24)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd_cents: Mapped[int] = mapped_column(Integer, default=0)
    max_cost_usd_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class CopilotAgentTurn(UUIDVersionMixin, Base):
    """One exchange, persisted.

    Written as it happens rather than at the end: a run that dies mid-way should
    still show what it had done and why, which is exactly when that is worth
    reading.
    """

    __tablename__ = "copilot_agent_turns"
    __table_args__ = (
        # A transcript is always read in order, for one run.
        UniqueConstraint("run_id", "sequence", name="uq_agent_turn_sequence"),
        Index("ix_copilot_agent_turns_run", "run_id", "sequence"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("copilot_agent_runs.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(24))
    content: Mapped[str] = mapped_column(Text, default="")
    #: Tool calls requested in this turn, and their results once they resolve.
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd_cents: Mapped[int] = mapped_column(Integer, default=0)


class CopilotAgentTask(UUIDVersionMixin, Base):
    """Something a run is waiting on.

    `resource_id` names a job or a child run without a foreign key to either.
    That is deliberate: compute may prune a finished job, and a task whose
    target vanished should read as a dangling wait the poller can resolve, not
    block the deletion of the thing it points at.
    """

    __tablename__ = "copilot_agent_tasks"
    __table_args__ = (
        UniqueConstraint("run_id", "kind", "resource_id", name="uq_agent_task_resource"),
        # The poller's query: which tasks are still outstanding.
        Index("ix_copilot_agent_tasks_status", "status", "updated_at"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("copilot_agent_runs.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(24), index=True)
    resource_id: Mapped[uuid.UUID] = mapped_column(index=True)
    # Leads the composite index above; see the note on CopilotAgentRun.status.
    status: Mapped[str] = mapped_column(String(24), default="running")
    #: Which tool call this task answers, so the resumed turn can put the result
    #: back where the model expects it.
    tool_call_id: Mapped[str] = mapped_column(String(120), default="")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
