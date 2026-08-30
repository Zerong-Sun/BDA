import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..candidates.repository import CandidateRepository
from ..core.problem import DomainError
from ..identity.models import User
from ..platform.operations import enqueue_operation
from ..projects.models import Project
from .models import ResearchBrief, ResearchFinding
from .schemas import (
    BriefCreate,
    BriefUpdate,
    FindingCreate,
    FindingUpdate,
    ResearchGapResolutionAccepted,
    ResearchGapResolutionCreate,
)


def request_gap_resolution(
    session: Session,
    project: Project,
    research_target_id: uuid.UUID,
    payload: ResearchGapResolutionCreate,
    user: User,
) -> ResearchGapResolutionAccepted:
    # Multiple Copilot/API requests may target the same gap concurrently.
    # Lock before incrementing the attempt and enqueuing the operation so the
    # versioned candidate update cannot race into a StaleDataError/HTTP 500.
    candidate = CandidateRepository(session).get(research_target_id, for_update=True)
    if (
        candidate is None
        or candidate.project_id != project.id
        or candidate.candidate_kind != "research_target"
    ):
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
    operation = enqueue_operation(
        session,
        topic="research.gaps.resolve",
        resource_type="research_target",
        resource_id=candidate.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload=payload.model_dump(mode="json"),
    )
    properties["gap_resolution"]["operation_id"] = str(operation.id)
    candidate.properties = properties
    record_audit(
        session,
        action="research.gaps.resolve.request",
        entity_type="research_target",
        entity_id=candidate.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
        payload={
            "operation_id": str(operation.id),
            "resolve_references": payload.resolve_references,
            "resolve_structure": payload.resolve_structure,
        },
    )
    return ResearchGapResolutionAccepted(
        operation_id=operation.id,
        research_target_id=candidate.id,
    )


def create_brief(session: Session, project: Project, payload: BriefCreate, user: User) -> ResearchBrief:
    row = ResearchBrief(project_id=project.id, created_by=user.id, **payload.model_dump())
    session.add(row)
    session.flush()
    return row


def _require_superseded(session: Session, project: Project, supersedes_id) -> None:
    """A finding may only overturn one from the same project."""
    if supersedes_id is None:
        return
    superseded = session.get(ResearchFinding, supersedes_id)
    if superseded is None or superseded.project_id != project.id:
        raise DomainError(
            "research_finding_not_found", "The superseded finding was not found", status_code=404
        )


def create_finding(session: Session, project: Project, payload: FindingCreate, user: User) -> ResearchFinding:
    _require_superseded(session, project, payload.supersedes_id)
    row = ResearchFinding(project_id=project.id, created_by=user.id, **payload.model_dump())
    session.add(row)
    session.flush()
    return row


def update_brief(
    session: Session,
    project: Project,
    brief: ResearchBrief,
    payload: BriefUpdate,
    user: User,
    expected_version: int,
) -> ResearchBrief:
    if brief.version != expected_version:
        raise DomainError("version_conflict", "Research brief was modified", status_code=412)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(brief, field, value)
    brief.version += 1
    record_audit(
        session,
        action="research.brief.update",
        entity_type="research_brief",
        entity_id=brief.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return brief


def update_finding(
    session: Session,
    project: Project,
    finding: ResearchFinding,
    payload: FindingUpdate,
    user: User,
    expected_version: int,
) -> ResearchFinding:
    if finding.version != expected_version:
        raise DomainError("version_conflict", "Research finding was modified", status_code=412)
    if payload.brief_id:
        brief = session.get(ResearchBrief, payload.brief_id)
        if brief is None or brief.project_id != project.id:
            raise DomainError("research_brief_not_found", "Research brief was not found", status_code=404)
    _require_superseded(session, project, payload.supersedes_id)
    if payload.supersedes_id is not None and payload.supersedes_id == finding.id:
        raise DomainError(
            "research_finding_invalid", "A finding cannot supersede itself", status_code=422
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(finding, field, value)
    finding.version += 1
    record_audit(
        session,
        action="research.finding.update",
        entity_type="research_finding",
        entity_id=finding.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return finding


def delete_research_resource(
    session: Session,
    project: Project,
    resource: ResearchBrief | ResearchFinding,
    user: User,
    expected_version: int,
) -> None:
    if resource.version != expected_version:
        raise DomainError("version_conflict", "Research resource was modified", status_code=412)
    resource_type = "research_brief" if isinstance(resource, ResearchBrief) else "research_finding"
    record_audit(
        session,
        action=f"{resource_type}.delete",
        entity_type=resource_type,
        entity_id=resource.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    session.delete(resource)
