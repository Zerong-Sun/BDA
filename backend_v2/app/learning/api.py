from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.etag import etag, parse_if_match
from ..core.pagination import decode_cursor, encode_cursor
from ..experiments.schemas import ExperimentResultResponse
from ..identity.deps import current_user, require_command
from ..identity.models import User
from ..projects.service import require_project, require_project_permission
from . import service
from .repository import KINDS, LearningRepository
from .schemas import (
    AssayCreate,
    AssayResponse,
    DatasetCreate,
    DatasetResponse,
    LearningDecisionCreate,
    LearningDecisionResponse,
    LearningDecisionReview,
    LearningPackage,
    LearningPage,
    ModelCreate,
    ModelResponse,
    ModelReview,
    ObservationCreate,
    StudyCreate,
    StudyResponse,
)

router = APIRouter(prefix="/projects/{project_id}/learning", tags=["learning"])
Kind = Literal["assays", "studies", "datasets", "models", "decisions"]
ResponseRecord = AssayResponse | StudyResponse | DatasetResponse | ModelResponse | LearningDecisionResponse
RESPONSES: dict[str, type[ResponseRecord]] = {
    "assays": AssayResponse,
    "studies": StudyResponse,
    "datasets": DatasetResponse,
    "models": ModelResponse,
    "decisions": LearningDecisionResponse,
}


@router.get("/{kind}", response_model=LearningPage)
def list_learning_records(
    project_id: uuid.UUID,
    kind: Kind,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> LearningPage:
    require_project(session, project_id, user)
    rows = LearningRepository(session).list(KINDS[kind], project_id, decode_cursor(cursor), limit)
    items = rows[:limit]
    return LearningPage(
        items=[RESPONSES[kind].model_validate(row) for row in items],
        next_cursor=encode_cursor(items[-1].id) if len(rows) > limit else None,
    )


@router.get(
    "/{kind}/{record_id}",
    response_model=AssayResponse | StudyResponse | DatasetResponse | ModelResponse | LearningDecisionResponse,
)
def get_learning_record(
    project_id: uuid.UUID,
    kind: Kind,
    record_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    project = require_project(session, project_id, user)
    row = service.require_record(session, KINDS[kind], project, record_id)
    response.headers["ETag"] = etag(row.version)
    return RESPONSES[kind].model_validate(row)


@router.post(
    "/assays", response_model=AssayResponse, status_code=201, openapi_extra={"x-permission": "learning.assay.create"}
)
def post_learning_assay(
    project_id: uuid.UUID,
    payload: AssayCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
):
    project = require_project_permission(session, project_id, user, "experiment")
    return service.create_assay(session, project, user, payload)


@router.post(
    "/studies", response_model=StudyResponse, status_code=201, openapi_extra={"x-permission": "learning.study.create"}
)
def post_learning_study(
    project_id: uuid.UUID,
    payload: StudyCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
):
    project = require_project_permission(session, project_id, user, "write")
    return service.create_study(session, project, user, payload)


@router.post(
    "/observations",
    response_model=ExperimentResultResponse,
    status_code=201,
    openapi_extra={"x-permission": "learning.observation.create"},
)
def post_learning_observation(
    project_id: uuid.UUID,
    payload: ObservationCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
):
    project = require_project_permission(session, project_id, user, "experiment")
    return service.create_observation(session, project, user, payload)


@router.post(
    "/datasets",
    response_model=DatasetResponse,
    status_code=201,
    openapi_extra={"x-permission": "learning.dataset.freeze"},
)
def post_learning_dataset(
    project_id: uuid.UUID,
    payload: DatasetCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
):
    project = require_project_permission(session, project_id, user, "write")
    return service.freeze_dataset(session, project, user, payload)


@router.post(
    "/models", response_model=ModelResponse, status_code=201, openapi_extra={"x-permission": "learning.model.train"}
)
def post_learning_model(
    project_id: uuid.UUID,
    payload: ModelCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
):
    project = require_project_permission(session, project_id, user, "write")
    return service.train_model(session, project, user, payload.dataset_id)


@router.post(
    "/models/{model_id}/review", response_model=ModelResponse, openapi_extra={"x-permission": "learning.model.review"}
)
def review_learning_model(
    project_id: uuid.UUID,
    model_id: uuid.UUID,
    payload: ModelReview,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
):
    project = require_project_permission(session, project_id, user, "write")
    row = service.review_model(session, project, user, model_id, payload, parse_if_match(if_match))
    response.headers["ETag"] = etag(row.version)
    return row


@router.post(
    "/decisions",
    response_model=LearningDecisionResponse,
    status_code=201,
    openapi_extra={"x-permission": "learning.decision.create"},
)
def post_learning_decision(
    project_id: uuid.UUID,
    payload: LearningDecisionCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
):
    project = require_project_permission(session, project_id, user, "write")
    return service.create_decision(session, project, user, payload)


@router.post(
    "/decisions/{decision_id}/review",
    response_model=LearningDecisionResponse,
    openapi_extra={"x-permission": "learning.decision.review"},
)
def review_learning_decision(
    project_id: uuid.UUID,
    decision_id: uuid.UUID,
    payload: LearningDecisionReview,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
):
    project = require_project_permission(session, project_id, user, "write")
    row = service.review_decision(session, project, user, decision_id, payload, parse_if_match(if_match))
    response.headers["ETag"] = etag(row.version)
    return row


@router.get("/decisions/{decision_id}/export", response_model=LearningPackage)
def export_learning_decision(
    project_id: uuid.UUID,
    decision_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    project = require_project(session, project_id, user)
    return service.export_decision(session, project, decision_id)
