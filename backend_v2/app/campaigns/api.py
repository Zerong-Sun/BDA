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
from ..platform.operations import enqueue_operation
from ..projects.service import require_project
from .models import CampaignDecision
from .repository import CampaignRepository
from .schemas import (
    CampaignCreate,
    CampaignPage,
    CampaignResponse,
    CampaignUpdate,
    DecisionCreate,
    DecisionPage,
    DecisionResponse,
    DecisionReview,
    DecisionUpdate,
    EvaluationCreate,
    EvaluationPage,
    EvaluationResponse,
    EvaluationRunAccepted,
    RoundCreate,
    RoundPage,
    RoundResponse,
)
from .service import (
    create_campaign,
    create_decision,
    create_evaluation,
    create_round,
    mark_round_evaluating,
    update_campaign,
    update_decision,
)
from .service import (
    review_decision as review_decision_service,
)

router = APIRouter(tags=["campaigns"])


def _campaign(session: Session, campaign_id: uuid.UUID, user: User):
    row = CampaignRepository(session).get(campaign_id)
    if row is None:
        raise DomainError("campaign_not_found", "Campaign was not found", status_code=404)
    return row, require_project(session, row.project_id, user)


@router.get("/projects/{project_id}/campaigns", response_model=CampaignPage)
def list_campaigns(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> CampaignPage:
    require_project(session, project_id, user)
    rows = CampaignRepository(session).list_project(project_id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return CampaignPage(
        items=[CampaignResponse.model_validate(x) for x in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.post(
    "/projects/{project_id}/campaigns",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "campaign.create"},
)
def post_campaign(
    project_id: uuid.UUID,
    payload: CampaignCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> CampaignResponse:
    project = require_project(session, project_id, user)
    return CampaignResponse.model_validate(create_campaign(session, project, payload, user))


@router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> CampaignResponse:
    row, _ = _campaign(session, campaign_id, user)
    response.headers["ETag"] = etag(row.version)
    return CampaignResponse.model_validate(row)


@router.patch(
    "/campaigns/{campaign_id}", response_model=CampaignResponse, openapi_extra={"x-permission": "campaign.update"}
)
def patch_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> CampaignResponse:
    row, _ = _campaign(session, campaign_id, user)
    update_campaign(row, payload, parse_if_match(if_match))
    response.headers["ETag"] = etag(row.version)
    return CampaignResponse.model_validate(row)


@router.get("/campaigns/{campaign_id}/rounds", response_model=RoundPage)
def list_rounds(
    campaign_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> RoundPage:
    row, _ = _campaign(session, campaign_id, user)
    after = decode_cursor(cursor)
    rows = CampaignRepository(session).list_rounds(row.id, after, limit)
    page = rows[:limit]
    return RoundPage(
        items=[RoundResponse.model_validate(item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.post(
    "/campaigns/{campaign_id}/rounds",
    response_model=RoundResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "campaign.round.create"},
)
def post_round(
    campaign_id: uuid.UUID,
    payload: RoundCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> RoundResponse:
    row, _ = _campaign(session, campaign_id, user)
    return RoundResponse.model_validate(create_round(session, row, payload))


def _round(session: Session, round_id: uuid.UUID, user: User):
    row = CampaignRepository(session).round(round_id)
    if row is None:
        raise DomainError("campaign_round_not_found", "Campaign round was not found", status_code=404)
    campaign, _ = _campaign(session, row.campaign_id, user)
    return row, campaign


@router.get("/campaign-rounds/{round_id}", response_model=RoundResponse)
def get_round(
    round_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> RoundResponse:
    row, _ = _round(session, round_id, user)
    response.headers["ETag"] = etag(row.version)
    return RoundResponse.model_validate(row)


@router.post(
    "/campaign-rounds/{round_id}/evaluations",
    response_model=EvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "campaign.evaluate"},
)
def post_evaluation(
    round_id: uuid.UUID,
    payload: EvaluationCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> EvaluationResponse:
    round_, _ = _round(session, round_id, user)
    return EvaluationResponse.model_validate(create_evaluation(session, round_, payload))


@router.get("/campaign-rounds/{round_id}/evaluations", response_model=EvaluationPage)
def list_evaluations(
    round_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> EvaluationPage:
    round_, _ = _round(session, round_id, user)
    after = decode_cursor(cursor)
    rows = CampaignRepository(session).list_evaluations(round_.id, after, limit)
    page = rows[:limit]
    return EvaluationPage(
        items=[EvaluationResponse.model_validate(item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get("/campaign-evaluations/{evaluation_id}", response_model=EvaluationResponse)
def get_evaluation(
    evaluation_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> EvaluationResponse:
    row = CampaignRepository(session).evaluation(evaluation_id)
    if row is None:
        raise DomainError("campaign_evaluation_not_found", "Campaign evaluation was not found", status_code=404)
    _round(session, row.round_id, user)
    response.headers["ETag"] = etag(row.version)
    return EvaluationResponse.model_validate(row)


@router.post(
    "/campaign-rounds/{round_id}/decisions",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "campaign.decide"},
)
def post_decision(
    round_id: uuid.UUID,
    payload: DecisionCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> DecisionResponse:
    round_, _ = _round(session, round_id, user)
    return DecisionResponse.model_validate(create_decision(session, round_, payload, user))


@router.get("/campaign-rounds/{round_id}/decisions", response_model=DecisionPage)
def list_decisions(
    round_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> DecisionPage:
    round_, _ = _round(session, round_id, user)
    after = decode_cursor(cursor)
    rows = CampaignRepository(session).list_decisions(round_.id, after, limit)
    page = rows[:limit]
    return DecisionPage(
        items=[DecisionResponse.model_validate(item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get("/campaign-decisions/{decision_id}", response_model=DecisionResponse)
def get_decision(
    decision_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> DecisionResponse:
    row = _decision(session, decision_id, user)
    response.headers["ETag"] = etag(row.version)
    return DecisionResponse.model_validate(row)


def _decision(session: Session, decision_id: uuid.UUID, user: User) -> CampaignDecision:
    row = CampaignRepository(session).decision(decision_id)
    if row is None:
        raise DomainError("campaign_decision_not_found", "Campaign decision was not found", status_code=404)
    _round(session, row.round_id, user)
    return row


@router.patch(
    "/campaign-decisions/{decision_id}",
    response_model=DecisionResponse,
    openapi_extra={"x-permission": "campaign.decision.update"},
)
def patch_decision(
    decision_id: uuid.UUID,
    payload: DecisionUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> DecisionResponse:
    row = _decision(session, decision_id, user)
    update_decision(row, payload, parse_if_match(if_match))
    response.headers["ETag"] = etag(row.version)
    return DecisionResponse.model_validate(row)


@router.post(
    "/campaign-decisions/{decision_id}/review",
    response_model=DecisionResponse,
    openapi_extra={"x-permission": "campaign.decision.review"},
)
def review_decision(
    decision_id: uuid.UUID,
    payload: DecisionReview,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> DecisionResponse:
    row = _decision(session, decision_id, user)
    review_decision_service(row, payload, parse_if_match(if_match), user)
    response.headers["ETag"] = etag(row.version)
    return DecisionResponse.model_validate(row)


@router.post(
    "/campaign-rounds/{round_id}/evaluation-runs",
    response_model=EvaluationRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "campaign.evaluate"},
)
def run_round_evaluation(
    round_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> EvaluationRunAccepted:
    round_, campaign = _round(session, round_id, user)
    project = require_project(session, campaign.project_id, user)
    operation = enqueue_operation(
        session,
        topic="campaign.evaluate",
        resource_type="campaign_round",
        resource_id=round_.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"round_id": str(round_.id)},
    )
    mark_round_evaluating(round_)
    return EvaluationRunAccepted(operation_id=operation.id, round_id=round_.id)
