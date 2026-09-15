"""Asking a person to settle one thing, with the options and what each rests on.

The decision inbox answers "what is waiting on me" by *inferring* it from five
lists. Inference has a ceiling: it can say a delivery is unreviewed, and it can
never say "I narrowed the hotspots to three sets and the choice between them is
yours, here is what each costs". An operator had no way to ask.

Three rules are enforced here rather than in the handler, because each must hold
on every path into the table:

* **An operator asks; a person answers.** `record` never sets an answer and
  `answer` requires a `User`. The tool surface has no way to reach `answer` at
  all - it is not a tool - so a bot cannot resolve its own question by calling
  something it already holds.
* **Options are bounded and each carries its own reason.** Two to six, because a
  reviewer who cannot hold the list stops choosing and starts accepting - the
  same argument `core/review.py` makes for approval batches. An option without a
  rationale is kept, not rejected, and marked as having none: that is the
  honest record, and it is exactly what a reader should notice.
* **An answer becomes a decision record.** Written through
  `timeline.create_entry` with `decided_by="agent_proposed_human_confirmed"`,
  which is what it is: the options were drafted by an operator and the call was
  made by a person. Collapsing it into either "human" or "agent" would destroy
  the only comparison the column exists for.

When the question is asked *by* a run, answering it does not resume that run.
The run is suspended by whatever tool suspended it; a decision request is a
question, not a scheduler, and giving it the power to wake work would make two
mechanisms responsible for the same transition.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from . import bots
from .models import CopilotDecisionRequest

#: What the request is waiting for.
STATUSES = ("open", "answered", "withdrawn")

MIN_OPTIONS = 2
MAX_OPTIONS = 6
MAX_TEXT = 2000
MAX_REFS = 20
DEFAULT_LIMIT = 20
MAX_LIMIT = 100

#: Keys generated for options that do not name one. Short on purpose: the key is
#: what an answer stores, and a person reading the record should see a choice
#: rather than a hash.
_GENERATED_KEYS = "abcdef"


def _text(value: Any, *, field: str, required: bool = True, limit: int = MAX_TEXT) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise DomainError(
            "copilot_decision_invalid",
            f"A decision request needs {field}.",
            status_code=422,
        )
    return text[:limit]


def normalise_options(raw: Any) -> list[dict[str, Any]]:
    """Force the shape a person chooses from and a reviewer later reads.

    A rationale is not required, and its absence is recorded rather than
    rejected: an operator that offers an option it cannot justify has said
    something worth seeing, and dropping the option would hide the choice it
    actually made.
    """
    if not isinstance(raw, list):
        raise DomainError(
            "copilot_decision_invalid", "options must be a list.", status_code=422
        )
    if not (MIN_OPTIONS <= len(raw) <= MAX_OPTIONS):
        raise DomainError(
            "copilot_decision_invalid",
            f"A decision request offers between {MIN_OPTIONS} and {MAX_OPTIONS} options.",
            status_code=422,
        )
    options: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise DomainError(
                "copilot_decision_invalid",
                "each option must be an object with a label.",
                status_code=422,
            )
        key = _text(entry.get("key"), field="an option key", required=False, limit=80)
        if not key:
            key = _GENERATED_KEYS[index]
        if key in seen:
            raise DomainError(
                "copilot_decision_invalid",
                f"Option keys must differ; {key!r} appears twice.",
                status_code=422,
            )
        seen.add(key)
        refs = entry.get("evidence_refs")
        if refs is not None and not isinstance(refs, list):
            raise DomainError(
                "copilot_decision_invalid", "evidence_refs must be a list.", status_code=422
            )
        options.append(
            {
                "key": key,
                "label": _text(entry.get("label"), field="an option label"),
                "rationale": _text(entry.get("rationale"), field="a rationale", required=False),
                "evidence_refs": [
                    _text(ref, field="an evidence reference", required=False, limit=200)
                    for ref in (refs or [])[:MAX_REFS]
                    if str(ref or "").strip()
                ],
            }
        )
    return options


def record(
    session: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    asked_by: str,
    question: str,
    options: Any,
    recommended: str | None = None,
    run_id: uuid.UUID | None = None,
) -> CopilotDecisionRequest:
    """Open one question. Never answers it, and never answers an earlier one."""
    bots.require(asked_by)
    normalised = normalise_options(options)
    keys = {option["key"] for option in normalised}
    choice = _text(recommended, field="a recommendation", required=False, limit=80)
    if choice and choice not in keys:
        # A recommendation pointing at nothing would render as a missing
        # default, and the reader could not tell whether the operator meant an
        # option that was dropped or mistyped one that never existed.
        raise DomainError(
            "copilot_decision_invalid",
            f"The recommended option {choice!r} is not one of the options offered.",
            status_code=422,
        )
    row = CopilotDecisionRequest(
        project_id=project_id,
        run_id=run_id,
        asked_by=asked_by,
        question=_text(question, field="a question"),
        options=normalised,
        recommended=choice or None,
        status="open",
        created_by=user_id,
    )
    session.add(row)
    session.flush()
    return row


def require(session: Session, request_id: uuid.UUID) -> CopilotDecisionRequest:
    """The question, or a 404. The lookup lives here rather than in the route.

    `test_api_modules_do_not_access_sqlalchemy_sessions_directly` is the rule,
    and the reason is this module: everything that decides what a decision
    request *is* - including that a missing one is a 404 and not an empty
    answer - belongs where the rest of its rules are.
    """
    row = session.get(CopilotDecisionRequest, request_id)
    if row is None:
        raise DomainError(
            "copilot_decision_not_found", "The decision request was not found", status_code=404
        )
    return row


def requests(
    session: Session,
    *,
    project_id: uuid.UUID,
    status: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[CopilotDecisionRequest]:
    """This project's questions, newest first, optionally by status."""
    if status is not None and status not in STATUSES:
        raise DomainError(
            "copilot_decision_invalid",
            f"status must be one of {sorted(STATUSES)}.",
            status_code=422,
        )
    stmt = select(CopilotDecisionRequest).where(CopilotDecisionRequest.project_id == project_id)
    if status:
        stmt = stmt.where(CopilotDecisionRequest.status == status)
    stmt = stmt.order_by(CopilotDecisionRequest.created_at.desc()).limit(
        max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    )
    return list(session.scalars(stmt))


