from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..campaigns.models import Campaign
from ..compute.models import Job
from ..compute.repository import ComputeRepository
from ..compute.service import transition_job
from ..core.problem import DomainError
from ..identity.models import User
from ..platform.models import Operation
from ..platform.operations import enqueue_operation
from ..research.models import ResearchGeneration
from .models import (
    AutopilotCampaign,
    AutopilotDraft,
    AutopilotLedgerEntry,
    AutopilotStage,
    BudgetReservation,
    CampaignBudget,
)
from .schemas import AutopilotConfirm, AutopilotDraftCreate, AutopilotStart


def _render_brief(brief: dict) -> str:
    return "Autopilot protocol\n\n" + json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True)


def create_draft(session: Session, payload: AutopilotDraftCreate, user: User) -> AutopilotDraft:
    brief = payload.structured_brief or {}
    prompt = payload.prompt or _render_brief(brief)
    spec = dict(brief)
    spec.setdefault("schema_version", "autopilot-spec-v1")
    draft = AutopilotDraft(
        project_id=payload.project_id,
        created_by=user.id,
        prompt=prompt,
        structured_brief=brief,
        normalized_spec=spec,
    )
    session.add(draft)
    session.flush()
    record_audit(
        session,
        action="autopilot.draft.create",
        entity_type="autopilot_draft",
        entity_id=draft.id,
        project_id=draft.project_id,
        actor_id=user.id,
    )
    return draft


def require_draft(session: Session, draft_id: uuid.UUID) -> AutopilotDraft:
    draft = session.get(AutopilotDraft, draft_id)
    if draft is None:
        raise DomainError("autopilot_draft_not_found", "Autopilot draft was not found", status_code=404)
    return draft


def require_campaign(session: Session, campaign_id: uuid.UUID) -> AutopilotCampaign:
    campaign = session.get(AutopilotCampaign, campaign_id)
    if campaign is None:
        raise DomainError("autopilot_campaign_not_found", "Autopilot campaign was not found", status_code=404)
    return campaign


def confirm_draft(
    session: Session,
    draft: AutopilotDraft,
    payload: AutopilotConfirm,
    user: User,
    expected_version: int,
) -> AutopilotCampaign:
    if draft.version != expected_version:
        raise DomainError("version_conflict", "Autopilot draft changed", status_code=412)
    if draft.confirmed_campaign_id is not None:
        return require_campaign(session, draft.confirmed_campaign_id)
    if payload.manual_campaign_id is not None:
        manual = session.get(Campaign, payload.manual_campaign_id)
        if manual is None or manual.project_id != draft.project_id:
            raise DomainError("campaign_handoff_invalid", "Manual campaign must belong to this project", status_code=409)
    campaign = AutopilotCampaign(
        project_id=draft.project_id,
        draft_id=draft.id,
        created_by=user.id,
        manual_campaign_id=payload.manual_campaign_id,
        name=payload.name,
        autonomy=payload.autonomy,
        frozen_prompt=draft.prompt,
        frozen_spec=draft.normalized_spec,
    )
    session.add(campaign)
    session.flush()
    budget_input = payload.budget
    session.add(
        CampaignBudget(
            campaign_id=campaign.id,
            gpu_seconds_limit=budget_input.gpu_seconds_limit if budget_input else None,
            money_micros_limit=budget_input.money_micros_limit if budget_input else None,
        )
    )
    stage_keys = campaign.frozen_spec.get("stages") or ["research", "plan", "compute", "review"]
    for position, stage_key in enumerate(stage_keys):
        session.add(
            AutopilotStage(
                campaign_id=campaign.id,
                stage_key=str(stage_key)[:80],
                position=position,
            )
        )
    draft.status = "confirmed"
    draft.confirmed_campaign_id = campaign.id
    draft.version += 1
    session.add(
        AutopilotLedgerEntry(
            campaign_id=campaign.id,
            writer_user_id=user.id,
            event_type="campaign.confirmed",
            payload={"autonomy": campaign.autonomy},
        )
    )
    record_audit(
        session,
        action="autopilot.campaign.confirm",
        entity_type="autopilot_campaign",
        entity_id=campaign.id,
        project_id=campaign.project_id,
        actor_id=user.id,
    )
    return campaign


