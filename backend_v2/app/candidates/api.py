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
from .repository import CandidateRepository
from .schemas import (
    CandidateCreate,
    CandidateMetricList,
    CandidateMetricResponse,
    CandidatePage,
    CandidateResponse,
    CandidateUpdate,
)
from .service import create_candidate, update_candidate

router = APIRouter(tags=["candidates"])


@router.get("/projects/{project_id}/candidates", response_model=CandidatePage)
def list_candidates(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    candidate_kind: str | None = Query(default=None, pattern="^(design_candidate|research_target)$"),
    metric: str | None = Query(
        default=None,
        max_length=60,
        description='Restrict to candidates carrying this metric, e.g. "plddt" or "ptm".',
    ),
    metric_min: float | None = Query(default=None, description="Lower bound on the metric, inclusive."),
    metric_max: float | None = Query(default=None, description="Upper bound on the metric, inclusive."),
    metric_method: str | None = Query(
        default=None,
        max_length=60,
        description='Restrict the metric to one producer, e.g. "alphafold2_superfold".',
    ),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> CandidatePage:
    require_project(session, project_id, user)
    if metric is None and (metric_min is not None or metric_max is not None or metric_method):
        raise DomainError(
            "invalid_metric_filter",
            "metric_min, metric_max and metric_method require metric",
            status_code=422,
        )
    rows = CandidateRepository(session).list_project(
        project_id,
        decode_cursor(cursor),
        limit,
        candidate_kind,
        metric_key=metric,
        metric_min=metric_min,
        metric_max=metric_max,
        metric_method=metric_method,
    )
    page = rows[:limit]
    return CandidatePage(
        items=[CandidateResponse.model_validate(row) for row in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.post(
    "/projects/{project_id}/candidates",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "candidate.create"},
)
def post_candidate(
    project_id: uuid.UUID,
    payload: CandidateCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> CandidateResponse:
    project = require_project(session, project_id, user)
    return CandidateResponse.model_validate(create_candidate(session, project, payload, user))


def _candidate(session: Session, candidate_id: uuid.UUID, user: User):
    candidate = CandidateRepository(session).get(candidate_id)
    if candidate is None:
        raise DomainError("candidate_not_found", "Candidate was not found", status_code=404)
    project = require_project(session, candidate.project_id, user)
    return candidate, project


@router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
def get_candidate(
    candidate_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> CandidateResponse:
    candidate, _ = _candidate(session, candidate_id, user)
    response.headers["ETag"] = etag(candidate.version)
    return CandidateResponse.model_validate(candidate)


@router.patch(
    "/candidates/{candidate_id}", response_model=CandidateResponse, openapi_extra={"x-permission": "candidate.update"}
)
def patch_candidate(
    candidate_id: uuid.UUID,
    payload: CandidateUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> CandidateResponse:
    candidate, project = _candidate(session, candidate_id, user)
    updated = update_candidate(session, project, candidate, payload, user, parse_if_match(if_match))
    response.headers["ETag"] = etag(updated.version)
    return CandidateResponse.model_validate(updated)


@router.get("/candidates/{candidate_id}/metrics", response_model=CandidateMetricList)
def list_candidate_metrics(
    candidate_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> CandidateMetricList:
    """Every metric recorded against a candidate, newest run last.

    Returned per (metric, method, model variant) rather than collapsed, because the
    spread across AlphaFold2 models is what tells a reviewer whether a confident number
    is actually agreed on.
    """
    candidate, _ = _candidate(session, candidate_id, user)
    rows = CandidateRepository(session).metrics_for(candidate.id)
    return CandidateMetricList(items=[CandidateMetricResponse.model_validate(row) for row in rows])
