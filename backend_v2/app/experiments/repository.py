from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ExperimentResult


class ExperimentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, result_id: uuid.UUID) -> ExperimentResult | None:
        return self.session.get(ExperimentResult, result_id)

    def list_project(self, project_id: uuid.UUID, *, after: uuid.UUID | None, limit: int) -> list[ExperimentResult]:
        query = select(ExperimentResult).where(ExperimentResult.project_id == project_id)
        if after:
            query = query.where(ExperimentResult.id > after)
        return list(self.session.scalars(query.order_by(ExperimentResult.id).limit(limit + 1)))
