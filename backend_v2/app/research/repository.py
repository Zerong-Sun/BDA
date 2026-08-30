from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ResearchBrief, ResearchFinding


class ResearchRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def brief(self, brief_id: uuid.UUID) -> ResearchBrief | None:
        return self.session.get(ResearchBrief, brief_id)

    def finding(self, finding_id: uuid.UUID) -> ResearchFinding | None:
        return self.session.get(ResearchFinding, finding_id)

    def list_briefs(self, project_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[ResearchBrief]:
        query = select(ResearchBrief).where(ResearchBrief.project_id == project_id)
        if after:
            query = query.where(ResearchBrief.id > after)
        return list(self.session.scalars(query.order_by(ResearchBrief.id).limit(limit + 1)))

    def list_findings(self, project_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[ResearchFinding]:
        query = select(ResearchFinding).where(ResearchFinding.project_id == project_id)
        if after:
            query = query.where(ResearchFinding.id > after)
        return list(self.session.scalars(query.order_by(ResearchFinding.id).limit(limit + 1)))

    def overview(self, project_id: uuid.UUID) -> tuple[list[ResearchBrief], list[ResearchFinding]]:
        briefs = list(self.session.scalars(select(ResearchBrief).where(ResearchBrief.project_id == project_id)))
        findings = list(self.session.scalars(select(ResearchFinding).where(ResearchFinding.project_id == project_id)))
        return briefs, findings
