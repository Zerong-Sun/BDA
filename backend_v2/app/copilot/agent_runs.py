"""Durable agent runs: suspend on long work, resume when it lands.

A chat turn answers in seconds; an agent that submits a GPU job cannot. The
state that survives that gap is the transcript itself — every turn is a row, so
resuming is reloading rows rather than restoring an object graph, and a process
that dies mid-run leaves a readable record of how far it got.

The three operations that make it durable:

* `suspend` — a tool started work that outlives this request. The run stops
  executing but stays alive, holding tasks that name what it waits on.
* `resume` — every task resolved, so the run can continue from its transcript.
* `cancel` — walks down: outstanding compute is cancelled and child runs are
  cancelled with it, because a cancelled parent leaving GPU jobs running is how
  a budget disappears quietly.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.problem import DomainError
from .models import (
    AGENT_TASK_KINDS,
    CopilotAgentRun,
    CopilotAgentTask,
    CopilotAgentTurn,
)

#: A subagent may not spawn a subagent. One level is enough to split work and
#: shallow enough that a cancel or a budget check terminates.
MAX_SUBAGENT_DEPTH = 1

#: States a run can still be worked on from.
_LIVE = {"running", "awaiting_tasks"}


def require_run(session: Session, run_id: uuid.UUID) -> CopilotAgentRun:
    run = session.get(CopilotAgentRun, run_id)
    if run is None:
        raise DomainError("agent_run_not_found", "Agent run was not found", status_code=404)
    return run


def create_run(
    session: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    goal: str,
    allowed_tools: list[str],
    conversation_id: uuid.UUID | None = None,
    parent_run_id: uuid.UUID | None = None,
    max_turns: int = 24,
    max_cost_usd_cents: int | None = None,
) -> CopilotAgentRun:
    if parent_run_id is not None:
        parent = require_run(session, parent_run_id)
        if parent.parent_run_id is not None:
            raise DomainError(
                "agent_subagent_too_deep",
                f"Subagents may nest {MAX_SUBAGENT_DEPTH} level deep.",
                status_code=422,
            )
        # A child cannot reach further than its parent. Enforced by intersecting
        # rather than trusting the caller's list.
        allowed_tools = sorted(set(allowed_tools) & set(parent.allowed_tools or []))

    run = CopilotAgentRun(
        project_id=project_id,
        conversation_id=conversation_id,
        created_by=user_id,
        goal=goal,
        status="running",
        parent_run_id=parent_run_id,
        allowed_tools=sorted(set(allowed_tools)),
        max_turns=max_turns,
        max_cost_usd_cents=max_cost_usd_cents,
    )
    session.add(run)
    session.flush()
    return run


def append_turn(
    session: Session,
    run: CopilotAgentRun,
    *,
    role: str,
    content: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd_cents: int = 0,
) -> CopilotAgentTurn:
    """Record one exchange and charge it to the run.

    Cost is accumulated here rather than at the end so `within_budget` can be
    asked *before* the next provider call, which is the only point where
    stopping still saves anything.
    """
    turn = CopilotAgentTurn(
        run_id=run.id,
        sequence=run.turn_count,
        role=role,
        content=content,
        tool_calls=list(tool_calls or []),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd_cents=cost_usd_cents,
    )
    session.add(turn)
    run.turn_count += 1
    run.cost_usd_cents += cost_usd_cents
    run.version += 1
    session.flush()
    return turn


def transcript(session: Session, run: CopilotAgentRun) -> list[CopilotAgentTurn]:
    """The run's turns in order. This is the whole of its resumable state."""
    return list(
        session.scalars(
            select(CopilotAgentTurn)
            .where(CopilotAgentTurn.run_id == run.id)
            .order_by(CopilotAgentTurn.sequence)
        )
    )


def budget_root(session: Session, run: CopilotAgentRun) -> CopilotAgentRun:
    """The run whose cost ceiling governs this one.

    A subagent is spawned by its parent, so the money it spends is the parent's
    money. Nesting stops at one level, so this is the parent or the run itself.
    """
    if run.parent_run_id is None:
        return run
    return session.get(CopilotAgentRun, run.parent_run_id) or run


def tree_cost_usd_cents(session: Session, run: CopilotAgentRun) -> int:
    """What this run and everything it spawned have spent together.

    Charged per run and summed here rather than accumulated onto the parent: a
    child that reported upward would make its own row untrue, and the row is
    what a person reads when asking where the money went.
    """
    children = session.scalar(
        select(func.coalesce(func.sum(CopilotAgentRun.cost_usd_cents), 0)).where(
            CopilotAgentRun.parent_run_id == run.id
        )
    )
    return run.cost_usd_cents + int(children or 0)


def within_budget(session: Session, run: CopilotAgentRun) -> tuple[bool, str]:
    """Whether the run may take another turn, and why not if it may not.

    Turns are counted per run: they measure one agent's reasoning, and a parent
    that spent its allowance thinking should not thereby silence a subagent that
    has barely started. Cost is counted across the tree, because money is
    fungible and a per-run ceiling is no ceiling at all once a run can spawn
    children - five subagents at the parent's limit spend six times the limit.
    """
    if run.turn_count >= run.max_turns:
        return False, f"turn limit reached ({run.max_turns})"
    root = budget_root(session, run)
    if root.max_cost_usd_cents is None:
        return True, ""
    spent = tree_cost_usd_cents(session, root)
    if spent >= root.max_cost_usd_cents:
        return False, f"cost limit reached ({root.max_cost_usd_cents} cents across the run tree)"
    return True, ""


