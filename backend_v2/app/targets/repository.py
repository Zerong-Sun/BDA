from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Target, TargetStructureRevision


class TargetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, target_id: uuid.UUID) -> Target | None:
        return self.session.get(Target, target_id)

    def list_project(self, project_id: uuid.UUID, *, after: uuid.UUID | None = None, limit: int = 50) -> list[Target]:
        query = select(Target).where(Target.project_id == project_id)
        if after:
            query = query.where(Target.id > after)
        return list(self.session.scalars(query.order_by(Target.id).limit(limit + 1)))

    def by_project(self, project_id: uuid.UUID) -> Target | None:
        return self.session.scalar(select(Target).where(Target.project_id == project_id).order_by(Target.created_at))

    def add(self, target: Target) -> Target:
        self.session.add(target)
        self.session.flush()
        return target

    def revision(self, revision_id: uuid.UUID) -> TargetStructureRevision | None:
        return self.session.get(TargetStructureRevision, revision_id)

    def list_revisions(
        self, target_id: uuid.UUID, *, after: uuid.UUID | None, limit: int
    ) -> list[TargetStructureRevision]:
        query = select(TargetStructureRevision).where(TargetStructureRevision.target_id == target_id)
        if after:
            query = query.where(TargetStructureRevision.id > after)
        return list(self.session.scalars(query.order_by(TargetStructureRevision.id).limit(limit + 1)))

    def structure_state(
        self, target_id: uuid.UUID
    ) -> tuple[TargetStructureRevision | None, uuid.UUID | None]:
        latest = self.session.scalar(
            select(TargetStructureRevision)
            .where(TargetStructureRevision.target_id == target_id)
            .order_by(TargetStructureRevision.created_at.desc(), TargetStructureRevision.id.desc())
            .limit(1)
        )
        approved = self.session.scalar(
            select(TargetStructureRevision.id)
            .where(TargetStructureRevision.target_id == target_id, TargetStructureRevision.approved.is_(True))
            .order_by(TargetStructureRevision.updated_at.desc())
            .limit(1)
        )
        return latest, approved
