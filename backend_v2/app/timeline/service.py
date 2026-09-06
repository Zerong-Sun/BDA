from __future__ import annotations

from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from .models import ProjectTimelineEntry
from .repository import TimelineRepository
from .schemas import TimelineEntryCreate, TimelineEntryUpdate, check_lane_evidence


def _check_link(session: Session, project: Project, entry_id, field: str) -> None:
    """A link must point at an entry in the same project, and never at itself.

    Cross-project links would leak one project's reasoning into another's timeline; a
    self-link renders the entry unreadable in any view that follows the chain.
    """
    if entry_id is None:
        return
    linked = TimelineRepository(session).get(entry_id)
    if linked is None or linked.project_id != project.id:
        raise DomainError(
            "timeline_link_not_found",
            f"{field} must reference a timeline entry in the same project",
            status_code=422,
        )


def _check_decision_ref_free(
    session: Session, project: Project, decision_ref: str | None, *, excluding=None
) -> None:
    """One row per decision number, per project.

    The unique constraint already guarantees this, but reaching it raises an
    IntegrityError at flush time - a 500 with no useful body, in a code path whose whole
    point is that the numbering is checkable. Asking first turns it into a 409 that says
    which entry already holds the number.
    """
    if decision_ref is None:
        return
    held = TimelineRepository(session).find_by_decision_ref(project.id, decision_ref)
    if held is not None and held.id != excluding:
        raise DomainError(
            "timeline_decision_ref_taken",
            f"decision_ref {decision_ref!r} is already recorded by entry {held.id}",
            status_code=409,
        )


def _dump(items) -> list:
    return [item.model_dump() if hasattr(item, "model_dump") else item for item in items]


def create_entry(
    session: Session, project: Project, payload: TimelineEntryCreate, user: User
) -> ProjectTimelineEntry:
    _check_link(session, project, payload.supersedes_id, "supersedes_id")
    _check_link(session, project, payload.caused_by_id, "caused_by_id")
    _check_decision_ref_free(session, project, payload.decision_ref)
    data = payload.model_dump()
    data["code_refs"] = _dump(payload.code_refs)
    data["alternatives"] = _dump(payload.alternatives)
    row = ProjectTimelineEntry(project_id=project.id, created_by=user.id, **data)
    session.add(row)
    session.flush()
    record_audit(
        session,
        action="timeline.create",
        entity_type="project_timeline_entry",
        entity_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return row


def update_entry(
    session: Session,
    project: Project,
    entry: ProjectTimelineEntry,
    payload: TimelineEntryUpdate,
    expected: int,
    *,
    actor: User,
) -> ProjectTimelineEntry:
    """Apply a partial change, and record who made it.

    ``actor`` is keyword-only and required rather than defaulted: an edit to a decision
    record that leaves no trace is exactly the failure the audit log exists to prevent,
    and a default would let a new call site drop the trail without anyone noticing.
    """
    if entry.version != expected:
        raise DomainError("version_conflict", "Timeline entry was modified by another request", status_code=412)
    changes = payload.model_dump(exclude_unset=True)
    for field in ("supersedes_id", "caused_by_id"):
        if field in changes:
            if changes[field] == entry.id:
                raise DomainError("timeline_self_link", f"{field} cannot point at the entry itself", status_code=422)
            _check_link(session, project, changes[field], field)
    for field in ("code_refs", "alternatives"):
        if changes.get(field) is not None:
            changes[field] = _dump(changes[field])
    if "decision_ref" in changes:
        _check_decision_ref_free(session, project, changes["decision_ref"], excluding=entry.id)
    # The lane rule is a cross-field one, so a PATCH has to be judged on the row as it
    # will be, not on the fields that happen to be in this request. Three separate ways
    # in: clearing provenance on a settled wet decision, turning a dry one wet, and
    # settling an open one - and no request mentions more than one of the three fields.
    merged = {
        "entry_type": changes.get("entry_type", entry.entry_type),
        "lane": changes.get("lane", entry.lane),
        "outcome": changes.get("outcome", entry.outcome),
        "provenance": changes.get("provenance", entry.provenance) or {},
    }
    try:
        check_lane_evidence(
            merged["entry_type"], merged["lane"], merged["outcome"], merged["provenance"]
        )
    except ValueError as exc:
        raise DomainError("timeline_lane_evidence_missing", str(exc), status_code=422) from exc
    for field, value in changes.items():
        setattr(entry, field, value)
    entry.version += 1
    record_audit(
        session,
        action="timeline.update",
        entity_type="project_timeline_entry",
        entity_id=entry.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=actor.id,
    )
    return entry


def delete_entry(
    session: Session, project: Project, entry: ProjectTimelineEntry, expected: int, *, actor: User
) -> None:
    """Remove an entry, freeing its decision number.

    The audit row is written *before* the delete, while the entity id still resolves to
    something; afterwards the only record that the number was ever held is this line.
    """
    if entry.version != expected:
        raise DomainError("version_conflict", "Timeline entry was modified by another request", status_code=412)
    record_audit(
        session,
        action="timeline.delete",
        entity_type="project_timeline_entry",
        entity_id=entry.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=actor.id,
    )
    session.delete(entry)
