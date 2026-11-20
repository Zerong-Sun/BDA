from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    AutopilotCampaign,
    AutopilotDraft,
    AutopilotLedgerEntry,
    AutopilotServicePrincipal,
    AutopilotStage,
    BudgetReservation,
    CampaignBudget,
)


class AutopilotRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def draft(self, draft_id: uuid.UUID) -> AutopilotDraft | None:
        return self.session.get(AutopilotDraft, draft_id)

    def campaign(self, campaign_id: uuid.UUID) -> AutopilotCampaign | None:
        return self.session.get(AutopilotCampaign, campaign_id)

    def campaign_for_update(self, campaign_id: uuid.UUID) -> AutopilotCampaign | None:
        return self.session.scalar(
            select(AutopilotCampaign).where(AutopilotCampaign.id == campaign_id).with_for_update()
        )

    def budget(self, campaign_id: uuid.UUID, *, for_update: bool = False) -> CampaignBudget | None:
        statement = select(CampaignBudget).where(CampaignBudget.campaign_id == campaign_id)
        return self.session.scalar(statement.with_for_update() if for_update else statement)

    def reservation_by_key(self, campaign_id: uuid.UUID, idempotency_key: str) -> BudgetReservation | None:
        return self.session.scalar(
            select(BudgetReservation).where(
                BudgetReservation.campaign_id == campaign_id,
                BudgetReservation.idempotency_key == idempotency_key,
            )
        )

    def reservation_for_operation(self, campaign_id: uuid.UUID, operation_id: uuid.UUID) -> BudgetReservation | None:
        return self.session.scalar(
            select(BudgetReservation).where(
                BudgetReservation.campaign_id == campaign_id,
                BudgetReservation.operation_id == operation_id,
            )
        )

    def reservation_for_update(self, campaign_id: uuid.UUID, reservation_id: uuid.UUID) -> BudgetReservation | None:
        return self.session.scalar(
            select(BudgetReservation)
            .where(
                BudgetReservation.campaign_id == campaign_id,
                BudgetReservation.id == reservation_id,
            )
            .with_for_update()
        )

    def open_reservations_for_update(self, campaign_id: uuid.UUID) -> list[BudgetReservation]:
        return list(
            self.session.scalars(
                select(BudgetReservation)
                .where(
                    BudgetReservation.campaign_id == campaign_id,
                    BudgetReservation.status.in_(["reserved", "dispatched"]),
                )
                .with_for_update()
            )
        )

    def ledger_entries(self, campaign_id: uuid.UUID, event_type: str) -> list[AutopilotLedgerEntry]:
        return list(
            self.session.scalars(
                select(AutopilotLedgerEntry).where(
                    AutopilotLedgerEntry.campaign_id == campaign_id,
                    AutopilotLedgerEntry.event_type == event_type,
                )
            )
        )

    def stage(self, stage_id: uuid.UUID) -> AutopilotStage | None:
        return self.session.get(AutopilotStage, stage_id)

    def stage_for_update(self, stage_id: uuid.UUID) -> AutopilotStage | None:
        return self.session.scalar(
            select(AutopilotStage)
            .where(AutopilotStage.id == stage_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def stages(self, campaign_id: uuid.UUID, *, resource_type: str | None = None) -> list[AutopilotStage]:
        statement = select(AutopilotStage).where(AutopilotStage.campaign_id == campaign_id)
        if resource_type is not None:
            statement = statement.where(AutopilotStage.resource_type == resource_type)
        return list(self.session.scalars(statement))

    def first_stage_with_status(self, campaign_id: uuid.UUID, statuses: Iterable[str]) -> AutopilotStage | None:
        return self.session.scalar(
            select(AutopilotStage)
            .where(
                AutopilotStage.campaign_id == campaign_id,
                AutopilotStage.status.in_(list(statuses)),
            )
            .order_by(AutopilotStage.position)
            .limit(1)
        )

    def stage_in_flight(self, campaign_id: uuid.UUID) -> AutopilotStage | None:
        return self.session.scalar(
            select(AutopilotStage).where(
                AutopilotStage.campaign_id == campaign_id,
                AutopilotStage.status == "ready",
            )
        )

    def stages_for_resource(self, resource_type: str, resource_id: uuid.UUID) -> list[AutopilotStage]:
        return list(
            self.session.scalars(
                select(AutopilotStage).where(
                    AutopilotStage.resource_type == resource_type,
                    AutopilotStage.resource_id == resource_id,
                )
            )
        )

    def service_principal(self, principal_id: uuid.UUID) -> AutopilotServicePrincipal | None:
        return self.session.get(AutopilotServicePrincipal, principal_id)

    def service_principal_named(self, name: str) -> AutopilotServicePrincipal | None:
        return self.session.scalar(select(AutopilotServicePrincipal).where(AutopilotServicePrincipal.name == name))
