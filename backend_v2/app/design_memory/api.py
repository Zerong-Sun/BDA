from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.etag import parse_if_match
from ..core.problem import DomainError
from ..identity.deps import current_user
from ..identity.models import User
from ..projects.service import require_project, require_project_permission
from ..workflows.models import WorkflowRun
from . import service
from .models import DesignLesson, DesignReview
from .schemas import FeedbackCreate, LessonCreate, LessonImport, ReviewCreate

router = APIRouter(tags=["design-memory"])


def scope(session, workflow_id, user, *, write=False):
    workflow = session.get(WorkflowRun, workflow_id)
    if not workflow:
        raise DomainError("workflow_not_found", "Workflow was not found", status_code=404)
    project = require_project_permission(session, workflow.project_id, user, "write" if write else "read")
    return project, workflow


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
    source = session.get(DesignLesson, payload.source_id)
    if not source:
        raise DomainError("design_lesson_not_found", "Source lesson was not found", status_code=404)
    require_project_permission(session, source.project_id, user, "read")
    if source.project_id == project.id:
        raise DomainError("design_lesson_already_local", "This lesson already belongs to the project", status_code=409)
    body = LessonCreate.model_validate({k: v for k, v in source.payload.items() if k in LessonCreate.model_fields})
    return service.serialize(
        service.save_lesson(
            session,
            project,
            user,
            body,
            origin={
                "project_id": str(source.project_id),
                "lesson_id": str(source.id),
                "snapshot": service.serialize(source),
            },
        )
    )


@router.get("/workflow-runs/{workflow_id}/design-learning")
def get_design_learning(
    workflow_id: uuid.UUID, session: Session = Depends(get_session), user: User = Depends(current_user)
):
    _, workflow = scope(session, workflow_id, user)
    return {
        **service.review_state(session, workflow),
        "workflow_version": workflow.version,
        "history": [
            service.serialize(r)
            for r in session.scalars(
                select(DesignReview)
                .where(DesignReview.workflow_run_id == workflow.id)
                .order_by(DesignReview.created_at.desc())
            )
        ],
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
    project, workflow = scope(session, workflow_id, user, write=True)
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
    project, workflow = scope(session, workflow_id, user, write=True)
    return service.serialize(service.save_feedback(session, project, workflow, user, payload))
