from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import KnowledgeEntry


class KnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_project(self, project_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[KnowledgeEntry]:
        q = select(KnowledgeEntry).where(KnowledgeEntry.project_id == project_id)
        if after:
            q = q.where(KnowledgeEntry.id > after)
        return list(self.session.scalars(q.order_by(KnowledgeEntry.id).limit(limit + 1)))

    def get(self, entry_id: uuid.UUID) -> KnowledgeEntry | None:
        return self.session.get(KnowledgeEntry, entry_id)
