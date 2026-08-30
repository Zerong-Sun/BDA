from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import WorkflowNode, WorkflowRun


class WorkflowRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, workflow: WorkflowRun) -> WorkflowRun:
        self.session.add(workflow)
        self.session.flush()
        return workflow

    def get(self, workflow_id: uuid.UUID) -> WorkflowRun | None:
        return self.session.get(WorkflowRun, workflow_id)

    def list_project(self, project_id: uuid.UUID, *, after: uuid.UUID | None, limit: int) -> list[WorkflowRun]:
        query = select(WorkflowRun).where(WorkflowRun.project_id == project_id)
        if after:
            query = query.where(WorkflowRun.id > after)
        return list(self.session.scalars(query.order_by(WorkflowRun.id).limit(limit + 1)))

    def nodes(self, workflow_id: uuid.UUID) -> list[WorkflowNode]:
        return list(self.session.scalars(select(WorkflowNode).where(WorkflowNode.workflow_run_id == workflow_id)))

    def node(self, node_id: uuid.UUID) -> WorkflowNode | None:
        return self.session.get(WorkflowNode, node_id)
