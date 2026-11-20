from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..audit.service import record_audit
from ..compute.models import Job
from ..core.models import update_versioned
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from .models import Candidate, CandidateMetric
from .repository import CandidateRepository
from .schemas import CandidateCreate, CandidateUpdate

if TYPE_CHECKING:
    from ..compute.parsers.base import ParsedMetric


def _verify_artifacts(session: Session, project: Project, ids: list) -> None:
    for artifact_id in filter(None, ids):
        artifact = session.get(Artifact, artifact_id)
        if artifact is None or artifact.project_id != project.id or artifact.status != "available":
            raise DomainError(
                "artifact_not_found", "Candidate artifact must be available in the same project", status_code=404
            )


def project_candidates(session: Session, project_id: uuid.UUID) -> list[Candidate]:
    return list(session.scalars(select(Candidate).where(Candidate.project_id == project_id)))


def save_research_candidate(
    session: Session,
    project: Project,
    existing: Candidate | None,
    *,
    candidate_key: str,
    name: str,
    rank: int | None,
    score: float | None,
    scores: dict,
    properties: dict,
) -> None:
    """Create or refresh a curated research-target candidate from an imported package."""
    if existing is None:
        session.add(
            Candidate(
                project_id=project.id,
                candidate_key=candidate_key,
                name=name,
                candidate_kind="research_target",
                status="proposed",
                rank=rank,
                score=score,
                scores=scores,
                properties=properties,
            )
        )
        return
    update_versioned(
        existing,
        name=name,
        candidate_kind="research_target",
        status="proposed",
        rank=rank,
        score=score,
        scores=scores,
        properties=properties,
    )


def delete_project_candidates(
    session: Session, project_id: uuid.UUID, should_delete: Callable[[Candidate], bool]
) -> None:
    for candidate in project_candidates(session, project_id):
        if should_delete(candidate):
            session.delete(candidate)


def get_candidate(session: Session, candidate_id: uuid.UUID) -> Candidate | None:
    return CandidateRepository(session).get(candidate_id)


def add_collected_candidate(session: Session, **fields: object) -> Candidate:
    """A candidate a verified job output proposed; flushed so its metrics can reference it."""
    candidate = Candidate(**fields)
    session.add(candidate)
    session.flush()
    return candidate


def record_candidate_metrics(
    session: Session,
    candidate: Candidate,
    metrics: list[ParsedMetric],
    job_id: uuid.UUID | None,
) -> None:
    """Upsert a candidate's metrics, keyed by where each number came from.

    Re-collecting an attempt must not duplicate rows, so a metric is matched on
    (candidate, key, method, variant, condition) - the same tuple the table's unique
    constraint uses. Condition has to be part of the match: a design scored against a
    panel of ligands reports the same (key, method, variant) once per ligand, and
    without condition in the WHERE clause the second ligand's row would be found as
    "existing" and silently overwrite the first instead of accumulating beside it.
    """
    for metric in metrics:
        existing = session.scalar(
            select(CandidateMetric).where(
                CandidateMetric.candidate_id == candidate.id,
                CandidateMetric.metric_key == metric.key,
                CandidateMetric.method == metric.method,
                CandidateMetric.model_variant == metric.model_variant,
                CandidateMetric.condition == metric.condition,
            )
        )
        if existing is not None:
            existing.value = metric.value
            existing.unit = metric.unit
            existing.evidence_kind = metric.evidence_kind
            existing.assessor = metric.assessor
            existing.context = metric.context
            existing.source_job_id = job_id
            continue
        session.add(
            CandidateMetric(
                candidate_id=candidate.id,
                metric_key=metric.key,
                value=metric.value,
                method=metric.method,
                model_variant=metric.model_variant,
                evidence_kind=metric.evidence_kind,
                assessor=metric.assessor,
                condition=metric.condition,
                unit=metric.unit,
                context=metric.context,
                source_job_id=job_id,
            )
        )


def record_measured_metric(
    session: Session,
    *,
    candidate_id: uuid.UUID,
    metric_key: str,
    value: float,
    method: str,
    unit: str,
    context: dict,
    source_experiment_result_id: uuid.UUID,
) -> CandidateMetric:
    """Upsert the instrument-measured value of one metric for one assay type."""
    existing = session.scalar(
        select(CandidateMetric).where(
            CandidateMetric.candidate_id == candidate_id,
            CandidateMetric.metric_key == metric_key,
            CandidateMetric.method == method,
            CandidateMetric.model_variant == "",
            CandidateMetric.condition == "",
        )
    )
    if existing is not None:
        existing.value = value
        existing.unit = unit
        existing.source_experiment_result_id = source_experiment_result_id
        existing.context = {**existing.context, **context}
        existing.version += 1
        session.flush()
        return existing

    metric = CandidateMetric(
        candidate_id=candidate_id,
        metric_key=metric_key,
        value=value,
        method=method,
        model_variant="",
        # Not a prediction. This is the distinction the column was added for.
        evidence_kind="measured",
        # A bench instrument is as independent as an assessor gets: it has no
        # stake in the design model's ranking.
        assessor="instrument",
        condition="",
        unit=unit,
        context=context,
        source_experiment_result_id=source_experiment_result_id,
    )
    session.add(metric)
    session.flush()
    return metric


def withdraw_measured_metrics(session: Session, source_experiment_result_id: uuid.UUID) -> None:
    """Drop the metrics projected from one result; the result and its audit history stay."""
    session.query(CandidateMetric).filter(
        CandidateMetric.source_experiment_result_id == source_experiment_result_id
    ).delete(synchronize_session="fetch")
    session.flush()


