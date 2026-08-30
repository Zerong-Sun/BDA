from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..audit.service import record_audit
from ..candidates.models import Candidate
from ..experiments.models import ExperimentResult
from ..identity.models import User
from ..platform.models import Operation
from ..platform.operations import enqueue_operation
from ..projects.models import Project
from .models import DeliveryPackage
from .schemas import DeliveryCreate, ResultSummary


def _kd_value_in_molar(value: float | None, unit: str | None) -> float | None:
    if value is None or value < 0 or not unit:
        return None
    normalized = unit.strip().replace("μ", "u").replace("µ", "u").lower()
    factor = {
        "m": 1.0,
        "mm": 1e-3,
        "um": 1e-6,
        "nm": 1e-9,
        "pm": 1e-12,
    }.get(normalized)
    return value * factor if factor is not None else None


def create_delivery(
    session: Session, project: Project, payload: DeliveryCreate, user: User
) -> tuple[DeliveryPackage, Operation]:
    package = DeliveryPackage(
        project_id=project.id, created_by=user.id, name=payload.name, selection=payload.model_dump(mode="json")
    )
    session.add(package)
    session.flush()
    operation = enqueue_operation(
        session,
        topic="delivery.build",
        resource_type="delivery_package",
        resource_id=package.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"delivery_package_id": str(package.id)},
    )
    record_audit(
        session,
        action="delivery.create",
        entity_type="delivery_package",
        entity_id=package.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return package, operation


def result_summary(session: Session, project: Project) -> ResultSummary:
    candidate_count = (
        session.scalar(select(func.count()).select_from(Candidate).where(Candidate.project_id == project.id)) or 0
    )
    result_count = (
        session.scalar(
            select(func.count()).select_from(ExperimentResult).where(ExperimentResult.project_id == project.id)
        )
        or 0
    )
    artifact_count = (
        session.scalar(
            select(func.count())
            .select_from(Artifact)
            .where(Artifact.project_id == project.id, Artifact.status == "available", Artifact.deleted_at.is_(None))
        )
        or 0
    )
    top = list(
        session.scalars(
            select(Candidate.id)
            .where(Candidate.project_id == project.id)
            .order_by(Candidate.rank.asc().nullslast(), Candidate.score.desc().nullslast())
            .limit(20)
        )
    )
    status_counts: dict[str, int] = {
        status: int(count)
        for status, count in session.execute(
            select(ExperimentResult.pass_status, func.count())
            .where(ExperimentResult.project_id == project.id)
            .group_by(ExperimentResult.pass_status)
        ).tuples()
    }
    tested_candidate_count = (
        session.scalar(
            select(func.count(func.distinct(ExperimentResult.candidate_id))).where(
                ExperimentResult.project_id == project.id,
                ExperimentResult.candidate_id.is_not(None),
            )
        )
        or 0
    )
    kd_results = list(
        session.scalars(
            select(ExperimentResult).where(
                ExperimentResult.project_id == project.id,
                ExperimentResult.value.is_not(None),
                func.lower(ExperimentResult.experiment_type).like("%kd%"),
            )
        )
    )
    comparable_kd_results = [
        (normalized, item)
        for item in kd_results
        if (normalized := _kd_value_in_molar(item.value, item.unit)) is not None
    ]
    best_result = (
        min(comparable_kd_results, key=lambda pair: (pair[0], str(pair[1].id)))[1]
        if comparable_kd_results
        else None
    )
    passed = int(status_counts.get("pass", 0))
    failed = int(status_counts.get("fail", 0))
    decided = passed + failed
    return ResultSummary(
        project_id=project.id,
        candidate_count=candidate_count,
        experiment_result_count=result_count,
        available_artifact_count=artifact_count,
        tested_candidate_count=tested_candidate_count,
        passed_result_count=passed,
        failed_result_count=failed,
        unknown_result_count=int(status_counts.get("unknown", 0)),
        pass_rate=passed / decided if decided else None,
        top_candidate_ids=top,
        best_result_id=best_result.id if best_result else None,
        best_result_value=best_result.value if best_result else None,
        best_result_unit=best_result.unit if best_result else None,
    )
