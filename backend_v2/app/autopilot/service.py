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
from ..copilot.models import CopilotAgentRun
from ..core import review
from ..core.problem import DomainError
from ..identity.models import User
from ..platform.models import Operation
from ..platform.operations import enqueue_operation
from ..projects.models import Project
from ..research.models import ResearchGeneration
from . import gates, operators
from .models import (
    AutopilotCampaign,
    AutopilotDraft,
    AutopilotLedgerEntry,
    AutopilotServicePrincipal,
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
                # Frozen for the same reason. Who carries a stage is part of the protocol
                # a person approved, not a lookup done later against whatever the roster
                # happens to say by then.
                operator=operators.operator_for(key),
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
        if stage.resource_type == "copilot_agent_run" and stage.resource_id:
            # An agent run left alive is the one stage resource that keeps *spending*
            # after the campaign is cancelled - `agent_runs.cancel` says it outright:
            # a cancelled parent leaving GPU jobs running and subagents thinking is how
            # a budget disappears without anyone deciding to spend it. A workflow run is
            # a draft that costs nothing and may still be wanted, which is why the two
            # resource types are treated differently here rather than uniformly.
            from ..copilot import agent_runs as copilot_runs

            run = session.get(CopilotAgentRun, stage.resource_id)
            if run is not None:
                copilot_runs.cancel(session, run, reason="autopilot campaign cancelled")
            # ...and then the stage says so. Leaving it `ready` beside a cancelled run
            # would be the page reporting work that is no longer happening.
            if stage.status not in {"succeeded", "failed", "cancelled"}:
                stage.status = "cancelled"
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
    stopped = _stop_operators(session, campaign, reason="autopilot campaign taken over")
    session.add(
        AutopilotLedgerEntry(
            campaign_id=campaign.id,
            writer_user_id=user.id,
            event_type="campaign.takeover",
            # What the handover actually stopped, signed by the person who asked
            # for it. A takeover that quietly cancelled work would be a worse
            # record than one that never mentioned the work at all.
            payload={"taken_over_by": str(user.id), "operators_stopped": stopped},
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
    reason = gates.explain(stage.stage_key)
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
                "reason": reason,
            },
        )
    )
    # Releasing has to *do* something. Recording the signature and leaving the stage in
    # `awaiting_release` would be a gate with no other side: the campaign would sit there
    # for ever and the approval would have bought nothing.
    resource = activate_stage(session, campaign, stage)
    if resource is not None:
        session.add(
            AutopilotLedgerEntry(
                campaign_id=campaign.id,
                # Signed by the person, not the worker principal: this row exists because
                # they released it, and "who caused this run" is the question it answers.
                writer_user_id=user.id,
                event_type="stage.resource_created",
                payload={
                    "stage_id": str(stage.id),
                    "resource_type": resource[0],
                    "resource_id": str(resource[1]),
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


def _stop_operators(
    session: Session, campaign: AutopilotCampaign, *, reason: str
) -> list[str]:
    """Stop any agent run this campaign's stages are still carrying.

    Takeover deliberately leaves the products alone - what changes hands is
    authority over the runs, jobs and candidates the stages created, and a
    compute job left running keeps GPU hours somebody already paid for. An agent
    run is the one product where that reasoning inverts: it is not a *result*
    sitting there, it is an operator still thinking and still writing through its
    own tools. Leaving it alive is the race takeover exists to prevent, one level
    down - the worker moving on while a person corrects the step before it.

    So: jobs keep running, operators stop. Cheap to restart, and the person now
    holds the campaign.

    Returns the stage keys it stopped, for the ledger.
    """
    from ..copilot import agent_runs as copilot_runs

    stopped: list[str] = []
    stages = session.scalars(
        select(AutopilotStage).where(
            AutopilotStage.campaign_id == campaign.id,
            AutopilotStage.resource_type == "copilot_agent_run",
        )
    )
    for stage in stages:
        if stage.resource_id is None:
            continue
        run = session.get(CopilotAgentRun, stage.resource_id)
        if run is None:
            continue
        if copilot_runs.cancel(session, run, reason=reason):
            stopped.append(stage.stage_key)
    return stopped


def require_stage(session: Session, stage_id: uuid.UUID) -> AutopilotStage:
    stage = session.get(AutopilotStage, stage_id)
    if stage is None:
        raise DomainError("autopilot_stage_not_found", "Autopilot stage was not found", status_code=404)
    return stage


#: Stage statuses that have not yet acted. `execute_campaign` looks at the frontmost of
#: these rather than at `pending` alone: a held stage sits in `awaiting_release`, and a
#: query that skipped it would advance to the stage *behind* the gate on the next
#: redelivery - walking past the exact thing the gate exists to stop.
UNSTARTED_STAGE_STATUSES = ("pending", "awaiting_release")

#: A stage that has finished, one way or the other. Nothing restarts one, and
#: `advance_campaign` steps over them looking for the next thing to do.
SETTLED_STAGE_STATUSES = ("succeeded", "failed", "cancelled")

#: Stage products that end their own stage, so a person must not also end it.
#:
#: Only the agent run does. A `workflow_run` is the opposite case and the
#: distinction matters: its adapter deliberately creates a *draft* for somebody
#: to open in the Workflow page and finish, so it is a product handed over rather
#: than a product that reports back. Refusing completion for every product - the
#: first version of this rule - left a `compute` stage with no way to end at all,
#: which is the same dead end `review` had one stage earlier.
SELF_SETTLING_RESOURCE_TYPES = frozenset({"copilot_agent_run"})


def settle_stage(
    session: Session,
    campaign: AutopilotCampaign,
    stage: AutopilotStage,
    *,
    status: str,
    user: User | None = None,
) -> AutopilotStage:
    """Record that a stage's product reached a terminal state.

    Before this, a stage went `pending` -> `ready` and stopped. Nothing ever
    wrote `succeeded`, so the Autopilot page reported "ready" for ever after the
    work was done and the campaign had no way to know a step was over - the one
    half of the loop that was missing was not the advancing, it was the knowing.

    Idempotent and one-way: a settled stage is not re-settled, because the second
    write would be a second answer to "how did this step end" and the ledger
    would carry both.
    """
    if status not in SETTLED_STAGE_STATUSES:
        raise DomainError(
            "autopilot_stage_bad_terminal_status",
            f"A stage settles as one of {', '.join(SETTLED_STAGE_STATUSES)}",
            status_code=422,
        )
    if stage.status in SETTLED_STAGE_STATUSES:
        return stage
    stage.status = status
    stage.version += 1
    session.add(
        AutopilotLedgerEntry(
            campaign_id=campaign.id,
            # Signed by the person when a person did it, and by the principal
            # when the platform did. "Who caused this" has to stay answerable,
            # and a human step marked complete by a worker id reads as automatic
            # work that never happened.
            writer_user_id=user.id if user is not None else None,
            service_principal_id=None if user is not None else _worker_principal_id(session),
            event_type="stage.settled",
            payload={
                "stage_id": str(stage.id),
                "stage_key": stage.stage_key,
                "status": status,
                "operator": stage.operator,
                "by": "user" if user is not None else "worker",
            },
        )
    )
    return stage


def complete_stage(
    session: Session,
    campaign: AutopilotCampaign,
    stage: AutopilotStage,
    expected_version: int,
    user: User,
) -> AutopilotStage:
    """A person marks a human step done, and the chain continues.

    Some stages have no automatic product on purpose - `review` is somebody's
    judgement, and `operators.UNSTAFFED` records which keys are in that state and
    why. Those stages reach `ready` and nothing moves them: `release` refuses
    anything that is not held, so until now a chain that reached one stopped
    there with no action available anywhere. The default campaign ends with
    `review`, so that was every default campaign.

    Refused only for a product that ends its own stage - an agent run. A
    `workflow_run` is the opposite: its adapter creates a *draft* for somebody to
    open in the Workflow page and finish, so the person who finished it is the
    one who can say the step is over. Refusing every product, which is what this
    rule said first, left a `compute` stage unfinishable and reproduced the dead
    end `review` had one stage earlier.
    """
    if stage.version != expected_version:
        raise DomainError("version_conflict", "Autopilot stage changed", status_code=412)
    if stage.campaign_id != campaign.id:
        raise DomainError(
            "autopilot_stage_not_found", "Stage does not belong to this campaign", status_code=404
        )
    if campaign.status in {"cancelled", "manual_takeover"}:
        raise DomainError(
            "autopilot_campaign_not_running",
            f"A {campaign.status} campaign has no stage to complete",
            status_code=409,
        )
    if stage.resource_type in SELF_SETTLING_RESOURCE_TYPES:
        raise DomainError(
            "autopilot_stage_has_a_product",
            f"Stage {stage.stage_key!r} produced a {stage.resource_type}, which settles it",
            status_code=409,
        )
    if stage.held:
        raise DomainError(
            "autopilot_stage_held",
            f"Stage {stage.stage_key!r} is held; release it rather than completing it",
            status_code=409,
        )
    if stage.status in SETTLED_STAGE_STATUSES:
        return stage
    if stage.status != "ready":
        raise DomainError(
            "autopilot_stage_not_started",
            f"Stage {stage.stage_key!r} has not started; there is nothing to complete",
            status_code=409,
        )

    settle_stage(session, campaign, stage, status="succeeded", user=user)
    record_audit(
        session,
        action="autopilot.stage.complete",
        entity_type="autopilot_stage",
        entity_id=stage.id,
        project_id=campaign.project_id,
        actor_id=user.id,
        payload={"stage_key": stage.stage_key},
    )
    _advance_and_record(session, campaign, stage, user=user)
    return stage


def _advance_and_record(
    session: Session,
    campaign: AutopilotCampaign,
    from_stage: AutopilotStage,
    *,
    user: User | None = None,
) -> AutopilotStage | None:
    """Move to the next stage and write down where it got to.

    Shared by the worker and by a person completing a human step, so the two
    cannot disagree about what advancing writes - the ledger is the thing anyone
    reconstructing a campaign reads, and two shapes of "advanced" entry would
    make it answer differently depending on who caused the step.
    """
    principal = None if user is not None else _worker_principal_id(session)
    reached, resource = advance_campaign(session, campaign)
    if reached is None:
        finish_campaign(session, campaign, user=user)
        return None
    session.add(
        AutopilotLedgerEntry(
            campaign_id=campaign.id,
            writer_user_id=user.id if user is not None else None,
            service_principal_id=principal,
            event_type="campaign.advanced",
            payload={
                "from_stage_id": str(from_stage.id),
                "stage_id": str(reached.id),
                "stage_key": reached.stage_key,
                "held": bool(reached.held),
                "hold_reason": reached.hold_reason,
            },
        )
    )
    if resource is not None:
        session.add(
            AutopilotLedgerEntry(
                campaign_id=campaign.id,
                writer_user_id=user.id if user is not None else None,
                service_principal_id=principal,
                event_type="stage.resource_created",
                payload={
                    "stage_id": str(reached.id),
                    "resource_type": resource[0],
                    "resource_id": str(resource[1]),
                },
            )
        )
    return reached


def finish_campaign(
    session: Session, campaign: AutopilotCampaign, *, user: User | None = None
) -> AutopilotCampaign:
    """Mark a campaign whose chain has run out of stages.

    A campaign stayed `running` after its last stage, because nothing ever
    advanced and so nothing ever reached the end. Now that the chain moves, a
    campaign that finished has to say so: "running" on a campaign with every
    stage settled is a status that means nothing and a page that invites someone
    to wait for a step that will not come.

    `failed` when any stage failed. The campaign's outcome is not the last
    stage's - a chain that lost a step in the middle and carried on did not
    succeed - and reporting otherwise would make the ledger the only place the
    failure survived.
    """
    if campaign.status in {"cancelled", "manual_takeover"}:
        return campaign
    stages = list(
        session.scalars(select(AutopilotStage).where(AutopilotStage.campaign_id == campaign.id))
    )
    if any(stage.status not in SETTLED_STAGE_STATUSES for stage in stages):
        return campaign
    outcome = "failed" if any(stage.status == "failed" for stage in stages) else "succeeded"
    if campaign.status == outcome:
        return campaign
    campaign.status = outcome
    campaign.version += 1
    session.add(
        AutopilotLedgerEntry(
            campaign_id=campaign.id,
            writer_user_id=user.id if user is not None else None,
            service_principal_id=None if user is not None else _worker_principal_id(session),
            event_type="campaign.finished",
            payload={"status": outcome, "stages": len(stages)},
        )
    )
    return campaign


def next_stage(session: Session, campaign: AutopilotCampaign) -> AutopilotStage | None:
    """The frontmost stage that has not acted.

    Deliberately not "the first `pending` one": a held stage sits in
    `awaiting_release`, and selecting on `pending` alone steps over the gate to
    the stage behind it. `execute_campaign` has always read it this way and this
    is that same read, shared so the two cannot drift apart.
    """
    return session.scalar(
        select(AutopilotStage)
        .where(
            AutopilotStage.campaign_id == campaign.id,
            AutopilotStage.status.in_(UNSTARTED_STAGE_STATUSES),
        )
        .order_by(AutopilotStage.position)
        .limit(1)
    )


def advance_campaign(
    session: Session, campaign: AutopilotCampaign
) -> tuple[AutopilotStage | None, tuple[str, uuid.UUID] | None]:
    """Activate the next stage, if the campaign is still the worker's to advance.

    Three refusals, and none of them is optional:

    * a **cancelled** campaign has nothing to advance to;
    * a **taken-over** campaign belongs to a person now, and advancing it is the
      exact race takeover exists to prevent - the worker moving a step on while
      someone is correcting the products of the one before it;
    * a **held** stage stops here, because `activate_stage` refuses to create its
      resource and the campaign waits for a signature. That is not a failure of
      advancing; it is advancing arriving at the gate.

    Returns the stage it reached and whatever its adapter created, so the caller
    can record both. A `None` stage means the chain is finished.
    """
    if campaign.status in {"cancelled", "manual_takeover"}:
        return None, None
    in_flight = session.scalar(
        select(AutopilotStage).where(
            AutopilotStage.campaign_id == campaign.id,
            AutopilotStage.status == "ready",
        )
    )
    if in_flight is not None:
        # A campaign runs one stage at a time - `execute_campaign` activates only
        # the frontmost - so a stage already in flight means this advance has
        # happened. Without this, a redelivered settlement advances a second
        # time: the stage it activated is `ready`, which `next_stage` does not
        # count as unstarted, so it finds the stage *after* it and starts that
        # one while the one between has not run.
        return None, None
    stage = next_stage(session, campaign)
    if stage is None:
        return None, None
    resource = activate_stage(session, campaign, stage)
    return stage, resource


def _worker_principal_id(session: Session) -> uuid.UUID:
    """The service principal a worker-written ledger row is signed by.

    A ledger entry needs an author. This one is written from a worker with no
    person behind it, so it carries the principal rather than borrowing the
    confirmer's identity - "who caused this" has to stay answerable, and
    attributing an automatic settlement to the person who confirmed the campaign
    would answer it wrongly.
    """
    principal = session.scalar(
        select(AutopilotServicePrincipal).where(
            AutopilotServicePrincipal.name == "autopilot-worker"
        )
    )
    if principal is None:
        principal = AutopilotServicePrincipal(
            name="autopilot-worker",
            allowed_actions=["campaign.execute", "campaign.cancel.reconcile"],
        )
        session.add(principal)
        session.flush()
    return principal.id


def activate_stage(
    session: Session, campaign: AutopilotCampaign, stage: AutopilotStage
) -> tuple[str, uuid.UUID] | None:
    """Make one stage act, or hold it.

    One function for both callers - the worker on dispatch and a person on release -
    because two copies of "may this stage act, and if so create its resource" is how the
    gate ends up enforced on one path and not the other. Returns the resource the adapter
    created, or None if the stage is held or has nothing to create.
    """
    from .adapters import ensure_stage_resource

    if stage.held:
        stage.status = "awaiting_release"
        return None
    stage.status = "ready"
    return ensure_stage_resource(session, campaign, stage)