def lock_candidate(session: Session, candidate_id: uuid.UUID) -> Candidate | None:
    return CandidateRepository(session).get(candidate_id, for_update=True)


def link_structure(candidate: Candidate, artifact_id: uuid.UUID) -> None:
    update_versioned(candidate, structure_artifact_id=artifact_id)


def begin_gap_resolution(session: Session, project: Project, research_target_id: uuid.UUID) -> Candidate:
    """Lock a project's research target and open a new pending gap-resolution attempt.

    The row lock serializes concurrent requests so the attempt counter and the
    versioned update cannot race into a stale-data error.
    """
    candidate = CandidateRepository(session).get(research_target_id, for_update=True)
    if candidate is None or candidate.project_id != project.id or candidate.candidate_kind != "research_target":
        raise DomainError(
            "research_target_not_found",
            "Research target was not found in this project",
            status_code=404,
        )
    properties = dict(candidate.properties or {})
    previous = properties.get("gap_resolution")
    attempt = int(previous.get("attempt") or 0) + 1 if isinstance(previous, dict) else 1
    properties["gap_resolution"] = {
        "status": "pending",
        "attempt": attempt,
        "requested_at": datetime.now(UTC).isoformat(),
        "items": [],
    }
    candidate.properties = properties
    candidate.version += 1
    return candidate


def record_gap_resolution_operation(candidate: Candidate, operation_id: uuid.UUID) -> None:
    # A new mapping, not the one already assigned: the JSON column only sees reassignment.
    properties = dict(candidate.properties or {})
    properties["gap_resolution"] = {**(properties.get("gap_resolution") or {}), "operation_id": str(operation_id)}
    candidate.properties = properties


def settle_gap_resolution(session: Session, research_target_id: uuid.UUID, operation_id: str, outcome: dict) -> bool:
    """Record a finished attempt unless a newer attempt has replaced it. False if the target is gone."""
    candidate = session.scalar(select(Candidate).where(Candidate.id == research_target_id).with_for_update())
    if candidate is None:
        return False
    properties = dict(candidate.properties or {})
    pending = properties.get("gap_resolution")
    resolution = dict(pending) if isinstance(pending, dict) else {}
    current_operation_id = str(resolution.get("operation_id") or "")
    if not operation_id or not current_operation_id or operation_id == current_operation_id:
        resolution.update(outcome)
        properties["gap_resolution"] = resolution
        candidate.properties = properties
        candidate.version += 1
    return True


def create_candidate(session: Session, project: Project, payload: CandidateCreate, user: User) -> Candidate:
    # A client may retry after the commit succeeded but its response was lost.
    # Replay identical creates only; a reused key must never overwrite a design.
    repository = CandidateRepository(session)
    values = payload.model_dump()

    def replay(existing: Candidate) -> Candidate:
        if any(getattr(existing, field) != value for field, value in values.items()):
            raise DomainError(
                "candidate_key_conflict", "Candidate key already exists with different content", status_code=409,
                errors=[{"candidate_id": str(existing.id)}],
            )
        return existing

    existing = repository.get_by_key(project.id, payload.candidate_key)
    if existing is not None:
        return replay(existing)
    _verify_artifacts(session, project, [payload.structure_artifact_id, payload.complex_artifact_id])
    if payload.source_job_id is not None:
        job = session.get(Job, payload.source_job_id)
        if job is None or job.project_id != project.id:
            raise DomainError("job_not_found", "Candidate source job must belong to the same project", status_code=404)
    candidate = Candidate(project_id=project.id, **values)
    try:
        with session.begin_nested():
            session.add(candidate)
            session.flush()
    except IntegrityError:
        # The unique constraint also arbitrates simultaneous retries. A savepoint
        # keeps the surrounding transaction usable when that insert loses.
        existing = repository.get_by_key(project.id, payload.candidate_key)
        if existing is None:
            raise
        return replay(existing)
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
    # Lock and refresh before checking the client version. Two simultaneous edits
    # must report a 412, rather than racing into a StaleDataError at commit.
    current = CandidateRepository(session).get(candidate.id, for_update=True)
    if current is None or current.project_id != project.id:
        raise DomainError("candidate_not_found", "Candidate was not found in this project", status_code=404)
    candidate = current
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
                "unit": row.unit,
                "context": row.context,
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
        "conflicted": verdict.conflicted,
        "scale_unknown": verdict.scale_unknown,
        "metric_count": len(rows),
        "criteria": [asdict(item) for item in verdict.criteria],
        # A fallback explains what to fix, but losing the other comparisons
        # makes a failed stricter tier indistinguishable from an unassessed one.
        "tier_assessments": {
            name: {
                "outcome": (
                    "scale_conflict" if any(item.outcome == "scale_conflict" for item in criteria)
                    else "scale_unknown" if any(item.outcome == "scale_unknown" for item in criteria)
                    else "fail" if any(item.outcome == "fail" for item in criteria)
                    else "missing" if any(item.outcome == "missing" for item in criteria)
                    else "pass" if criteria else "not_assessed"
                ),
                "passed": sum(item.outcome == "pass" for item in criteria),
                "failed": sum(item.outcome == "fail" for item in criteria),
                "missing": sum(item.outcome == "missing" for item in criteria),
                "conflicted": sum(item.outcome == "scale_conflict" for item in criteria),
                "scale_unknown": sum(item.outcome == "scale_unknown" for item in criteria),
                "criteria": [asdict(item) for item in criteria],
            }
            for name, criteria in verdict.tier_criteria.items()
        },
    }
