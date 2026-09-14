"""One project's research room: records that already exist, in one order.

The roster gave the project a team, and each part of what that team does was
already recorded - a turn in `copilot_messages`, a handover in
`copilot_handoffs`, a durable task in `copilot_agent_runs`. What no surface had
was the *order*: three tabs, three lists, and a reader who had to interleave
them by timestamp in their head to answer "what happened, and who did it".

This module does that interleaving and nothing else.

**It reads; it never writes.** Every row it returns was written by the path that
owns it, so the room cannot become a second way to record work - which is what
would make the record and its display disagree.

**It invents no dialogue.** The only communication between operators that exists
is a handover row and a delegated child run. Both are rendered as what they are.
A model asked to narrate the chain would produce something that reads better and
is not the record; there is no code here that could emit such a line, which is
the point.

**One entry per task, not one per transition.** A run's status changes over its
life, and emitting an event per change would need a history table that does not
exist. The entry is the task, ordered by when it was started, carrying its
current state - so paging is stable and nothing is fabricated. A finished task
therefore does not jump to the top of the room; it is found where it started,
and the inbox is where "waiting on you" is answered.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.pagination import decode_time_cursor, encode_time_cursor
from .handoffs import to_json_model as handoff_to_json_model
from .models import CopilotAgentRun, CopilotConversation, CopilotHandoff, CopilotMessage

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

#: Message roles the room shows. `system` rows are prompt scaffolding rather
#: than anything anybody said, and showing them would put the policy text in
#: the middle of the conversation.
VISIBLE_ROLES = ("user", "assistant")


def _aware(moment: datetime) -> datetime:
    """A comparable instant, whatever the driver returned.

    Every timestamp here is stored as `DateTime(timezone=True)` and written in
    UTC, but SQLite hands some of them back without the offset. Three sources
    are merged in one sort, so a single naive value among aware ones raises
    `TypeError` and takes the whole room down rather than misordering one entry.
    `mcp.py` normalises the same way for the same reason; the assumption - that
    a stored instant is UTC - is the one the column already makes.
    """
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def _keyset(query: Any, column: Any, id_column: Any, cursor: tuple[datetime, uuid.UUID] | None) -> Any:
    """Rows strictly older than the cursor, ties broken by id.

    The pair is what makes the key total: two rows can share an instant, and a
    timestamp-only cursor would then either repeat one or skip one, depending
    on which side of the comparison it fell.
    """
    if cursor is None:
        return query
    moment, last_id = cursor
    return query.where(
        (column < moment) | ((column == moment) & (id_column < last_id))
    )


def _task_entry(run: CopilotAgentRun) -> dict[str, Any]:
    outcome = run.outcome if isinstance(run.outcome, dict) else {}
    return {
        "id": run.id,
        "goal": run.goal,
        "bot": run.bot,
        "status": run.status,
        "parent_run_id": run.parent_run_id,
        "turn_count": run.turn_count,
        #: The business outcome, which is not the transport status: a run can be
        #: `completed` as a process and `needs_input` as a delivery, and the
        #: second is the one a person acts on. `agent_loop.evaluate_delivery`
        #: writes it under `status`, which is also what the task list reads.
        "delivery_state": str(outcome.get("status") or "") or None,
        "decision_record_id": outcome.get("decision_record_id"),
        "updated_at": run.updated_at,
    }


def events(
    session: Session,
    *,
    project_id: uuid.UUID,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """The room's entries, newest first, with the cursor for the next page.

    Each source is asked for its own top `limit + 1` and the union is cut to
    `limit`. That is correct rather than merely convenient: an entry can only
    reach the merged page if it is within its own source's top `limit`, so no
    source can hide behind another's volume.
    """
    size = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    after = decode_time_cursor(cursor)

    conversations = select(CopilotConversation.id).where(CopilotConversation.project_id == project_id)
    message_query = _keyset(
        select(CopilotMessage).where(
            CopilotMessage.conversation_id.in_(conversations),
            CopilotMessage.role.in_(VISIBLE_ROLES),
        ),
        CopilotMessage.created_at,
        CopilotMessage.id,
        after,
    ).order_by(CopilotMessage.created_at.desc(), CopilotMessage.id.desc()).limit(size + 1)

    handoff_query = _keyset(
        select(CopilotHandoff).where(CopilotHandoff.project_id == project_id),
        CopilotHandoff.created_at,
        CopilotHandoff.id,
        after,
    ).order_by(CopilotHandoff.created_at.desc(), CopilotHandoff.id.desc()).limit(size + 1)

    run_query = _keyset(
        select(CopilotAgentRun).where(CopilotAgentRun.project_id == project_id),
        CopilotAgentRun.created_at,
        CopilotAgentRun.id,
        after,
    ).order_by(CopilotAgentRun.created_at.desc(), CopilotAgentRun.id.desc()).limit(size + 1)

    entries: list[dict[str, Any]] = []
    for message in session.scalars(message_query):
        entries.append(
            {
                "kind": "message",
                "id": message.id,
                "occurred_at": message.created_at,
                "bot": message.bot,
                "message": message,
            }
        )
    for handoff in session.scalars(handoff_query):
        entries.append(
            {
                "kind": "handoff",
                "id": handoff.id,
                "occurred_at": handoff.created_at,
                "bot": handoff.from_bot,
                "handoff": handoff_to_json_model(handoff),
            }
        )
    for run in session.scalars(run_query):
        entries.append(
            {
                "kind": "task",
                "id": run.id,
                "occurred_at": run.created_at,
                "bot": run.bot,
                "task": _task_entry(run),
            }
        )

    entries.sort(key=lambda entry: (_aware(entry["occurred_at"]), entry["id"]), reverse=True)
    page = entries[:size]
    next_cursor = (
        encode_time_cursor(page[-1]["occurred_at"], page[-1]["id"])
        if len(entries) > size and page
        else None
    )
    return page, next_cursor
