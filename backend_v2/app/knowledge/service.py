from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from .models import KnowledgeEntry
from .schemas import KnowledgeCreate, KnowledgeUpdate


def create_entry(session: Session, project: Project, payload: KnowledgeCreate, user: User) -> KnowledgeEntry:
    _require_user_entry_type(payload.entry_type)
    row = KnowledgeEntry(project_id=project.id, created_by=user.id, **payload.model_dump())
    session.add(row)
    session.flush()
    record_audit(
        session,
        action="knowledge.create",
        entity_type="knowledge_entry",
        entity_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return row


def update_entry(entry: KnowledgeEntry, payload: KnowledgeUpdate, expected: int) -> KnowledgeEntry:
    _require_user_entry_type(entry.entry_type)
    _require_user_entry_type(payload.entry_type)
    if entry.version != expected:
        raise DomainError("version_conflict", "Knowledge entry was modified by another request", status_code=412)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    entry.version += 1
    return entry


def delete_entry(session: Session, entry: KnowledgeEntry, expected: int) -> None:
    _require_user_entry_type(entry.entry_type)
    if entry.version != expected:
        raise DomainError("version_conflict", "Knowledge entry was modified by another request", status_code=412)
    session.delete(entry)


def _require_user_entry_type(entry_type: str | None) -> None:
    if entry_type == "bot_work_record":
        raise DomainError(
            "system_record_read_only",
            "Bot work records are generated from source events and cannot be edited manually",
            status_code=403,
        )
