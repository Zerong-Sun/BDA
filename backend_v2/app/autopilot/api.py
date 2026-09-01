from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.etag import etag, parse_if_match
from ..identity.deps import current_user
from ..identity.models import User
from ..projects.service import require_project_permission
from .schemas import (
    AutopilotCampaignResponse,
    AutopilotConfirm,
    AutopilotDraftCreate,
    AutopilotDraftResponse,
    AutopilotOperationAccepted,
    AutopilotStart,
)
from .service import (
    cancel_campaign,
    confirm_draft,
    create_draft,
    require_campaign,
    require_draft,
    start_campaign,
)

router = APIRouter(tags=["autopilot"])


@router.post(
    "/autopilot-drafts",
    response_model=AutopilotDraftResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "autopilot.draft.create"},
)
def post_draft(
    payload: AutopilotDraftCreate,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> AutopilotDraftResponse:
    require_project_permission(session, payload.project_id, user, "autopilot")
    draft = create_draft(session, payload, user)
    response.headers["ETag"] = etag(draft.version)
    return AutopilotDraftResponse.model_validate(draft)


@router.get("/autopilot-drafts/{draft_id}", response_model=AutopilotDraftResponse)
def get_draft(
    draft_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> AutopilotDraftResponse:
    draft = require_draft(session, draft_id)
    require_project_permission(session, draft.project_id, user, "read")
    response.headers["ETag"] = etag(draft.version)
    return AutopilotDraftResponse.model_validate(draft)


@router.post(
    "/autopilot-drafts/{draft_id}/confirm",
    response_model=AutopilotCampaignResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "autopilot.campaign.confirm"},
)
def post_confirm(
    draft_id: uuid.UUID,
    payload: AutopilotConfirm,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> AutopilotCampaignResponse:
    draft = require_draft(session, draft_id)
    require_project_permission(session, draft.project_id, user, "autopilot")
    campaign = confirm_draft(session, draft, payload, user, parse_if_match(if_match))
    response.headers["ETag"] = etag(campaign.version)
    return AutopilotCampaignResponse.model_validate(campaign)


@router.get("/autopilot-campaigns/{campaign_id}", response_model=AutopilotCampaignResponse)
def get_campaign(
    campaign_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> AutopilotCampaignResponse:
    campaign = require_campaign(session, campaign_id)
    require_project_permission(session, campaign.project_id, user, "read")
    response.headers["ETag"] = etag(campaign.version)
    return AutopilotCampaignResponse.model_validate(campaign)


@router.post(
    "/autopilot-campaigns/{campaign_id}/start",
    response_model=AutopilotOperationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "autopilot.campaign.start"},
)
def post_start(
    campaign_id: uuid.UUID,
    payload: AutopilotStart,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> AutopilotOperationAccepted:
    campaign = require_campaign(session, campaign_id)
    require_project_permission(session, campaign.project_id, user, "autopilot")
    operation = start_campaign(session, campaign, payload, user)
    return AutopilotOperationAccepted(campaign_id=campaign.id, operation_id=operation.id, status=operation.status)


@router.post(
    "/autopilot-campaigns/{campaign_id}/cancel",
    response_model=AutopilotOperationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "autopilot.campaign.cancel"},
)
def post_cancel(
    campaign_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> AutopilotOperationAccepted:
    campaign = require_campaign(session, campaign_id)
    require_project_permission(session, campaign.project_id, user, "autopilot")
    operation = cancel_campaign(session, campaign, user)
    return AutopilotOperationAccepted(campaign_id=campaign.id, operation_id=operation.id, status=operation.status)
