from sqlalchemy.orm import Session

from ..core.problem import DomainError
from ..identity.models import User
from ..platform.operations import enqueue_operation
from ..projects.models import Project
from ..targets.models import Target
from ..workflows.models import WorkflowRun
from .models import DesignRoute, IntelligenceEvidence, IntelligenceHotspot, IntelligenceReport, IntelligenceRun
from .schemas import EvidenceReview, HotspotReview, IntelligenceCreate, ReportReview


def create_run(session: Session, project: Project, payload: IntelligenceCreate, user: User) -> IntelligenceRun:
    target = session.get(Target, payload.target_id)
    if target is None or target.project_id != project.id:
        raise DomainError("target_not_found", "Target does not belong to this project", status_code=404)
    row = IntelligenceRun(project_id=project.id, created_by=user.id, **payload.model_dump())
    session.add(row)
    session.flush()
    enqueue_operation(
        session,
        topic="intelligence.run",
        resource_type="intelligence_run",
        resource_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"run_id": str(row.id)},
    )
    return row


def apply_route(session: Session, route: DesignRoute, run: IntelligenceRun, user: User) -> WorkflowRun:
    if route.applied_workflow_id:
        return session.get(WorkflowRun, route.applied_workflow_id)  # type: ignore[return-value]
    workflow = WorkflowRun(project_id=run.project_id, name=route.name, graph=route.workflow_spec, created_by=user.id)
    session.add(workflow)
    session.flush()
    route.applied_workflow_id = workflow.id
    route.status = "applied"
    route.version += 1
    return workflow


def review_report(row: IntelligenceReport, payload: ReportReview, expected: int) -> IntelligenceReport:
    _check_version(row.version, expected, "Report")
    row.review_status = payload.review_status
    if payload.summary is not None:
        row.summary = payload.summary
    row.version += 1
    return row


def review_evidence(row: IntelligenceEvidence, payload: EvidenceReview, expected: int) -> IntelligenceEvidence:
    _check_version(row.version, expected, "Evidence")
    row.review_status = payload.review_status
    if payload.confidence is not None:
        row.confidence = payload.confidence
    row.version += 1
    return row


def review_hotspot(row: IntelligenceHotspot, payload: HotspotReview, expected: int) -> IntelligenceHotspot:
    _check_version(row.version, expected, "Hotspot")
    row.review_status = payload.review_status
    if payload.rationale is not None:
        row.rationale = payload.rationale
    row.version += 1
    return row


def _check_version(actual: int, expected: int, resource: str) -> None:
    if actual != expected:
        raise DomainError("version_conflict", f"{resource} was modified", status_code=412)
