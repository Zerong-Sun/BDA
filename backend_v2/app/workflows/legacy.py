"""Narrow, audited normalization of unsubmitted legacy drafts.

This is a maintenance service, not a runtime fallback for unknown job states.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..compute.models import Job, JobSubmission
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from .models import WorkflowNode, WorkflowRun


def normalize_legacy_draft_nodes(
    session: Session, project: Project, workflow_id: uuid.UUID, user: User, expected_version: int
) -> list[dict[str, str]]:
    """Map only the retired not_started spelling, retaining IDs and parameters.

    The caller owns authorization and transaction commit. Refuse any submitted
    workflow, even if its current status was subsequently changed to draft.
    """
    workflow = session.scalar(
        select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update().execution_options(populate_existing=True)
    )
    if workflow is None or workflow.project_id != project.id:
        raise DomainError("workflow_not_found", "Workflow was not found in this project", status_code=404)
    if workflow.version != expected_version:
        raise DomainError("version_conflict", "Workflow was modified by another request", status_code=412)
    if workflow.status != "draft":
        raise DomainError("workflow_locked", "Only an unsubmitted draft can be normalized", status_code=409)
    for model in (JobSubmission, Job):
        if session.scalar(select(model.id).where(model.workflow_run_id == workflow.id).limit(1)):
            raise DomainError("workflow_locked", "Submitted workflow history must be preserved", status_code=409)
    nodes = session.scalars(select(WorkflowNode).where(WorkflowNode.workflow_run_id == workflow.id).with_for_update()).all()
    changes = []
    for node in nodes:
        if str(node.status) != "not_started":
            continue
        changes.append({"node_id": str(node.id), "node_key": node.node_key, "before": "not_started", "after": "draft"})
        node.status = "draft"
        node.version += 1
    if changes:
        workflow.version += 1
        record_audit(
            session, action="workflow.legacy_status.normalize", entity_type="workflow_run", entity_id=workflow.id,
            project_id=project.id, organization_id=project.organization_id, actor_id=user.id,
            payload={"changes": changes, "previous_version": expected_version, "version": workflow.version},
        )
    return changes
