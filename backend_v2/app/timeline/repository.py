from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .models import ProjectTimelineEntry


class TimelineRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_project(
        self,
        project_id: uuid.UUID,
        after: tuple[datetime, uuid.UUID] | None,
        limit: int,
        entry_type: str | None = None,
        phase: str | None = None,
        outcome: str | None = None,
    ) -> list[ProjectTimelineEntry]:
        """Chronological (oldest first), keyset-paged on (occurred_at, id).

        The keyset predicate is written as an explicit OR rather than a row-value
        comparison so it behaves identically on PostgreSQL and on the SQLite used by the
        tests; row-value support differs between them and a silently wrong page boundary
        is exactly the kind of bug that only shows up once a timeline is long.
        """
        query = select(ProjectTimelineEntry).where(ProjectTimelineEntry.project_id == project_id)
        if entry_type:
            query = query.where(ProjectTimelineEntry.entry_type == entry_type)
        if phase:
            query = query.where(ProjectTimelineEntry.phase == phase)
        if outcome:
            query = query.where(ProjectTimelineEntry.outcome == outcome)
        if after is not None:
            moment, last_id = after
            query = query.where(
                or_(
                    ProjectTimelineEntry.occurred_at > moment,
                    and_(
                        ProjectTimelineEntry.occurred_at == moment,
                        ProjectTimelineEntry.id > last_id,
                    ),
                )
            )
        query = query.order_by(ProjectTimelineEntry.occurred_at, ProjectTimelineEntry.id)
        return list(self.session.scalars(query.limit(limit + 1)))

    def get(self, entry_id: uuid.UUID) -> ProjectTimelineEntry | None:
        return self.session.get(ProjectTimelineEntry, entry_id)

    def find_by_decision_ref(self, project_id: uuid.UUID, decision_ref: str) -> ProjectTimelineEntry | None:
        """The one row that records a numbered decision, if it exists yet."""
        return self.session.scalar(
            select(ProjectTimelineEntry).where(
                ProjectTimelineEntry.project_id == project_id,
                ProjectTimelineEntry.decision_ref == decision_ref,
            )
        )
