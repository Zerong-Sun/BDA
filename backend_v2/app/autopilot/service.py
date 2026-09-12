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
from ..core import review
from ..core.problem import DomainError
from ..identity.models import User
from ..platform.models import Operation
from ..platform.operations import enqueue_operation
from ..projects.models import Project
from ..research.models import ResearchGeneration
from . import gates
from .models import (
    AutopilotCampaign,
    AutopilotDraft,
    AutopilotLedgerEntry,
    AutopilotStage,
    BudgetReservation,
    CampaignBudget,
)
from .schemas import AutopilotConfirm, AutopilotDraftCreate, AutopilotStart

DEFAULT_STAGE_KEYS = ["research", "plan", "compute", "review"]


def _render_brief(brief: dict) -> str:
    return "Autopilot protocol\n\n" + json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True)


def _stage_keys(spec: dict) -> list:
    declared = spec.get("stages")
    return list(declared) if declared else list(DEFAULT_STAGE_KEYS)


def _check_stage_budget(spec: dict) -> None:
    """Confirming accepts every stage at once, so the list has to be readable.

    Checked at draft creation so an over-long spec never becomes something to confirm, and
    again at confirm because that is the approval act and a draft may predate the rule -
    the same both-ends discipline `check_lane_evidence` uses on create and update.
    """
    try:
        review.check_review_budget("autopilot.stages", len(_stage_keys(spec)), unit="stages")
    except ValueError as exc:
        raise DomainError("autopilot_stage_budget_exceeded", str(exc), status_code=422) from exc


