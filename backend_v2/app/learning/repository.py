from __future__ import annotations

import uuid
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    LearningAssay,
    LearningBatch,
    LearningDataset,
    LearningDecision,
    LearningEvidence,
    LearningModel,
    LearningStudy,
)

LearningRecord = (
    LearningAssay
    | LearningStudy
    | LearningDataset
    | LearningModel
    | LearningDecision
    | LearningEvidence
    | LearningBatch
)
Record = TypeVar("Record", bound=LearningRecord)
KINDS: dict[str, type[LearningRecord]] = {
    "assays": LearningAssay,
    "studies": LearningStudy,
    "datasets": LearningDataset,
    "models": LearningModel,
    "decisions": LearningDecision,
    "evidence": LearningEvidence,
    "batches": LearningBatch,
}


class LearningRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(
        self, cls: type[Record], project_id: uuid.UUID, record_id: uuid.UUID, *, lock: bool = False
    ) -> Record | None:
        query = select(cls).where(cls.id == record_id, cls.project_id == project_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return self.session.scalar(query)

    def list(self, cls: type[Record], project_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[Record]:
        query = select(cls).where(cls.project_id == project_id).order_by(cls.id)
        if after is not None:
            query = query.where(cls.id > after)
        return list(self.session.scalars(query.limit(limit + 1)))
