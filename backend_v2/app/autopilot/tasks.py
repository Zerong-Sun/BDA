from __future__ import annotations

import uuid

from sqlalchemy import select

from ..core.celery_app import celery_app
from ..core.database import session_scope
from .adapters import ensure_stage_resource
from .models import (
    AutopilotCampaign,
    AutopilotLedgerEntry,
    AutopilotServicePrincipal,
    AutopilotStage,
    BudgetReservation,
    CampaignBudget,
)


def _worker_principal(session) -> AutopilotServicePrincipal:
    principal = session.scalar(
        select(AutopilotServicePrincipal).where(AutopilotServicePrincipal.name == "autopilot-worker")
    )
    if principal is None:
        principal = AutopilotServicePrincipal(
            name="autopilot-worker",
            allowed_actions=["campaign.execute", "campaign.cancel.reconcile"],
        )
        session.add(principal)
        session.flush()
    return principal


def _ledger_exists(session, campaign_id: uuid.UUID, event_type: str, operation_id: str) -> bool:
    entries = session.scalars(
        select(AutopilotLedgerEntry).where(
            AutopilotLedgerEntry.campaign_id == campaign_id,
            AutopilotLedgerEntry.event_type == event_type,
        )
    )
    return any(str(entry.payload.get("operation_id")) == operation_id for entry in entries)


@celery_app.task(name="bda_v2.autopilot_execute", bind=True)
def execute_campaign(self, campaign_id: str) -> dict:
    """Idempotently activate a frozen protocol after its budget reservation exists.

    The first stage is made ready and then handed to its adapter, which creates the
    object on the main trunk that the stage points at - the same `workflow_runs` row the
    canvas would create, not an Autopilot-private copy. A stage whose key has no adapter
    is left as a human step rather than being given a fabricated resource.

    Still true, and still the reason this task is careful: it never fabricates a compute
    submission from an incomplete natural-language draft. The adapter creates the run; a
    spec that names no route leaves it a draft for a person to finish.
    """
    parsed = uuid.UUID(campaign_id)
    operation_id = str(self.request.id)
    with session_scope() as session:
        campaign = session.scalar(
            select(AutopilotCampaign).where(AutopilotCampaign.id == parsed).with_for_update()
        )
        if campaign is None:
            return {"campaign_id": campaign_id, "status": "missing"}
        reservation = session.scalar(
            select(BudgetReservation).where(
                BudgetReservation.campaign_id == parsed,
                BudgetReservation.operation_id == uuid.UUID(operation_id),
            )
        )
        if campaign.status == "cancelled":
            return {"campaign_id": campaign_id, "status": "cancelled"}
        if campaign.status == "manual_takeover":
            # A person holds this campaign now. Advancing it anyway is the exact race
            # takeover exists to prevent: the worker would move a stage on while someone
            # is correcting the products of the one before it.
            return {"campaign_id": campaign_id, "status": "manual_takeover"}
        if reservation is None:
            raise RuntimeError("autopilot_budget_reservation_missing")
        if _ledger_exists(session, parsed, "campaign.execution_dispatched", operation_id):
            return {"campaign_id": campaign_id, "status": campaign.status, "idempotent": True}
        reservation.status = "dispatched"
        first = session.scalar(
            select(AutopilotStage)
            .where(AutopilotStage.campaign_id == parsed, AutopilotStage.status == "pending")
            .order_by(AutopilotStage.position)
            .limit(1)
        )
        resource = None
        if first is not None:
            first.status = "ready"
            resource = ensure_stage_resource(session, campaign, first)
        principal = _worker_principal(session)
        session.add(
            AutopilotLedgerEntry(
                campaign_id=parsed,
                service_principal_id=principal.id,
                event_type="campaign.execution_dispatched",
                payload={
                    "operation_id": operation_id,
                    "reservation_id": str(reservation.id),
                    "first_stage_id": str(first.id) if first else None,
                },
            )
        )
        if first is not None and resource is not None:
            # Recorded separately from the dispatch: "budget was committed to this" and
            # "this run exists because of it" are two different questions, and the second
            # is the one someone reading the Workflow page needs answered.
            session.add(
                AutopilotLedgerEntry(
                    campaign_id=parsed,
                    service_principal_id=principal.id,
                    event_type="stage.resource_created",
                    payload={
                        "operation_id": operation_id,
                        "stage_id": str(first.id),
                        "resource_type": resource[0],
                        "resource_id": str(resource[1]),
                    },
                )
            )
    return {"campaign_id": campaign_id, "status": "running"}


