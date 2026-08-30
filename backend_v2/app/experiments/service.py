from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..audit.service import record_audit
from ..candidates.models import Candidate
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from .models import ExperimentResult
from .schemas import ExperimentResultBatch


def create_results(
    session: Session,
    project: Project,
    payload: ExperimentResultBatch,
    user: User,
) -> list[ExperimentResult]:
    items = []
    for item in payload.results:
        resolved_candidate_id = item.candidate_id
        if item.candidate_id:
            candidate = session.get(Candidate, item.candidate_id)
            if candidate is None or candidate.project_id != project.id:
                raise DomainError("candidate_not_found", "Project candidate was not found", status_code=404)
        elif item.candidate_ref:
            # Resolve the human-facing reference so the result joins to the design it
            # measured. candidate_key is unique per project, so this is unambiguous.
            resolved_candidate_id = session.scalar(
                select(Candidate.id).where(
                    Candidate.project_id == project.id,
                    Candidate.candidate_key == item.candidate_ref,
                )
            )
        if item.source_artifact_id:
            artifact = session.get(Artifact, item.source_artifact_id)
            if artifact is None or artifact.project_id != project.id or artifact.status != "available":
                raise DomainError("artifact_not_found", "Available project artifact was not found", status_code=404)
        items.append(
            ExperimentResult(
                project_id=project.id,
                created_by=user.id,
                **{**item.model_dump(), "candidate_id": resolved_candidate_id},
            )
        )
    session.add_all(items)
    session.flush()
    record_audit(
        session,
        action="experiment_results.create",
        entity_type="experiment_result_batch",
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
        payload={"count": len(items)},
    )
    return items
