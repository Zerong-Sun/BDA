from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.etag import etag, parse_if_match
from ..core.pagination import decode_time_cursor, encode_time_cursor
from ..core.problem import DomainError
from ..identity.deps import current_user, require_command
from ..identity.models import User
from ..projects.models import Project
from ..projects.service import require_project
from .models import ProjectTimelineEntry
from .repository import TimelineRepository
from .schemas import (
    TimelineEntryCreate,
    TimelineEntryDeleteResponse,
    TimelineEntryPage,
    TimelineEntryResponse,
    TimelineEntryUpdate,
)
from .service import create_entry, update_entry
from .service import delete_entry as delete_entry_service

router = APIRouter(tags=["timeline"])


@router.get("/projects/{project_id}/timeline", response_model=TimelineEntryPage)
def list_timeline(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    entry_type: str | None = Query(default=None),
    phase: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> TimelineEntryPage:
    """The project's decision record, oldest first.

    Filters are the questions this table exists to answer: "what did we rule out"
    (outcome=refuted), "what happened in phase 2" (phase=phase-2), "show only the
    problems" (entry_type=problem).
    """
    require_project(session, project_id, user)
    rows = TimelineRepository(session).list_project(
        project_id, decode_time_cursor(cursor), limit, entry_type=entry_type, phase=phase, outcome=outcome
    )
    page = rows[:limit]
    return TimelineEntryPage(
        items=[TimelineEntryResponse.model_validate(row) for row in page],
        next_cursor=(
            encode_time_cursor(page[-1].occurred_at, page[-1].id) if len(rows) > limit and page else None
        ),
    )


@router.post(
    "/projects/{project_id}/timeline",
    response_model=TimelineEntryResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "timeline.create"},
)
def post_timeline_entry(
    project_id: uuid.UUID,
    payload: TimelineEntryCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> TimelineEntryResponse:
    project = require_project(session, project_id, user)
    return TimelineEntryResponse.model_validate(create_entry(session, project, payload, user))


def _entry(session: Session, entry_id: uuid.UUID, user: User) -> tuple[ProjectTimelineEntry, Project]:
    entry = TimelineRepository(session).get(entry_id)
    if entry is None:
        raise DomainError("timeline_entry_not_found", "Timeline entry was not found", status_code=404)
    project = require_project(session, entry.project_id, user)
    return entry, project


@router.get("/timeline/{entry_id}", response_model=TimelineEntryResponse)
def get_timeline_entry(
    entry_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> TimelineEntryResponse:
    entry, _ = _entry(session, entry_id, user)
    response.headers["ETag"] = etag(entry.version)
    return TimelineEntryResponse.model_validate(entry)


@router.patch(
    "/timeline/{entry_id}",
    response_model=TimelineEntryResponse,
    openapi_extra={"x-permission": "timeline.update"},
)
def patch_timeline_entry(
    entry_id: uuid.UUID,
    payload: TimelineEntryUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> TimelineEntryResponse:
    entry, project = _entry(session, entry_id, user)
    update_entry(session, project, entry, payload, parse_if_match(if_match), actor=user)
    response.headers["ETag"] = etag(entry.version)
    return TimelineEntryResponse.model_validate(entry)


@router.delete(
    "/timeline/{entry_id}",
    response_model=TimelineEntryDeleteResponse,
    openapi_extra={"x-permission": "timeline.delete"},
)
def delete_timeline_entry(
    entry_id: uuid.UUID,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> TimelineEntryDeleteResponse:
    entry, project = _entry(session, entry_id, user)
    delete_entry_service(session, project, entry, parse_if_match(if_match), actor=user)
    return TimelineEntryDeleteResponse(id=entry.id)
