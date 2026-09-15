"""Which residues a design should target, and who said so.

The platform could already measure a structure (`structures/kernels.py`) and
could already run a design against named residues - the plugin registry has
carried `ppi.hotspot_res` and `target_hotspot_residues` since RFdiffusion and
BindCraft were registered. Between the two there was nothing: no object a
person could point at, confirm, and hand to a job. The residues lived in a
sentence in a chat window and were retyped into a parameter box.

This module is that object, and its whole design is the `origin` column.

**A measurement is not a decision.** An operator may propose a set; proposing
records `origin="agent"` and `status="proposed"`, and nothing downstream may
consume it. A person confirms it, and the row becomes
`agent_proposed_human_confirmed` - the same three-state attribution
`project_timeline_entries.decided_by` uses, deliberately spelled the same way,
because it is the same question about the same kind of judgement. A set the
person picked themselves is `human` from the start.

**Confirmation is the only gate that matters**, because the confirmed set is
what P4 feeds to a design job. `confirm` therefore takes a `User`, is
unreachable from any tool, and refuses a set with no residues: an empty
"confirmed" set would silently mean "design against nothing in particular",
which is exactly the run nobody meant to submit.

**Residues are stored as the file numbers a person reads** - `{chain, seq}` with
the author numbering - because that is what a viewer shows, what a paper cites,
and what the design tools take on their command lines. Translating to canonical
numbering here would move every residue in the files where the two differ.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.problem import DomainError
from ..identity.models import User
from .models import TargetHotspotSet

#: Where the set came from. Same vocabulary as `timeline.DECIDED_BY`, minus the
#: "unspecified" state: a hotspot set always has an author.
ORIGINS = ("agent", "human", "agent_proposed_human_confirmed")

#: `proposed` cannot reach a job; `confirmed` can; `rejected` stays readable so
#: a set that was considered and refused is part of the record rather than a
#: gap in it.
STATUSES = ("proposed", "confirmed", "rejected")

MAX_RESIDUES = 40
MAX_LABEL = 200
MAX_TEXT = 2000
MAX_REFS = 20
DEFAULT_LIMIT = 50
MAX_LIMIT = 200

#: A chain id as structure files write them: one or a few alphanumerics.
_CHAIN = re.compile(r"^[A-Za-z0-9]{1,4}$")


def normalise_residues(raw: Any) -> list[dict[str, Any]]:
    """`[{chain, seq}]`, de-duplicated, in the order given.

    Order is kept because an operator that lists an anchor residue first is
    saying something; duplicates are dropped because a set is a set, and a
    residue named twice would be counted twice by anything that measures the
    interface this describes.
    """
    if not isinstance(raw, list) or not raw:
        raise DomainError(
            "target_hotspot_invalid",
            "A hotspot set names at least one residue.",
            status_code=422,
        )
    if len(raw) > MAX_RESIDUES:
        raise DomainError(
            "target_hotspot_invalid",
            f"A hotspot set names at most {MAX_RESIDUES} residues; {len(raw)} were given.",
            status_code=422,
        )
    residues: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise DomainError(
                "target_hotspot_invalid",
                "each residue is an object with a chain and a residue number.",
                status_code=422,
            )
        chain = str(entry.get("chain") or "").strip()
        if not _CHAIN.match(chain):
            raise DomainError(
                "target_hotspot_invalid", f"{chain!r} is not a chain id.", status_code=422
            )
        raw_seq = entry.get("seq")
        # `bool` is an `int` in Python, so True would otherwise be read as
        # residue 1 - a silently wrong residue is worse than a rejected one.
        if raw_seq is None or isinstance(raw_seq, bool):
            raise DomainError(
                "target_hotspot_invalid",
                f"{raw_seq!r} is not a residue number.",
                status_code=422,
            )
        try:
            seq = int(raw_seq)
        except (TypeError, ValueError) as error:
            raise DomainError(
                "target_hotspot_invalid",
                f"{raw_seq!r} is not a residue number.",
                status_code=422,
            ) from error
        if (chain, seq) in seen:
            continue
        seen.add((chain, seq))
        residue: dict[str, Any] = {"chain": chain, "seq": seq}
        name = str(entry.get("name") or "").strip()[:8]
        if name:
            # The three-letter or one-letter code, when the caller knows it. Kept
            # because "A164" and "A164 ARG" read differently to a person checking
            # the set against a structure, and the viewer cannot supply it later.
            residue["name"] = name
        residues.append(residue)
    return residues


def _text(value: Any, *, field: str, required: bool = True, limit: int = MAX_TEXT) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise DomainError(
            "target_hotspot_invalid", f"A hotspot set needs {field}.", status_code=422
        )
    return text[:limit]


def record(
    session: Session,
    *,
    project_id: uuid.UUID,
    target_id: uuid.UUID,
    user_id: uuid.UUID,
    label: str,
    residues: Any,
    origin: str,
    structure_artifact_id: uuid.UUID | None = None,
    rationale: str = "",
    evidence_refs: Any = None,
) -> TargetHotspotSet:
    """Write one set. An operator's set is proposed; a person's is confirmed.

    The two cases differ only in `origin` and `status`, and both are derived
    here rather than accepted from the caller: a tool that could pass
    `origin="human"` would be able to mint a confirmed set, which is the one
    thing this table exists to prevent.
    """
    if origin not in {"agent", "human"}:
        raise DomainError(
            "target_hotspot_invalid",
            "A set is recorded as proposed by an operator or chosen by a person.",
            status_code=422,
        )
    refs = evidence_refs if isinstance(evidence_refs, list) else []
    row = TargetHotspotSet(
        project_id=project_id,
        target_id=target_id,
        structure_artifact_id=structure_artifact_id,
        label=_text(label, field="a label", limit=MAX_LABEL),
        residues=normalise_residues(residues),
        rationale=_text(rationale, field="a rationale", required=False),
        evidence_refs=[
            _text(ref, field="an evidence reference", required=False, limit=200)
            for ref in refs[:MAX_REFS]
            if str(ref or "").strip()
        ],
        origin=origin,
        status="confirmed" if origin == "human" else "proposed",
        created_by=user_id,
        confirmed_by=user_id if origin == "human" else None,
    )
    session.add(row)
    session.flush()
    return row


def require(session: Session, hotspot_set_id: uuid.UUID) -> TargetHotspotSet:
    row = session.get(TargetHotspotSet, hotspot_set_id)
    if row is None:
        raise DomainError(
            "target_hotspot_not_found", "The hotspot set was not found", status_code=404
        )
    return row


def sets(
    session: Session,
    *,
    project_id: uuid.UUID,
    target_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[TargetHotspotSet]:
    if status is not None and status not in STATUSES:
        raise DomainError(
            "target_hotspot_invalid", f"status must be one of {sorted(STATUSES)}.", status_code=422
        )
    stmt = select(TargetHotspotSet).where(TargetHotspotSet.project_id == project_id)
    if target_id:
        stmt = stmt.where(TargetHotspotSet.target_id == target_id)
    if status:
        stmt = stmt.where(TargetHotspotSet.status == status)
    stmt = stmt.order_by(TargetHotspotSet.created_at.desc()).limit(
        max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    )
    return list(session.scalars(stmt))


def confirm(session: Session, row: TargetHotspotSet, *, user: User) -> TargetHotspotSet:
    """A person takes responsibility for this set; only then can a job use it."""
    if row.status == "confirmed":
        # Idempotent rather than an error: two people clicking confirm is not a
        # conflict, and the second click should not look like a failure.
        return row
    if row.status == "rejected":
        raise DomainError(
            "target_hotspot_rejected",
            "A rejected set is part of the record. Propose a new one instead.",
            status_code=409,
        )
    if not row.residues:
        raise DomainError(
            "target_hotspot_invalid",
            "An empty set cannot be confirmed: a design against no residues in "
            "particular is not what anybody meant to submit.",
            status_code=422,
        )
    row.status = "confirmed"
    # The operator proposed it and a person accepted it. Neither "agent" nor
    # "human" describes that, which is why the third state exists.
    row.origin = "agent_proposed_human_confirmed" if row.origin == "agent" else row.origin
    row.confirmed_by = user.id
    row.version += 1
    session.flush()
    return row


def reject(session: Session, row: TargetHotspotSet, *, user: User, reason: str = "") -> TargetHotspotSet:
    """Refuse a proposed set, keeping it and the reason in the record."""
    if row.status == "confirmed":
        raise DomainError(
            "target_hotspot_confirmed",
            "A confirmed set is what a job may already have used; it is not rejected afterwards.",
            status_code=409,
        )
    row.status = "rejected"
    row.confirmed_by = user.id
    note = _text(reason, field="a reason", required=False)
    if note:
        row.rationale = f"{row.rationale}\n\nRejected: {note}".strip()
    row.version += 1
    session.flush()
    return row


def as_residue_argument(row: TargetHotspotSet) -> str:
    """The confirmed set as design tools take it: `A164,A168,A171`.

    One formatter, because two would drift: RFdiffusion's `ppi.hotspot_res` and
    BindCraft's `target_hotspot_residues` both read this shape, and the point of
    P4 is that nobody retypes it.
    """
    if row.status != "confirmed":
        raise DomainError(
            "target_hotspot_not_confirmed",
            "Only a confirmed hotspot set can be used as a design parameter.",
            status_code=409,
        )
    return ",".join(f"{residue['chain']}{residue['seq']}" for residue in row.residues)


def to_json(row: TargetHotspotSet) -> dict[str, Any]:
    """The row as a tool result, which is JSON handed to a model."""
    return {
        "id": str(row.id),
        "target_id": str(row.target_id),
        "structure_artifact_id": str(row.structure_artifact_id) if row.structure_artifact_id else None,
        "label": row.label,
        "residues": list(row.residues or []),
        "rationale": row.rationale,
        "evidence_refs": list(row.evidence_refs or []),
        "origin": row.origin,
        "status": row.status,
    }
