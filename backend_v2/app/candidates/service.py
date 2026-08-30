from __future__ import annotations

from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..audit.service import record_audit
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from .models import Candidate
from .schemas import CandidateCreate, CandidateUpdate


def _verify_artifacts(session: Session, project: Project, ids: list) -> None:
    for artifact_id in filter(None, ids):
        artifact = session.get(Artifact, artifact_id)
        if artifact is None or artifact.project_id != project.id or artifact.status != "available":
            raise DomainError(
                "artifact_not_found", "Candidate artifact must be available in the same project", status_code=404
            )


def create_candidate(session: Session, project: Project, payload: CandidateCreate, user: User) -> Candidate:
    _verify_artifacts(session, project, [payload.structure_artifact_id, payload.complex_artifact_id])
    candidate = Candidate(project_id=project.id, **payload.model_dump())
    session.add(candidate)
    session.flush()
    record_audit(
        session,
        action="candidate.create",
        entity_type="candidate",
        entity_id=candidate.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return candidate


def update_candidate(
    session: Session,
    project: Project,
    candidate: Candidate,
    payload: CandidateUpdate,
    user: User,
    expected_version: int,
) -> Candidate:
    if candidate.version != expected_version:
        raise DomainError("version_conflict", "Candidate was modified by another request", status_code=412)
    values = payload.model_dump(exclude_unset=True)
    _verify_artifacts(session, project, [values.get("structure_artifact_id"), values.get("complex_artifact_id")])
    for field, value in values.items():
        setattr(candidate, field, value)
    candidate.version += 1
    record_audit(
        session,
        action="candidate.update",
        entity_type="candidate",
        entity_id=candidate.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return candidate
