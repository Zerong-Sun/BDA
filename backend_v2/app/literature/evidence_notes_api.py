from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.etag import etag, parse_if_match
from ..core.pagination import decode_cursor, encode_cursor
from ..core.problem import DomainError
from ..identity.deps import current_user
from ..identity.models import User
from ..projects.service import require_project_permission
from . import evidence_notes as service
from .models import LiteratureClaim, LiteratureDocument
from .schemas import EvidenceNotePage, EvidenceNoteResponse, EvidenceNoteWrite, ReviewUpdate

router = APIRouter()


def writable_note(session: Session, note_id: uuid.UUID, user: User) -> tuple[LiteratureClaim, LiteratureDocument]:
    claim = session.scalar(select(LiteratureClaim).where(LiteratureClaim.id == note_id).with_for_update())
    if claim is None or not service.is_note(claim):
        raise DomainError("evidence_note_not_found", "Curated evidence note was not found", status_code=404)
    document = session.get(LiteratureDocument, claim.document_id)
    if document is None:
        raise DomainError("literature_document_not_found", "Literature document was not found", status_code=404)
    require_project_permission(session, document.project_id, user, "write")
    return claim, document


@router.get("/projects/{project_id}/literature/evidence-notes", response_model=EvidenceNotePage)
def list_evidence_notes(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> EvidenceNotePage:
    require_project_permission(session, project_id, user, "read")
    rows = service.note_rows(session, project_id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return EvidenceNotePage(
        items=[service.response(*row) for row in page],
        next_cursor=encode_cursor(page[-1][0].id) if len(rows) > limit and page else None,
    )


@router.post("/literature/documents/{document_id}/evidence-notes", response_model=EvidenceNoteResponse,
             status_code=201, openapi_extra={"x-permission": "literature.review"})
def create_evidence_note(
    document_id: uuid.UUID, payload: EvidenceNoteWrite, response: Response,
    session: Session = Depends(get_session), user: User = Depends(current_user),
) -> EvidenceNoteResponse:
    document = session.get(LiteratureDocument, document_id)
    if document is None:
        raise DomainError("literature_document_not_found", "Literature document was not found", status_code=404)
    require_project_permission(session, document.project_id, user, "write")
    result = service.save_note(session, document, payload, user)
    response.headers["ETag"] = etag(result.version)
    return result


@router.put("/literature/evidence-notes/{note_id}", response_model=EvidenceNoteResponse,
            openapi_extra={"x-permission": "literature.review"})
def update_evidence_note(
    note_id: uuid.UUID, payload: EvidenceNoteWrite, response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session), user: User = Depends(current_user),
) -> EvidenceNoteResponse:
    claim, document = writable_note(session, note_id, user)
    result = service.save_note(session, document, payload, user, claim, parse_if_match(if_match))
    response.headers["ETag"] = etag(result.version)
    return result


@router.patch("/literature/evidence-notes/{note_id}/review", response_model=EvidenceNoteResponse,
              openapi_extra={"x-permission": "literature.review"})
def review_evidence_note(
    note_id: uuid.UUID, payload: ReviewUpdate, response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session), user: User = Depends(current_user),
) -> EvidenceNoteResponse:
    claim, document = writable_note(session, note_id, user)
    result = service.review_note(session, claim, document, payload, parse_if_match(if_match), user)
    response.headers["ETag"] = etag(result.version)
    return result
