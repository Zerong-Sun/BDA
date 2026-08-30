from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import LigandImport


class LigandRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, import_id: uuid.UUID) -> LigandImport | None:
        return self.session.get(LigandImport, import_id)

    def list_project(self, project_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[LigandImport]:
        query = select(LigandImport).where(LigandImport.project_id == project_id)
        if after:
            query = query.where(LigandImport.id > after)
        return list(self.session.scalars(query.order_by(LigandImport.id).limit(limit + 1)))
