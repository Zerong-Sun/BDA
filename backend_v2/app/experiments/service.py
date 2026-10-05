from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..audit.service import record_audit
from ..candidates.models import Candidate
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from .models import ExperimentResult
from .schemas import ExperimentResultBatch, ExperimentResultCreate


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


def create_idempotent_result(
    session: Session,
    project: Project,
    payload: ExperimentResultCreate,
    user: User,
    *,
    request_key: str,
) -> ExperimentResult:
    """Internal adapter for a caller holding its measurement-contract lock.

    This domain owns both the measurement and its uniqueness key. The learning
    domain must not mutate experiment rows after calling create_results.
    """
    existing = session.scalar(
        select(ExperimentResult).where(
            ExperimentResult.project_id == project.id,
            ExperimentResult.legacy_id == request_key,
        )
    )
    if existing is not None:
        return existing
    row = create_results(session, project, ExperimentResultBatch(results=[payload]), user)[0]
    row.legacy_id = request_key
    session.flush()
    return row


def withdraw_learning_result(
    session: Session, project: Project, row: ExperimentResult, user: User, *, expected: int, rationale: str
) -> ExperimentResult:
    """Retain the original measurement; a versioned withdrawal changes eligibility."""
    if row.project_id != project.id or not isinstance(row.result_metadata.get("learning"), dict):
        raise DomainError("learning_result_not_found", "Learning result was not found", status_code=404)
    if row.version != expected:
        raise DomainError("version_conflict", "Measurement changed; reload before withdrawal", status_code=412)
    if row.result_metadata.get("learning_withdrawal"):
        raise DomainError("learning_result_withdrawn", "Measurement is already withdrawn", status_code=409)
    row.result_metadata = {
        **row.result_metadata,
        "learning_withdrawal": {"rationale": rationale, "by": str(user.id), "at": datetime.now(UTC).isoformat()},
    }
    row.version += 1
    session.flush()
    record_audit(
        session,
        action="learning.observation.withdraw",
        entity_type="experiment_result",
        entity_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return row