def suspend(
    session: Session,
    run: CopilotAgentRun,
    tasks: list[tuple[str, uuid.UUID, str]],
) -> list[CopilotAgentTask]:
    """Park the run until the named work finishes.

    `tasks` is (kind, resource_id, tool_call_id). The tool call id travels with
    the task so a resumed turn can put each result back where the model expects
    it, rather than guessing from ordering.
    """
    if not tasks:
        raise DomainError(
            "agent_suspend_without_tasks",
            "A run cannot wait on nothing; it would never be woken.",
            status_code=422,
        )
    created = []
    for kind, resource_id, tool_call_id in tasks:
        if kind not in AGENT_TASK_KINDS:
            raise DomainError(
                "agent_task_bad_kind",
                f"kind must be one of {', '.join(AGENT_TASK_KINDS)}",
                status_code=422,
            )
        existing = session.scalar(
            select(CopilotAgentTask).where(
                CopilotAgentTask.run_id == run.id,
                CopilotAgentTask.kind == kind,
                CopilotAgentTask.resource_id == resource_id,
            )
        )
        if existing is not None:
            created.append(existing)
            continue
        task = CopilotAgentTask(
            run_id=run.id,
            kind=kind,
            resource_id=resource_id,
            status="running",
            tool_call_id=tool_call_id,
        )
        session.add(task)
        created.append(task)
    run.status = "awaiting_tasks"
    run.version += 1
    session.flush()
    return created


def outstanding_tasks(session: Session, run: CopilotAgentRun) -> list[CopilotAgentTask]:
    return list(
        session.scalars(
            select(CopilotAgentTask).where(
                CopilotAgentTask.run_id == run.id, CopilotAgentTask.status == "running"
            )
        )
    )


def settle_task(
    session: Session,
    task: CopilotAgentTask,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> CopilotAgentTask:
    """Record how one awaited piece of work turned out."""
    task.status = status
    task.result = dict(result or {})
    task.error = error
    task.version += 1
    session.flush()
    return task


def resume(session: Session, run: CopilotAgentRun) -> bool:
    """Wake a run whose tasks have all settled. True if it moved.

    A failed task does not fail the run: the agent is told what happened and
    decides. A failed fold is information, and an agent that cannot see it will
    repeat the run that produced it.
    """
    if run.status != "awaiting_tasks":
        return False
    if outstanding_tasks(session, run):
        return False
    run.status = "running"
    run.version += 1
    session.flush()
    return True


def resumable_runs(session: Session, limit: int = 50) -> list[CopilotAgentRun]:
    """Suspended runs with nothing left outstanding.

    No longer the primary path: compute emits `job.settled` and the platform
    emits `operation.settled` on every terminal state, so a settled wait wakes
    its run directly. This remains the backstop for wake-ups no event carries -
    a task settled by a cancel, an event lost between publisher and worker - and
    should normally return nothing.
    """
    waiting = session.scalars(
        select(CopilotAgentRun).where(CopilotAgentRun.status == "awaiting_tasks").limit(limit)
    )
    return [run for run in waiting if not outstanding_tasks(session, run)]


def finish(
    session: Session, run: CopilotAgentRun, *, status: str, error: str | None = None
) -> CopilotAgentRun:
    if status not in {"succeeded", "failed"}:
        raise DomainError(
            "agent_bad_terminal_status",
            "A run finishes as succeeded or failed; cancelling has its own path.",
            status_code=422,
        )
    run.status = status
    run.error = error
    run.version += 1
    session.flush()
    return run


def cancel(session: Session, run: CopilotAgentRun, *, reason: str = "") -> int:
    """Cancel a run, its outstanding work, and its children.

    Returns how many runs were cancelled. The cascade is the point: a cancelled
    parent that leaves GPU jobs running and subagents thinking is how a budget
    disappears without anyone deciding to spend it.
    """
    if run.status not in _LIVE:
        return 0

    cancelled = 1
    for task in outstanding_tasks(session, run):
        if task.kind == "gpu_job":
            _cancel_compute_job(session, task.resource_id, run)
        elif task.kind == "subagent":
            child = session.get(CopilotAgentRun, task.resource_id)
            if child is not None:
                cancelled += cancel(session, child, reason="parent run cancelled")
        settle_task(session, task, status="cancelled")

    # Children may also exist without an outstanding task pointing at them, if
    # the parent moved on before they finished.
    for child in session.scalars(
        select(CopilotAgentRun).where(
            CopilotAgentRun.parent_run_id == run.id, CopilotAgentRun.status.in_(tuple(_LIVE))
        )
    ):
        cancelled += cancel(session, child, reason="parent run cancelled")

    run.status = "cancelled"
    run.error = reason or None
    run.version += 1
    session.flush()
    return cancelled


def _cancel_compute_job(session: Session, job_id: uuid.UUID, run: CopilotAgentRun) -> None:
    """Ask compute to stop a job, through compute's own service.

    Imported inside the function to keep the dependency one-way at import time:
    copilot orchestrates compute, and compute must never need copilot.

    The run supplies the project and the actor, so the cancellation is audited
    against whoever started the agent rather than appearing to come from nowhere.
    """
    from ..compute.models import Job
    from ..compute.service import request_cancel
    from ..identity.models import User
    from ..projects.models import Project

    job = session.get(Job, job_id)
    if job is None:
        return
    project = session.get(Project, run.project_id)
    user = session.get(User, run.created_by)
    if project is None or user is None:
        return
    try:
        request_cancel(session, job, project, user)
    except DomainError:
        # Already terminal. Nothing to stop, and not a reason to abandon the
        # rest of the cascade.
        return