def answer(
    session: Session,
    row: CopilotDecisionRequest,
    *,
    project: Project,
    user: User,
    choice: str,
    note: str = "",
) -> CopilotDecisionRequest:
    """Settle the question and write the decision record it produced.

    The record is written here rather than left to the caller because the two
    are one act: an answer nobody recorded is a preference, and this table is
    not where the project's decisions live.
    """
    from ..timeline.schemas import TimelineEntryCreate
    from ..timeline.service import create_entry

    if row.status != "open":
        raise DomainError(
            "copilot_decision_settled",
            "This question has already been settled.",
            status_code=409,
        )
    options = {option["key"]: option for option in (row.options or [])}
    if choice not in options:
        raise DomainError(
            "copilot_decision_invalid",
            f"{choice!r} is not one of the options offered.",
            status_code=422,
        )
    chosen = options[choice]
    comment = _text(note, field="a note", required=False)

    rejected = [option for key, option in options.items() if key != choice]
    body = "\n\n".join(
        [
            row.question,
            f"Chosen: {chosen['label']}",
            *( [f"Because: {chosen['rationale']}"] if chosen.get("rationale") else [] ),
            *( [f"Note: {comment}"] if comment else [] ),
            # The branches not taken are the part of a decision that is worth
            # the most later and is never written down unless something writes
            # it down at the moment of the decision.
            "Not chosen: "
            + "; ".join(
                f"{option['label']}" + (f" ({option['rationale']})" if option.get("rationale") else "")
                for option in rejected
            ),
        ]
    )
    provenance: dict[str, list[str]] = {
        "external_refs": [
            f"copilot-decision-request:{row.id}",
            *( [f"copilot-agent-run:{row.run_id}"] if row.run_id else [] ),
            *[ref for option in options.values() for ref in option.get("evidence_refs", [])],
        ]
    }
    entry = create_entry(
        session,
        project,
        TimelineEntryCreate(
            occurred_at=datetime.now(UTC),
            entry_type="decision",
            title=row.question[:300],
            summary=f"{chosen['label']}"[:1000],
            body=body,
            phase="copilot_decision",
            provenance=provenance,
            tags=["copilot", "decision_request"],
        ),
        user,
        # The operator drafted the options; the person chose. Neither "human"
        # nor "agent" is true of this entry, and the third state exists for it.
        decided_by="agent_proposed_human_confirmed",
    )

    row.status = "answered"
    row.answer = choice
    row.answer_note = comment or None
    row.answered_by = user.id
    row.answered_at = datetime.now(UTC)
    row.decision_entry_id = entry.id
    row.version += 1
    session.flush()
    return row


def withdraw(session: Session, row: CopilotDecisionRequest) -> CopilotDecisionRequest:
    """Close a question that no longer needs an answer, leaving it readable.

    Not a delete: a question the work moved past still says what was being
    weighed at the time, and an inbox that empties by forgetting teaches people
    that it forgets.
    """
    if row.status == "answered":
        raise DomainError(
            "copilot_decision_settled",
            "An answered question is part of the record and is not withdrawn.",
            status_code=409,
        )
    row.status = "withdrawn"
    row.version += 1
    session.flush()
    return row


def to_json_model(row: CopilotDecisionRequest) -> dict[str, Any]:
    """The row for the REST schema, which keeps native types."""
    return {
        "id": row.id,
        "project_id": row.project_id,
        "run_id": row.run_id,
        "asked_by": row.asked_by,
        "question": row.question,
        "options": list(row.options or []),
        "recommended": row.recommended,
        "status": row.status,
        "answer": row.answer,
        "answer_note": row.answer_note,
        "answered_by": row.answered_by,
        "answered_at": row.answered_at,
        "decision_entry_id": row.decision_entry_id,
        "version": row.version,
        "created_at": row.created_at,
    }


def to_json(row: CopilotDecisionRequest) -> dict[str, Any]:
    """The row as a tool result, which is JSON handed to a model."""
    return {
        "id": str(row.id),
        "asked_by": row.asked_by,
        "question": row.question,
        "options": list(row.options or []),
        "recommended": row.recommended,
        "status": row.status,
        "answer": row.answer,
        "answered_at": row.answered_at.isoformat() if row.answered_at else None,
    }
