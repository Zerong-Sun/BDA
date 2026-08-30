from __future__ import annotations

import uuid

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from .models import Candidate, CandidateMetric


class CandidateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, candidate_id: uuid.UUID, *, for_update: bool = False) -> Candidate | None:
        if for_update:
            return self.session.scalar(
                select(Candidate)
                .where(Candidate.id == candidate_id)
                .with_for_update()
            )
        return self.session.get(Candidate, candidate_id)

    def list_project(
        self,
        project_id: uuid.UUID,
        after: uuid.UUID | None,
        limit: int,
        candidate_kind: str | None = None,
        metric_key: str | None = None,
        metric_min: float | None = None,
        metric_max: float | None = None,
        metric_method: str | None = None,
    ) -> list[Candidate]:
        query = select(Candidate).where(Candidate.project_id == project_id)
        if candidate_kind:
            query = query.where(Candidate.candidate_kind == candidate_kind)
        if metric_key:
            # EXISTS rather than a join: a candidate scored by several models must not
            # come back once per matching metric row.
            condition = and_(
                CandidateMetric.candidate_id == Candidate.id,
                CandidateMetric.metric_key == metric_key,
            )
            if metric_method:
                condition = and_(condition, CandidateMetric.method == metric_method)
            if metric_min is not None:
                condition = and_(condition, CandidateMetric.value >= metric_min)
            if metric_max is not None:
                condition = and_(condition, CandidateMetric.value <= metric_max)
            query = query.where(select(CandidateMetric.id).where(condition).exists())
        if after:
            query = query.where(Candidate.id > after)
        return list(self.session.scalars(query.order_by(Candidate.id).limit(limit + 1)))

    def metrics_for(self, candidate_id: uuid.UUID) -> list[CandidateMetric]:
        return list(
            self.session.scalars(
                select(CandidateMetric)
                .where(CandidateMetric.candidate_id == candidate_id)
                .order_by(CandidateMetric.metric_key, CandidateMetric.method, CandidateMetric.model_variant)
            )
        )
