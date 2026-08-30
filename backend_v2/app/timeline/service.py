from __future__ import annotations

from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from .models import ProjectTimelineEntry
from .repository import TimelineRepository
from .schemas import TimelineEntryCreate, TimelineEntryUpdate


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


def create_entry(
    session: Session, project: Project, payload: TimelineEntryCreate, user: User
) -> ProjectTimelineEntry:
    _check_link(session, project, payload.supersedes_id, "supersedes_id")
    _check_link(session, project, payload.caused_by_id, "caused_by_id")
    data = payload.model_dump()
    data["code_refs"] = [ref.model_dump() if hasattr(ref, "model_dump") else ref for ref in payload.code_refs]
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
    session: Session, project: Project, entry: ProjectTimelineEntry, payload: TimelineEntryUpdate, expected: int
) -> ProjectTimelineEntry:
    if entry.version != expected:
        raise DomainError("version_conflict", "Timeline entry was modified by another request", status_code=412)
    changes = payload.model_dump(exclude_unset=True)
    for field in ("supersedes_id", "caused_by_id"):
        if field in changes:
            if changes[field] == entry.id:
                raise DomainError("timeline_self_link", f"{field} cannot point at the entry itself", status_code=422)
            _check_link(session, project, changes[field], field)
    if "code_refs" in changes and changes["code_refs"] is not None:
        changes["code_refs"] = [
            ref.model_dump() if hasattr(ref, "model_dump") else ref for ref in changes["code_refs"]
        ]
    for field, value in changes.items():
        setattr(entry, field, value)
    entry.version += 1
    return entry


def delete_entry(session: Session, entry: ProjectTimelineEntry, expected: int) -> None:
    if entry.version != expected:
        raise DomainError("version_conflict", "Timeline entry was modified by another request", status_code=412)
    session.delete(entry)
