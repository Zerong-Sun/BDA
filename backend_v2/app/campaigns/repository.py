from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Campaign, CampaignDecision, CampaignEvaluation, CampaignRound


class CampaignRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, campaign_id: uuid.UUID) -> Campaign | None:
        return self.session.get(Campaign, campaign_id)

    def list_project(self, project_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[Campaign]:
        query = select(Campaign).where(Campaign.project_id == project_id)
        if after:
            query = query.where(Campaign.id > after)
        return list(self.session.scalars(query.order_by(Campaign.id).limit(limit + 1)))

    def next_round(self, campaign_id: uuid.UUID) -> int:
        return (
            self.session.scalar(
                select(func.max(CampaignRound.round_number)).where(CampaignRound.campaign_id == campaign_id)
            )
            or 0
        ) + 1

    def round(self, round_id: uuid.UUID) -> CampaignRound | None:
        return self.session.get(CampaignRound, round_id)

    def list_rounds(self, campaign_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[CampaignRound]:
        query = select(CampaignRound).where(CampaignRound.campaign_id == campaign_id)
        if after:
            query = query.where(CampaignRound.id > after)
        return list(self.session.scalars(query.order_by(CampaignRound.id).limit(limit + 1)))

    def evaluation(self, evaluation_id: uuid.UUID) -> CampaignEvaluation | None:
        return self.session.get(CampaignEvaluation, evaluation_id)

    def list_evaluations(
        self, round_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[CampaignEvaluation]:
        query = select(CampaignEvaluation).where(CampaignEvaluation.round_id == round_id)
        if after:
            query = query.where(CampaignEvaluation.id > after)
        return list(self.session.scalars(query.order_by(CampaignEvaluation.id).limit(limit + 1)))

    def decision(self, decision_id: uuid.UUID) -> CampaignDecision | None:
        return self.session.get(CampaignDecision, decision_id)

    def list_decisions(
        self, round_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[CampaignDecision]:
        query = select(CampaignDecision).where(CampaignDecision.round_id == round_id)
        if after:
            query = query.where(CampaignDecision.id > after)
        return list(self.session.scalars(query.order_by(CampaignDecision.id).limit(limit + 1)))
