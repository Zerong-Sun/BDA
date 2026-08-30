from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.etag import etag, parse_if_match
from ..core.pagination import decode_cursor, encode_cursor
from ..core.problem import DomainError
from ..identity.deps import current_user, require_command
from ..identity.models import User
from ..projects.service import require_project
from .models import KnowledgeEntry
from .repository import KnowledgeRepository
from .schemas import KnowledgeCreate, KnowledgeDeleteResponse, KnowledgePage, KnowledgeResponse, KnowledgeUpdate
from .service import create_entry, update_entry
from .service import delete_entry as delete_entry_service

router = APIRouter(tags=["knowledge"])


@router.get("/projects/{project_id}/knowledge", response_model=KnowledgePage)
def list_entries(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> KnowledgePage:
    require_project(session, project_id, user)
    rows = KnowledgeRepository(session).list_project(project_id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return KnowledgePage(
        items=[KnowledgeResponse.model_validate(x) for x in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.post(
    "/projects/{project_id}/knowledge",
    response_model=KnowledgeResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "knowledge.create"},
)
def post_entry(
    project_id: uuid.UUID,
    payload: KnowledgeCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> KnowledgeResponse:
    return KnowledgeResponse.model_validate(
        create_entry(session, require_project(session, project_id, user), payload, user)
    )


def _entry(session: Session, entry_id: uuid.UUID, user: User) -> KnowledgeEntry:
    entry = KnowledgeRepository(session).get(entry_id)
    if entry is None:
        raise DomainError("knowledge_not_found", "Knowledge entry was not found", status_code=404)
    require_project(session, entry.project_id, user)
    return entry


@router.patch(
    "/knowledge/{entry_id}", response_model=KnowledgeResponse, openapi_extra={"x-permission": "knowledge.update"}
)
def patch_entry(
    entry_id: uuid.UUID,
    payload: KnowledgeUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> KnowledgeResponse:
    entry = _entry(session, entry_id, user)
    update_entry(entry, payload, parse_if_match(if_match))
    response.headers["ETag"] = etag(entry.version)
    return KnowledgeResponse.model_validate(entry)


@router.delete(
    "/knowledge/{entry_id}", response_model=KnowledgeDeleteResponse, openapi_extra={"x-permission": "knowledge.delete"}
)
def delete_entry(
    entry_id: uuid.UUID,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> KnowledgeDeleteResponse:
    entry = _entry(session, entry_id, user)
    delete_entry_service(session, entry, parse_if_match(if_match))
    return KnowledgeDeleteResponse(id=entry.id)
