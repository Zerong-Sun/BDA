from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DesignLesson, DesignReview


class DesignMemoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: DesignReview | DesignLesson) -> None:
        self.session.add(row)
        self.session.flush()

    def lessons(self, project_id: uuid.UUID) -> list[DesignLesson]:
        return list(
            self.session.scalars(
                select(DesignLesson)
                .where(DesignLesson.project_id == project_id)
                .order_by(DesignLesson.created_at, DesignLesson.id)
            )
        )

    def lesson(self, lesson_id: uuid.UUID) -> DesignLesson | None:
        return self.session.get(DesignLesson, lesson_id)

    def is_superseded(self, lesson_id: uuid.UUID) -> bool:
        return bool(self.session.scalar(select(DesignLesson.id).where(DesignLesson.supersedes_id == lesson_id)))

    def review(self, review_id: uuid.UUID) -> DesignReview | None:
        return self.session.get(DesignReview, review_id)

    def latest_review(self, workflow_run_id: uuid.UUID) -> DesignReview | None:
        return self.session.scalar(
            select(DesignReview)
            .where(DesignReview.workflow_run_id == workflow_run_id)
            .order_by(DesignReview.created_at.desc(), DesignReview.id.desc())
            .limit(1)
        )

    def reviews(self, workflow_run_id: uuid.UUID) -> list[DesignReview]:
        return list(
            self.session.scalars(
                select(DesignReview)
                .where(DesignReview.workflow_run_id == workflow_run_id)
                .order_by(DesignReview.created_at.desc())
            )
        )