def _reserve_budget(
    session: Session,
    campaign: AutopilotCampaign,
    payload: AutopilotStart,
) -> BudgetReservation:
    existing = session.scalar(
        select(BudgetReservation).where(
            BudgetReservation.campaign_id == campaign.id,
            BudgetReservation.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is not None:
        if existing.gpu_seconds != payload.gpu_seconds or existing.money_micros != payload.money_micros:
            raise DomainError("idempotency_conflict", "Reservation key was reused with another budget", status_code=409)
        return existing
    budget = session.scalar(
        select(CampaignBudget).where(CampaignBudget.campaign_id == campaign.id).with_for_update()
    )
    if budget is None:
        raise DomainError("campaign_budget_missing", "Campaign budget is missing", status_code=409)
    next_gpu = budget.gpu_seconds_reserved + budget.gpu_seconds_committed + payload.gpu_seconds
    next_money = budget.money_micros_reserved + budget.money_micros_committed + payload.money_micros
    if budget.gpu_seconds_limit is not None and next_gpu > budget.gpu_seconds_limit:
        raise DomainError("campaign_budget_exceeded", "GPU budget hard limit exceeded", status_code=409)
    if budget.money_micros_limit is not None and next_money > budget.money_micros_limit:
        raise DomainError("campaign_budget_exceeded", "Money budget hard limit exceeded", status_code=409)
    budget.gpu_seconds_reserved += payload.gpu_seconds
    budget.money_micros_reserved += payload.money_micros
    reservation = BudgetReservation(
        campaign_id=campaign.id,
        idempotency_key=payload.idempotency_key,
        gpu_seconds=payload.gpu_seconds,
        money_micros=payload.money_micros,
    )
    session.add(reservation)
    session.flush()
    return reservation


def start_campaign(
    session: Session,
    campaign: AutopilotCampaign,
    payload: AutopilotStart,
    user: User,
) -> Operation:
    if campaign.autonomy == "plan_only":
        raise DomainError("plan_only_compute_forbidden", "A plan-only campaign cannot start compute", status_code=409)
    reservation = _reserve_budget(session, campaign, payload)
    if reservation.operation_id is not None:
        operation = session.get(Operation, reservation.operation_id)
        if operation is not None:
            return operation
    if campaign.status not in {"confirmed", "running"}:
        raise DomainError("autopilot_campaign_not_startable", "Campaign cannot be started", status_code=409)
    operation = enqueue_operation(
        session,
        topic="autopilot.execute",
        resource_type="autopilot_campaign",
        resource_id=campaign.id,
        project_id=campaign.project_id,
        user=user,
        payload={
            "campaign_id": str(campaign.id),
            "reservation_id": str(reservation.id),
            "idempotency_key": payload.idempotency_key,
        },
    )
    reservation.operation_id = operation.id
    campaign.status = "running"
    campaign.started_at = campaign.started_at or datetime.now(UTC)
    campaign.version += 1
    session.add(
        AutopilotLedgerEntry(
            campaign_id=campaign.id,
            writer_user_id=user.id,
            event_type="campaign.started",
            payload={"operation_id": str(operation.id), "reservation_id": str(reservation.id)},
        )
    )
    return operation


def cancel_campaign(session: Session, campaign: AutopilotCampaign, user: User) -> Operation:
    if campaign.cancel_operation_id is not None:
        existing = session.get(Operation, campaign.cancel_operation_id)
        if existing is not None:
            return existing
    operation = enqueue_operation(
        session,
        topic="autopilot.cancel",
        resource_type="autopilot_campaign",
        resource_id=campaign.id,
        project_id=campaign.project_id,
        user=user,
        payload={"campaign_id": str(campaign.id)},
    )
    campaign.cancel_operation_id = operation.id
    campaign.status = "cancelled"
    campaign.cancelled_at = campaign.cancelled_at or datetime.now(UTC)
    campaign.version += 1
    stages = list(session.scalars(select(AutopilotStage).where(AutopilotStage.campaign_id == campaign.id)))
    for stage in stages:
        if stage.status in {"pending", "running", "blocked"}:
            stage.status = "cancelled"
        if stage.operation_id:
            child_operation = session.get(Operation, stage.operation_id)
            if child_operation and child_operation.status not in {"succeeded", "failed", "cancelled"}:
                child_operation.status = "cancel_requested" if child_operation.status == "running" else "cancelled"
                child_operation.version += 1
        if stage.resource_type == "job" and stage.resource_id:
            job = session.get(Job, stage.resource_id)
            if job and job.status not in {"succeeded", "failed", "cancelled"}:
                if job.status != "cancel_requested":
                    transition_job(session, job, "cancel_requested")
                    ComputeRepository(session).enqueue("job.cancel", job.id, {"job_id": str(job.id)})
        if stage.resource_type == "research_generation" and stage.resource_id:
            generation = session.get(ResearchGeneration, stage.resource_id)
            if generation and generation.status not in {"succeeded", "failed", "cancelled"}:
                generation.status = "cancel_requested"
    session.add(
        AutopilotLedgerEntry(
            campaign_id=campaign.id,
            writer_user_id=user.id,
            event_type="campaign.cancel_requested",
            payload={"operation_id": str(operation.id)},
        )
    )
    record_audit(
        session,
        action="autopilot.campaign.cancel",
        entity_type="autopilot_campaign",
        entity_id=campaign.id,
        project_id=campaign.project_id,
        actor_id=user.id,
    )
    return operation
