from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..candidates.models import Candidate
from ..projects.models import Project
from ..targets.models import Target
from ..workflows.models import WorkflowRun
from .models import MigrationRun, Operation


class PlatformRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_operations(
        self,
        after: tuple[datetime, uuid.UUID] | None,
        limit: int,
        *,
        project_ids: list[uuid.UUID] | None = None,
        include_projectless: bool = False,
        created_by: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        kind: str | None = None,
        status: str | None = None,
        since: datetime | None = None,
    ) -> list[Operation]:
        """Newest first, keyset-paged on (created_at, id).

        `project_ids` is the visibility fence, not a filter: None means "no fence"
        (administrators), and a list means "only these". `include_projectless` is
        separate because a platform-level operation belongs to no project and is
        therefore invisible to everyone except an administrator - a fence expressed
        only as a list of project ids would silently let those through.

        The keyset predicate is spelled out as an OR rather than a row-value
        comparison so it behaves the same on PostgreSQL and on the SQLite the tests
        use; the two differ on row-value support, and a wrong page boundary only
        shows up once the table is long.
        """
        query = select(Operation)
        if project_ids is not None:
            fence = Operation.project_id.in_(project_ids)
            query = query.where(or_(fence, Operation.project_id.is_(None)) if include_projectless else fence)
        if created_by is not None:
            query = query.where(Operation.created_by == created_by)
        if project_id is not None:
            query = query.where(Operation.project_id == project_id)
        if kind:
            query = query.where(Operation.kind == kind)
        if status:
            query = query.where(Operation.status == status)
        if since is not None:
            query = query.where(Operation.created_at >= since)
        if after is not None:
            moment, last_id = after
            query = query.where(
                or_(
                    Operation.created_at < moment,
                    and_(Operation.created_at == moment, Operation.id < last_id),
                )
            )
        return list(
            self.session.scalars(
                query.order_by(Operation.created_at.desc(), Operation.id.desc()).limit(limit + 1)
            )
        )

    def list_migration_runs(self, after: uuid.UUID | None, limit: int) -> list[MigrationRun]:
        query = select(MigrationRun)
        if after:
            query = query.where(MigrationRun.id > after)
        return list(self.session.scalars(query.order_by(MigrationRun.id).limit(limit + 1)))

    def resolve_legacy_id(self, entity_type: str, legacy_id: str) -> Any | None:
        models: dict[str, Any] = {
            "artifacts": Artifact,
            "candidates": Candidate,
            "projects": Project,
            "targets": Target,
            "workflow-runs": WorkflowRun,
        }
        model = models.get(entity_type)
        if model is None:
            return None
        return self.session.scalar(select(model).where(model.legacy_id == legacy_id))

    def ping(self) -> None:
        self.session.execute(text("SELECT 1"))
