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
    AutopilotStageResponse,
    AutopilotStart,
)
from .service import (
    cancel_campaign,
    confirm_draft,
    create_draft,
    release_stage,
    require_campaign,
    require_draft,
    require_stage,
    start_campaign,
    take_over_campaign,
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


@router.post(
    "/autopilot-campaigns/{campaign_id}/takeover",
    response_model=AutopilotCampaignResponse,
    openapi_extra={"x-permission": "autopilot.campaign.takeover"},
)
def post_takeover(
    campaign_id: uuid.UUID,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> AutopilotCampaignResponse:
    """Take authority over a running campaign's products.

    `If-Match` is required for the same reason every other mutation here requires it: two
    people taking over the same campaign from two stale tabs must not both believe they
    did. The protocol stays frozen; what moves is who may edit the runs and candidates
    the stages produced.
    """
    campaign = require_campaign(session, campaign_id)
    require_project_permission(session, campaign.project_id, user, "autopilot")
    take_over_campaign(session, campaign, parse_if_match(if_match), user)
    response.headers["ETag"] = etag(campaign.version)
    return AutopilotCampaignResponse.model_validate(campaign)


@router.post(
    "/autopilot-campaigns/{campaign_id}/stages/{stage_id}/release",
    response_model=AutopilotStageResponse,
    openapi_extra={"x-permission": "autopilot.stage.release"},
)
def post_stage_release(
    campaign_id: uuid.UUID,
    stage_id: uuid.UUID,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    # `current_user` plus the project's own `autopilot` permission, matching every other
    # route here: the permission check is where the authority actually lives.
    user: User = Depends(current_user),
) -> AutopilotStageResponse:
    """Let one held stage act.

    Per stage rather than per campaign, which is the whole point: `autonomy` is a dial with
    two positions, and a supervised campaign that asks about everything trains the reviewer
    to approve without reading. What needs a person is decided by what the step does - see
    `gates.py` - so the approval is granted where that question is answerable.

    `If-Match` for the same reason every other mutation here carries it: two people
    releasing the same stage from two stale tabs must not both believe they did. The
    release is idempotent, so a retry is not a second signature.
    """
    campaign = require_campaign(session, campaign_id)
    require_project_permission(session, campaign.project_id, user, "autopilot")
    stage = require_stage(session, stage_id)
    released = release_stage(session, campaign, stage, user, parse_if_match(if_match))
    response.headers["ETag"] = etag(released.version)
    return AutopilotStageResponse.model_validate(released)
