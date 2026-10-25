from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..candidates.models import Candidate
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from ..workflows.models import WorkflowRun
from .models import Campaign, CampaignDecision, CampaignEvaluation, CampaignRound
from .repository import CampaignRepository
from .schemas import (
    CampaignCreate,
    CampaignUpdate,
    DecisionCreate,
    DecisionReview,
    DecisionUpdate,
    EvaluationCreate,
    RoundCreate,
)


def create_campaign(session: Session, project: Project, payload: CampaignCreate, user: User) -> Campaign:
    campaign = Campaign(project_id=project.id, created_by=user.id, **payload.model_dump())
    session.add(campaign)
    session.flush()
    record_audit(
        session,
        action="campaign.create",
        entity_type="campaign",
        entity_id=campaign.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return campaign


def update_campaign(campaign: Campaign, payload: CampaignUpdate, expected: int) -> Campaign:
    if campaign.version != expected:
        raise DomainError("version_conflict", "Campaign was modified by another request", status_code=412)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    campaign.version += 1
    return campaign


def create_round(session: Session, campaign: Campaign, payload: RoundCreate) -> CampaignRound:
    if payload.workflow_run_id is not None:
        workflow = session.get(WorkflowRun, payload.workflow_run_id)
        if workflow is None or workflow.project_id != campaign.project_id:
            raise DomainError("workflow_not_found", "Workflow was not found in this project", status_code=404)
    row = CampaignRound(
        campaign_id=campaign.id,
        round_number=CampaignRepository(session).next_round(campaign.id),
        **payload.model_dump(),
    )
    session.add(row)
    session.flush()
    return row


def create_evaluation(session: Session, round_: CampaignRound, payload: EvaluationCreate) -> CampaignEvaluation:
    campaign = session.get(Campaign, round_.campaign_id)
    if campaign is None:
        raise DomainError("campaign_not_found", "Campaign was not found", status_code=404)
    if payload.candidate_id is not None:
        candidate = session.get(Candidate, payload.candidate_id)
        if candidate is None or candidate.project_id != campaign.project_id:
            raise DomainError("candidate_not_found", "Candidate was not found in this project", status_code=404)
    row = CampaignEvaluation(round_id=round_.id, **payload.model_dump())
    session.add(row)
    session.flush()
    return row


def create_decision(session: Session, round_: CampaignRound, payload: DecisionCreate, user: User) -> CampaignDecision:
    row = CampaignDecision(round_id=round_.id, decided_by=user.id, **payload.model_dump())
    session.add(row)
    session.flush()
    return row


def update_decision(row: CampaignDecision, payload: DecisionUpdate, expected: int) -> CampaignDecision:
    if row.version != expected:
        raise DomainError("version_conflict", "Campaign decision was modified", status_code=412)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    row.version += 1
    return row


def review_decision(
    row: CampaignDecision, payload: DecisionReview, expected: int, user: User
) -> CampaignDecision:
    if row.version != expected:
        raise DomainError("version_conflict", "Campaign decision was modified", status_code=412)
    row.review_status = "approved" if payload.approve else "rejected"
    row.reviewed_by = user.id
    row.reviewed_at = datetime.now(UTC)
    row.version += 1
    return row


def mark_round_evaluating(round_: CampaignRound) -> CampaignRound:
    round_.status = "evaluating"
    round_.version += 1
    return round_
