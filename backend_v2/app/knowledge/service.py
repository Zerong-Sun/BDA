import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..core.models import update_versioned
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from .models import KnowledgeEntry
from .repository import KnowledgeRepository
from .schemas import KnowledgeCreate, KnowledgeUpdate


def search_entries(session: Session, project_id: uuid.UUID, query: str, *, limit: int = 12) -> list[KnowledgeEntry]:
    return KnowledgeRepository(session).search(project_id, query, limit=limit)


def project_entries(session: Session, project_id: uuid.UUID) -> list[KnowledgeEntry]:
    return list(session.scalars(select(KnowledgeEntry).where(KnowledgeEntry.project_id == project_id)))


def save_content_addressed_entry(
    session: Session,
    *,
    entry_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by: uuid.UUID,
    title: str,
    entry_type: str,
    content: str,
    tags: list[str],
    source: dict,
) -> KnowledgeEntry:
    """Return the revision whose id is derived from its content, creating it at most once.

    A row added earlier in the same transaction is not yet visible to `get`, so it is
    looked up among pending objects too; otherwise two refreshes in one transaction
    would insert the same primary key twice.
    """
    existing = session.get(KnowledgeEntry, entry_id)
    if existing is not None:
        return existing
    pending = next((row for row in session.new if isinstance(row, KnowledgeEntry) and row.id == entry_id), None)
    if pending is not None:
        return pending
    row = KnowledgeEntry(
        id=entry_id,
        project_id=project_id,
        created_by=created_by,
        title=title,
        entry_type=entry_type,
        content=content,
        tags=tags,
        source=source,
    )
    session.add(row)
    return row


def save_package_entry(
    session: Session,
    project: Project,
    existing: KnowledgeEntry | None,
    *,
    entry_type: str,
    title: str,
    content: str,
    source: dict,
    tags: list[str],
    created_by: uuid.UUID | None = None,
) -> None:
    """Create or refresh a knowledge entry owned by an imported research package.

    Package entries are attributed to the project owner unless an importing user is
    named, and are not editable through the user-facing entry API, so this path skips
    `_require_user_entry_type`.
    """
    if existing is None:
        session.add(
            KnowledgeEntry(
                project_id=project.id,
                title=title,
                content=content,
                entry_type=entry_type,
                source=source,
                tags=tags,
                created_by=created_by or project.owner_id,
            )
        )
        return
    update_versioned(existing, title=title, content=content, source=source)


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
