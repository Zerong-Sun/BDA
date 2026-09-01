from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from ..artifacts.repository import ArtifactRepository
from ..core.database import get_session
from ..core.pagination import decode_cursor, encode_cursor
from ..core.problem import DomainError
from ..identity.deps import current_user, require_command
from ..identity.models import User
from ..platform.operations import enqueue_operation
from ..projects.service import require_project, require_project_permission
from .repository import ExperimentRepository
from .schemas import (
    ExperimentResultBatch,
    ExperimentResultImportAccepted,
    ExperimentResultImportCreate,
    ExperimentResultPage,
    ExperimentResultResponse,
)
from .service import create_results

router = APIRouter(prefix="/projects/{project_id}/experiment-results", tags=["experiments"])


@router.get("", response_model=ExperimentResultPage)
def list_results(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ExperimentResultPage:
    require_project(session, project_id, user)
    items = ExperimentRepository(session).list_project(project_id, after=decode_cursor(cursor), limit=limit)
    has_next = len(items) > limit
    page = items[:limit]
    return ExperimentResultPage(
        items=[ExperimentResultResponse.model_validate(item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if has_next and page else None,
    )


@router.get("/{result_id}", response_model=ExperimentResultResponse)
def get_result(
    project_id: uuid.UUID,
    result_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ExperimentResultResponse:
    require_project(session, project_id, user)
    item = ExperimentRepository(session).get(result_id)
    if item is None or item.project_id != project_id:
        raise DomainError("experiment_result_not_found", "Experiment result was not found", status_code=404)
    response.headers["ETag"] = f'W/"{item.version}"'
    return ExperimentResultResponse.model_validate(item)


@router.post(
    "",
    response_model=list[ExperimentResultResponse],
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "experiment.create"},
)
def post_results(
    project_id: uuid.UUID,
    payload: ExperimentResultBatch,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> list[ExperimentResultResponse]:
    project = require_project_permission(session, project_id, user, "experiment")
    return [ExperimentResultResponse.model_validate(item) for item in create_results(session, project, payload, user)]


@router.post(
    "/imports",
    response_model=ExperimentResultImportAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "experiment.import"},
)
def import_results(
    project_id: uuid.UUID,
    payload: ExperimentResultImportCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ExperimentResultImportAccepted:
    project = require_project_permission(session, project_id, user, "experiment")
    artifact = ArtifactRepository(session).artifact(payload.artifact_id)
    if artifact is None or artifact.project_id != project.id or artifact.status != "available":
        raise DomainError("artifact_not_found", "Available project artifact was not found", status_code=404)
    if artifact.content_type not in {
        "text/csv",
        "application/json",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }:
        raise DomainError(
            "experiment_format_unsupported", "Experiment import must be CSV, JSON, or XLSX", status_code=422
        )
    operation = enqueue_operation(
        session,
        topic="experiment_results.import",
        resource_type="artifact",
        resource_id=artifact.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={
            "artifact_id": str(artifact.id),
            "project_id": str(project.id),
            "created_by": str(user.id),
            "dry_run": payload.dry_run,
        },
    )
    return ExperimentResultImportAccepted(operation_id=operation.id, artifact_id=artifact.id)
