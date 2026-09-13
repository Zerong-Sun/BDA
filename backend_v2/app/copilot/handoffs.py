"""Reading and writing the channel between operators.

The roster used to name a successor in prose, which meant a bot could announce
a handover and leave nothing behind. This module is the other half: a handover
is a row, the recipient reads its own inbox, and a reviewer reads the same rows
the recipient does rather than taking the producer's word for what happened.

Two rules are enforced here rather than in the tool handler, because both must
hold on every path into the table and a handler is one path:

* both operator ids exist in the roster - a note addressed to nobody is a note
  that is never read, and it would look like a completed handover;
* claims are normalised into `{statement, evidence_ref, confidence}` - the
  shape is what `auditor` checks, so accepting a free-form list here would move
  the parsing into the reviewer, where a malformed claim becomes a judgement
  call instead of a rejected input.

Nothing updates a row. `record` inserts; there is no edit and no delete.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.problem import DomainError
from . import bots
from .models import CopilotHandoff

#: How strongly the producing operator claims its own statement is supported.
#: Deliberately about *evidence*, not about certainty: an operator that is very
#: sure of an unsupported claim is exactly the case the reviewer exists for.
#:   stated     - a recorded value or document says this
#:   consistent - the evidence permits it and does not establish it
#:   unsupported- offered as a lead, with nothing behind it yet
CONFIDENCE_LEVELS = ("stated", "consistent", "unsupported")

MAX_CLAIMS = 20
MAX_OPEN_QUESTIONS = 20
MAX_REFS = 40
MAX_TEXT = 2000
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def _text(value: Any, *, field: str, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise DomainError(
            "copilot_handoff_invalid",
            f"Handover {field} must not be empty.",
            status_code=422,
        )
    return text[:MAX_TEXT]


def normalise_claims(raw: Any) -> list[dict[str, str]]:
    """Force the shape the reviewer reads.

    A claim without `evidence_ref` is kept rather than rejected, and lands as
    `confidence="unsupported"` with an empty ref. That is the honest record: the
    operator did make the claim, and the reviewer's job is to say it cites
    nothing. Dropping it here would hide the exact defect review exists to find.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise DomainError(
            "copilot_handoff_invalid", "claims must be a list.", status_code=422
        )
    if len(raw) > MAX_CLAIMS:
        raise DomainError(
            "copilot_handoff_invalid",
            f"A handover carries at most {MAX_CLAIMS} claims.",
            status_code=422,
        )
    claims: list[dict[str, str]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise DomainError(
                "copilot_handoff_invalid",
                "each claim must be an object with a statement.",
                status_code=422,
            )
        evidence = _text(entry.get("evidence_ref"), field="evidence_ref", required=False)
        confidence = str(entry.get("confidence") or "").strip()
        if confidence not in CONFIDENCE_LEVELS:
            confidence = "consistent" if evidence else "unsupported"
        if not evidence:
            # A ref is what makes a claim checkable, so its absence sets the
            # level regardless of what the operator asserted about itself.
            confidence = "unsupported"
        claims.append(
            {
                "statement": _text(entry.get("statement"), field="claim statement"),
                "evidence_ref": evidence,
                "confidence": confidence,
            }
        )
    return claims


def _string_list(raw: Any, *, field: str, maximum: int) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise DomainError("copilot_handoff_invalid", f"{field} must be a list.", status_code=422)
    if len(raw) > maximum:
        raise DomainError(
            "copilot_handoff_invalid",
            f"A handover carries at most {maximum} {field}.",
            status_code=422,
        )
    return [text for text in (_text(item, field=field, required=False) for item in raw) if text]


def record(
    session: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    from_bot: str,
    to_bot: str,
    summary: str,
    claims: Any = None,
    open_questions: Any = None,
    refs: Any = None,
    produced_by_run: uuid.UUID | None = None,
) -> CopilotHandoff:
    """Append one handover. Both operators must exist; nothing is updated."""
    bots.require(from_bot)
    bots.require(to_bot)
    if from_bot == to_bot:
        raise DomainError(
            "copilot_handoff_invalid",
            "An operator does not hand over to itself.",
            status_code=422,
        )

    row = CopilotHandoff(
        project_id=project_id,
        from_bot=from_bot,
        to_bot=to_bot,
        summary=_text(summary, field="summary"),
        claims=normalise_claims(claims),
        open_questions=_string_list(open_questions, field="open questions", maximum=MAX_OPEN_QUESTIONS),
        refs=_string_list(refs, field="refs", maximum=MAX_REFS),
        produced_by_run=produced_by_run,
        created_by=user_id,
    )
    session.add(row)
    session.flush()
    return row


def inbox(
    session: Session,
    *,
    project_id: uuid.UUID,
    to_bot: str | None = None,
    from_bot: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[CopilotHandoff]:
    """Handovers in this project, newest first.

    `to_bot` is the recipient's read and `from_bot` the reviewer's. Neither is
    required: an operator with no filter sees the whole chain, which is what a
    director needs to decide who works next.
    """
    stmt = select(CopilotHandoff).where(CopilotHandoff.project_id == project_id)
    if to_bot:
        stmt = stmt.where(CopilotHandoff.to_bot == bots.require(to_bot).id)
    if from_bot:
        stmt = stmt.where(CopilotHandoff.from_bot == bots.require(from_bot).id)
    stmt = stmt.order_by(CopilotHandoff.created_at.desc()).limit(
        max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    )
    return list(session.scalars(stmt))


def is_off_chain(from_bot: str, to_bot: str) -> bool:
    """Whether this route is one the sender's roster entry anticipated.

    Advisory, and deliberately not enforced: `BotSpec.handoff` is the expected
    path, but a reviewer posting a verdict back to whoever it reviewed is a
    legitimate route the tuple does not list, and refusing it would make the
    review stance unable to report. Surfaced to the caller so an unusual route
    is visible rather than silent.
    """
    sender = bots.get(from_bot)
    return bool(sender and to_bot not in sender.handoff)


def to_json_model(row: CopilotHandoff) -> dict[str, Any]:
    """The row for the REST schema, which keeps native types.

    Separate from `to_json` because a tool result is JSON handed to a model and
    wants strings, while the response schema wants the UUIDs and datetimes it
    declares. One function coerced for both would have the API returning
    stringified ids for this resource and typed ones for every other.
    """
    return {
        "id": row.id,
        "from_bot": row.from_bot,
        "to_bot": row.to_bot,
        "summary": row.summary,
        "claims": list(row.claims or []),
        "open_questions": list(row.open_questions or []),
        "refs": list(row.refs or []),
        "produced_by_run": row.produced_by_run,
        "created_at": row.created_at,
    }


def to_json(row: CopilotHandoff) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "from_bot": row.from_bot,
        "to_bot": row.to_bot,
        "summary": row.summary,
        "claims": list(row.claims or []),
        "open_questions": list(row.open_questions or []),
        "refs": list(row.refs or []),
        "produced_by_run": str(row.produced_by_run) if row.produced_by_run else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