@celery_app.task(name="bda_v2.autopilot_cancel", bind=True)
def reconcile_cancel(self, campaign_id: str) -> dict:
    """Release uncommitted reservations after the synchronous cancellation cascade."""
    parsed = uuid.UUID(campaign_id)
    operation_id = str(self.request.id)
    with session_scope() as session:
        campaign = session.scalar(
            select(AutopilotCampaign).where(AutopilotCampaign.id == parsed).with_for_update()
        )
        if campaign is None:
            return {"campaign_id": campaign_id, "status": "missing"}
        if _ledger_exists(session, parsed, "campaign.cancel_reconciled", operation_id):
            return {"campaign_id": campaign_id, "status": "cancelled", "idempotent": True}
        budget = session.scalar(
            select(CampaignBudget).where(CampaignBudget.campaign_id == parsed).with_for_update()
        )
        reservations = list(
            session.scalars(
                select(BudgetReservation)
                .where(
                    BudgetReservation.campaign_id == parsed,
                    BudgetReservation.status.in_(["reserved", "dispatched"]),
                )
                .with_for_update()
            )
        )
        released_gpu = sum(item.gpu_seconds for item in reservations)
        released_money = sum(item.money_micros for item in reservations)
        if budget is not None:
            budget.gpu_seconds_reserved = max(0, budget.gpu_seconds_reserved - released_gpu)
            budget.money_micros_reserved = max(0, budget.money_micros_reserved - released_money)
        for reservation in reservations:
            reservation.status = "released"
        principal = _worker_principal(session)
        session.add(
            AutopilotLedgerEntry(
                campaign_id=parsed,
                service_principal_id=principal.id,
                event_type="campaign.cancel_reconciled",
                payload={
                    "operation_id": operation_id,
                    "released_gpu_seconds": released_gpu,
                    "released_money_micros": released_money,
                },
            )
        )
    return {"campaign_id": campaign_id, "status": "cancelled", "released_gpu_seconds": released_gpu}


@celery_app.task(name="bda_v2.autopilot_settle", bind=True)
def settle_reservation(self, campaign_id: str, reservation_id: str, actual_gpu_seconds: int) -> dict:
    """Turn a reservation into committed spend, at what it actually cost.

    A reservation is a claim on the budget made *before* the work runs, so it is
    necessarily an estimate. Until it is settled, the campaign's remaining budget is
    wrong in one direction or the other: an over-estimate holds back headroom that is
    never used, and nothing anywhere records what the run really cost.

    Three properties this has to keep, each for a reason the ledger already knows about:

    * **Idempotent under redelivery.** Celery retries. Committing twice would charge a
      campaign for work it did once, and the hard-limit CHECK constraints would then
      start refusing legitimate stages.
    * **Never commits more than was reserved.** The budget's CHECK constraints are the
      real guard, but reaching them means a failed transaction and a confusing error;
      clamping and recording the overrun says the same thing readably. An actual cost
      above the reservation is a real event - the estimate was wrong - and it belongs in
      the ledger rather than in a stack trace.
    * **Leaves cancelled campaigns alone.** `reconcile_cancel` has already released those
      reservations; settling one afterwards would re-charge a campaign nobody ran.
    """
    parsed = uuid.UUID(campaign_id)
    operation_id = str(self.request.id)
    with session_scope() as session:
        campaign = session.scalar(
            select(AutopilotCampaign).where(AutopilotCampaign.id == parsed).with_for_update()
        )
        if campaign is None:
            return {"campaign_id": campaign_id, "status": "missing"}
        reservation = session.scalar(
            select(BudgetReservation)
            .where(
                BudgetReservation.campaign_id == parsed,
                BudgetReservation.id == uuid.UUID(reservation_id),
            )
            .with_for_update()
        )
        if reservation is None:
            return {"campaign_id": campaign_id, "status": "reservation_missing"}
        if reservation.status in {"released", "committed"}:
            # Already settled, or released by a cancellation. Either way there is nothing
            # left to charge, and saying so beats charging it again.
            return {"campaign_id": campaign_id, "status": reservation.status, "idempotent": True}
        budget = session.scalar(
            select(CampaignBudget).where(CampaignBudget.campaign_id == parsed).with_for_update()
        )
        actual = max(0, int(actual_gpu_seconds))
        charged = min(actual, reservation.gpu_seconds)
        overrun = actual - charged
        if budget is not None:
            budget.gpu_seconds_reserved = max(0, budget.gpu_seconds_reserved - reservation.gpu_seconds)
            budget.gpu_seconds_committed += charged
            budget.money_micros_reserved = max(0, budget.money_micros_reserved - reservation.money_micros)
            budget.money_micros_committed += reservation.money_micros
        reservation.status = "committed"
        principal = _worker_principal(session)
        session.add(
            AutopilotLedgerEntry(
                campaign_id=parsed,
                service_principal_id=principal.id,
                event_type="reservation.settled",
                payload={
                    "operation_id": operation_id,
                    "reservation_id": reservation_id,
                    "reserved_gpu_seconds": reservation.gpu_seconds,
                    "actual_gpu_seconds": actual,
                    "committed_gpu_seconds": charged,
                    # Non-zero means the estimate was too low. Recorded rather than
                    # silently clamped: it is the number that makes the next estimate
                    # better, and the one an over-budget campaign is explained by.
                    "unbilled_overrun_gpu_seconds": overrun,
                },
            )
        )
    return {
        "campaign_id": campaign_id,
        "status": "committed",
        "committed_gpu_seconds": charged,
        "unbilled_overrun_gpu_seconds": overrun,
    }
