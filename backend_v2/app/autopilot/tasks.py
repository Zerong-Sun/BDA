from __future__ import annotations

import uuid

from sqlalchemy import select

from ..core.celery_app import celery_app
from ..core.database import session_scope
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

    Concrete research/compute children are created by stage-specific adapters. This task
    records the durable handoff and makes the first stage ready; it never fabricates a
    compute submission from an incomplete natural-language draft.
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
        if first is not None:
            first.status = "ready"
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
