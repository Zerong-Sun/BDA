from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.etag import parse_if_match
from ..identity.deps import current_user
from ..identity.models import User
from ..projects.service import require_project, require_project_permission
from . import service
from .schemas import FeedbackCreate, LessonCreate, LessonImport, ManualExecution, ReviewCreate

router = APIRouter(tags=["design-memory"])


@router.post(
    "/workflow-runs/{workflow_id}/design-learning/manual-execution", openapi_extra={"x-permission": "project:write"}
)
def post_manual_execution(
    workflow_id: uuid.UUID,
    payload: ManualExecution,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    project, workflow = service.scope(session, workflow_id, user, write=True)
    return service.manual_execution(session, project, workflow, user, payload.phase, parse_if_match(if_match))


@router.get("/projects/{project_id}/design-lessons")
def list_lessons(project_id: uuid.UUID, session: Session = Depends(get_session), user: User = Depends(current_user)):
    require_project(session, project_id, user)
    return {"items": [service.serialize(r) for r in service.lessons(session, project_id)]}


@router.post("/projects/{project_id}/design-lessons", status_code=201, openapi_extra={"x-permission": "project:write"})
def post_lesson(
    project_id: uuid.UUID,
    payload: LessonCreate,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    project = require_project_permission(session, project_id, user, "write")
    return service.serialize(service.save_lesson(session, project, user, payload))


@router.post(
    "/projects/{project_id}/design-lessons/import", status_code=201, openapi_extra={"x-permission": "project:write"}
)
def import_lesson(
    project_id: uuid.UUID,
    payload: LessonImport,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    project = require_project_permission(session, project_id, user, "write")
    return service.serialize(service.import_lesson(session, project, user, payload.source_id))


@router.get("/workflow-runs/{workflow_id}/design-learning")
def get_design_learning(
    workflow_id: uuid.UUID, session: Session = Depends(get_session), user: User = Depends(current_user)
):
    _, workflow = service.scope(session, workflow_id, user)
    return {
        **service.review_state(session, workflow),
        "workflow_version": workflow.version,
        "history": service.review_history(session, workflow),
    }


@router.post(
    "/workflow-runs/{workflow_id}/design-learning/reviews",
    status_code=201,
    openapi_extra={"x-permission": "project:write"},
)
def post_review(
    workflow_id: uuid.UUID,
    payload: ReviewCreate,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    project, workflow = service.scope(session, workflow_id, user, write=True)
    return service.serialize(service.save_review(session, project, workflow, user, payload, parse_if_match(if_match)))


@router.post(
    "/workflow-runs/{workflow_id}/design-learning/feedback",
    status_code=201,
    openapi_extra={"x-permission": "project:write"},
)
def post_feedback(
    workflow_id: uuid.UUID,
    payload: FeedbackCreate,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    project, workflow = service.scope(session, workflow_id, user, write=True)
    return service.serialize(service.save_feedback(session, project, workflow, user, payload))
