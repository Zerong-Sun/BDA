from __future__ import annotations

import uuid
from dataclasses import asdict

from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..audit.service import record_audit
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from .models import Candidate
from .repository import CandidateRepository
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


def triage_candidate(
    session: Session,
    project: Project,
    candidate_id: uuid.UUID,
    tiers: dict[str, dict[str, str]],
) -> dict:
    """Judge one candidate against declared acceptance tiers.

    The tiers arrive as an argument rather than being looked up here: they
    belong to a route in the copilot's catalogue, and a domain service reaching
    into that would point the dependency the wrong way. This owns the part that
    is a candidates question - which numbers this design actually has.

    Every metric row is passed to the kernel, including several seeds of the
    same key, because choosing between them is the kernel's documented job and
    doing it here would hide the choice from its tests.
    """
    from .triage import triage as evaluate_tiers

    candidate = CandidateRepository(session).get(candidate_id)
    if candidate is None or candidate.project_id != project.id:
        raise DomainError("candidate_not_found", "No such candidate in this project.", status_code=404)
    rows = CandidateRepository(session).metrics_for(candidate.id)
    verdict = evaluate_tiers(
        [
            {
                "key": row.metric_key,
                "value": row.value,
                "method": row.method,
                "assessor": row.assessor,
            }
            for row in rows
        ],
        tiers,
    )
    return {
        "candidate_id": str(candidate.id),
        "candidate_key": candidate.candidate_key,
        "name": candidate.name,
        "tier": verdict.tier,
        "criteria_tier": verdict.criteria_tier,
        "passed": verdict.passed,
        "failed": verdict.failed,
        "missing": verdict.missing,
        "metric_count": len(rows),
        "criteria": [asdict(item) for item in verdict.criteria],
        # A fallback explains what to fix, but losing the other comparisons
        # makes a failed stricter tier indistinguishable from an unassessed one.
        "tier_assessments": {
            name: {
                "outcome": (
                    "fail" if any(item.outcome == "fail" for item in criteria)
                    else "missing" if any(item.outcome == "missing" for item in criteria)
                    else "pass" if criteria else "not_assessed"
                ),
                "passed": sum(item.outcome == "pass" for item in criteria),
                "failed": sum(item.outcome == "fail" for item in criteria),
                "missing": sum(item.outcome == "missing" for item in criteria),
                "criteria": [asdict(item) for item in criteria],
            }
            for name, criteria in verdict.tier_criteria.items()
        },
    }