def create_draft(session: Session, payload: AutopilotDraftCreate, user: User) -> AutopilotDraft:
    brief = payload.structured_brief or {}
    prompt = payload.prompt or _render_brief(brief)
    spec = dict(brief)
    spec.setdefault("schema_version", "autopilot-spec-v1")
    _check_stage_budget(spec)
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
    _check_stage_budget(draft.normalized_spec)
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
    stage_keys = _stage_keys(campaign.frozen_spec)
    for position, stage_key in enumerate(stage_keys):
        key = str(stage_key)[:80]
        session.add(
            AutopilotStage(
                campaign_id=campaign.id,
                stage_key=key,
                position=position,
                # Frozen with the spec: the tier is part of what is being approved, so a
                # later reclassification must not re-open a confirmed campaign.
                risk_tier=gates.tier_for(key),
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
    _record_confirmation_decision(session, campaign, stage_keys, user)
    return campaign


def _record_confirmation_decision(
    session: Session,
    campaign: AutopilotCampaign,
    stage_keys: list,
    user: User,
) -> None:
    """Put the confirmation on the project's decision record, not only in the ledger.

    Confirming a campaign closes options: these stages and not others, this budget
    ceiling, this autonomy level. That is the platform's own test for what belongs on the
    decision tree - it shuts a door, it has a reviewable basis, and reopening it needs a
    new campaign rather than an edit, because the spec is frozen.

    Until now the only trace was the ledger, which answers "what did Autopilot do" for
    operations. It does not answer "why did the project go this way", so a confirmed
    campaign was invisible in the view that question is asked in, and the tree could not
    show that a branch was taken by an agent's proposal at all.

    `decided_by="agent_proposed_human_confirmed"` is the accurate reading: the spec was
    normalised from a prompt by a model, and `POST .../confirm` is a person accepting it
    under `If-Match`. `outcome="unspecified"` because confirming is not a finding - the
    campaign has not run. `lane="unspecified"` rather than `dry`: the spec may schedule
    bench stages, and asserting a half the spec does not state would be a guess.

    Written through the timeline domain's own service, per the cross-domain rule, and
    failure is not swallowed: a confirmation that silently skipped the record would
    reproduce the D080-D099 gap with a machine doing the forgetting.
    """
    from ..timeline.schemas import Alternative, TimelineEntryCreate
    from ..timeline.service import create_entry as create_timeline_entry

    project = session.get(Project, campaign.project_id)
    if project is None:  # pragma: no cover - the campaign's FK guarantees it
        return
    stages = ", ".join(str(key) for key in stage_keys)
    budget = session.scalar(select(CampaignBudget).where(CampaignBudget.campaign_id == campaign.id))
    limits = []
    if budget is not None and budget.gpu_seconds_limit is not None:
        limits.append(f"GPU {budget.gpu_seconds_limit}s")
    if budget is not None and budget.money_micros_limit is not None:
        limits.append(f"{budget.money_micros_limit} micros")
    create_timeline_entry(
        session,
        project,
        TimelineEntryCreate(
            occurred_at=datetime.now(UTC),
            entry_type="decision",
            outcome="unspecified",
            lane="unspecified",
            title=f"Autopilot campaign confirmed: {campaign.name}",
            summary=(
                f"{campaign.autonomy} autonomy over stages {stages}."
                + (f" Hard budget: {'; '.join(limits)}." if limits else " No compute budget set.")
            ),
            body=(
                "The protocol below was normalised from a prompt and frozen at "
                "confirmation; it cannot be edited afterwards, only superseded by a new "
                f"campaign.\n\nPrompt:\n{campaign.frozen_prompt}"
            ),
            # The frozen spec is addressable: it is a row, and this is the key that names
            # it. Not `external_refs` - the platform owns this one.
            provenance={"autopilot_campaign_ids": [str(campaign.id)]},
            alternatives=[
                Alternative(
                    option="Run the stages by hand",
                    rejected_because=(
                        "Confirmed as an automatic campaign instead; the spec is frozen so "
                        "budget and permission checks hold, and a person can take it back "
                        "through takeover."
                    ),
                )
            ],
            tags=["autopilot"],
        ),
        user,
        decided_by="agent_proposed_human_confirmed",
    )


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
                    ComputeRepository(session).enqueue(
                        "job.cancel",
                        job.id,
                        project_id=job.project_id,
                        payload={"job_id": str(job.id)},
                    )
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


def take_over_campaign(
    session: Session, campaign: AutopilotCampaign, expected: int, user: User
) -> AutopilotCampaign:
    """Hand authority over a campaign's products from the worker to a person.

    Three things happen together, and none of them is optional:

    * the campaign stops advancing on its own (`execute_campaign` refuses a taken-over
      campaign the same way it refuses a cancelled one);
    * who and when is recorded on the row;
    * the ledger gets an entry written by the *user*, not by the service principal, which
      is what makes "who decided this" answerable afterwards.

    The frozen spec is untouched. What changes hands is authority over the products - the
    runs, jobs and candidates the stages created - not over the protocol, which stays
    immutable because the budget and permission checks rest on it.

    Idempotent: taking over an already-taken-over campaign returns it unchanged rather
    than writing a second handover, so a double-clicked button does not produce two
    entries claiming two different people took the same thing.
    """
    if campaign.version != expected:
        raise DomainError(
            "version_conflict", "Autopilot campaign was modified by another request", status_code=412
        )
    if campaign.status == "manual_takeover":
        return campaign
    if campaign.status == "cancelled":
        raise DomainError(
            "autopilot_campaign_cancelled",
            "A cancelled campaign has nothing left to take over",
            status_code=409,
        )
    campaign.status = "manual_takeover"
    campaign.taken_over_at = datetime.now(UTC)
    campaign.taken_over_by = user.id
    campaign.version += 1
    session.add(
        AutopilotLedgerEntry(
            campaign_id=campaign.id,
            writer_user_id=user.id,
            event_type="campaign.takeover",
            payload={"taken_over_by": str(user.id)},
        )
    )
    record_audit(
        session,
        action="autopilot.campaign.takeover",
        entity_type="autopilot_campaign",
        entity_id=campaign.id,
        project_id=campaign.project_id,
        actor_id=user.id,
    )
    return campaign


def release_stage(
    session: Session,
    campaign: AutopilotCampaign,
    stage: AutopilotStage,
    user: User,
    expected_version: int,
) -> AutopilotStage:
    """Let one held stage through, on the record and signed by a person.

    Idempotent, for the reason takeover is: two release records would make "who let this
    through" unanswerable, which is the only question a release record exists to answer.

    A stage that was never held cannot be released. That is not pedantry - a release on an
    ungated stage would be a signature on something nobody was asked to approve, and it
    would make the release log read as though more had been reviewed than was.
    """
    if stage.version != expected_version:
        raise DomainError("version_conflict", "Autopilot stage changed", status_code=412)
    if stage.campaign_id != campaign.id:
        raise DomainError("autopilot_stage_not_found", "Stage does not belong to this campaign", status_code=404)
    if campaign.status in ("cancelled", "manual_takeover"):
        raise DomainError(
            "autopilot_campaign_not_running",
            f"A {campaign.status} campaign has no stage to release",
            status_code=409,
        )
    if not gates.TIERS.get(stage.risk_tier, True):
        raise DomainError(
            "autopilot_stage_not_held",
            f"Stage {stage.stage_key!r} is not held; there is nothing to release",
            status_code=409,
        )
    if stage.released_at is not None:
        return stage
    stage.released_at = datetime.now(UTC)
    stage.released_by = user.id
    stage.version += 1
    session.add(
        AutopilotLedgerEntry(
            campaign_id=campaign.id,
            writer_user_id=user.id,
            event_type="stage.released",
            payload={
                "stage_id": str(stage.id),
                "stage_key": stage.stage_key,
                "risk_tier": stage.risk_tier,
                "reason": gates.explain(stage.stage_key),
            },
        )
    )
    record_audit(
        session,
        action="autopilot.stage.release",
        entity_type="autopilot_stage",
        entity_id=stage.id,
        project_id=campaign.project_id,
        actor_id=user.id,
        payload={"stage_key": stage.stage_key, "risk_tier": stage.risk_tier},
    )
    return stage


def require_stage(session: Session, stage_id: uuid.UUID) -> AutopilotStage:
    stage = session.get(AutopilotStage, stage_id)
    if stage is None:
        raise DomainError("autopilot_stage_not_found", "Autopilot stage was not found", status_code=404)
    return stage
