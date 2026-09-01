from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..audit.service import record_audit
from ..candidates.models import Candidate
from ..compute.models import Job
from ..core.problem import DomainError
from ..core.rate_limit import enforce_project_quota
from ..experiments.models import ExperimentResult
from ..identity.models import User
from ..intelligence.models import IntelligenceRun
from ..knowledge.models import KnowledgeEntry
from ..literature.models import LiteratureDocument
from ..platform.operations import enqueue_operation
from ..research.models import ResearchBrief, ResearchFinding
from ..targets.repository import TargetRepository

# Through the timeline domain's own service, never into its table: a prompt rewrite is
# a decision on the project record, and this is the write that makes it non-optional.
from ..timeline.schemas import TimelineEntryCreate
from ..timeline.service import create_entry as create_timeline_entry
from ..workflows.models import WorkflowRun
from .models import Project, ProjectMember, ProjectPromptDraft
from .repository import ProjectRepository
from .schemas import (
    CandidateFunnelResponse,
    ProjectCreate,
    ProjectLibraryItem,
    ProjectOverviewResponse,
    ProjectPromptDraftAccepted,
    ProjectPromptDraftCreate,
    ProjectResearchSummaryResponse,
    ProjectResponse,
    ProjectUpdate,
    TargetReadinessResponse,
)

BUILTIN_RESEARCH_PACKAGE_PREFIXES = ("pd1-demo",)
BUILTIN_RESEARCH_PROJECT_NAMES = {
    "PD1": {"PD-1/PD-L1结合与调控网络", "PD-1/PD-L1 binding and regulatory network"},
}
BUILTIN_RESEARCH_PROJECT_TYPES = {
    "PD1": "checkpoint_protein_knowledge",
}


def _require_project_access(session: Session, project_id: uuid.UUID, user: User) -> Project:
    repo = ProjectRepository(session)
    project = repo.get(project_id)
    if project is None:
        raise DomainError("project_not_found", "Project was not found", status_code=404)
    if not repo.user_can_access(project, user):
        raise DomainError("forbidden", "The current user cannot access this project", status_code=403)
    return project


def require_project(session: Session, project_id: uuid.UUID, user: User) -> Project:
    project = _require_project_access(session, project_id, user)
    if getattr(user, "_bda_project_write_required", False):
        return _authorize_project_action(session, project, user, "write")
    return project


PROJECT_PERMISSION_MINIMUMS = {
    "read": "viewer",
    "write": "researcher",
    "compute": "researcher",
    "research_import": "researcher",
    "artifact": "researcher",
    "experiment": "researcher",
    "autopilot": "researcher",
    "manage": "admin",
}


def require_project_permission(
    session: Session,
    project_id: uuid.UUID,
    user: User,
    action: str,
) -> Project:
    """Authorize an action using global, organization, then project scope.

    Project membership can only narrow the organization role. It can never turn
    an organization viewer into a writer.
    """
    project = _require_project_access(session, project_id, user)
    return _authorize_project_action(session, project, user, action)


def _authorize_project_action(
    session: Session,
    project: Project,
    user: User,
    action: str,
) -> Project:
    role = ProjectRepository(session).effective_project_role(project, user)
    ranks = {"viewer": 0, "researcher": 1, "admin": 2, "owner": 3}
    minimum = PROJECT_PERMISSION_MINIMUMS.get(action)
    if minimum is None:
        raise RuntimeError(f"unknown project permission action: {action}")
    if role is None or ranks[role] < ranks[minimum]:
        raise DomainError(
            "project_permission_denied",
            f"Project permission '{action}' is required",
            status_code=403,
        )
    if action != "read":
        enforce_project_quota(user.id, project.organization_id, action)
    return project


def visible_project_ids(session: Session, user: User) -> list[uuid.UUID] | None:
    """Every project this user may read, or None for an administrator.

    None means "no fence" rather than "no projects", which is the distinction a
    caller has to get right: a fence of `[]` hides everything, and an admin needs
    the opposite. Membership follows `user_can_access` - direct project membership
    or membership of the owning organization - so a listing built on this cannot
    show more than the per-resource check would allow.
    """
    if user.role == "admin":
        return None
    repo = ProjectRepository(session)
    return [project.id for project in repo.list_visible(user, after=None, limit=10_000)]


def create_project(session: Session, payload: ProjectCreate, user: User) -> Project:
    repo = ProjectRepository(session)
    role = repo.organization_role(payload.organization_id, user.id)
    if user.role != "admin" and role not in {"admin", "owner", "researcher"}:
        raise DomainError("forbidden", "Organization membership is required", status_code=403)
    project = repo.add(
        Project(
            organization_id=payload.organization_id,
            owner_id=user.id,
            name=payload.name.strip(),
            project_type=payload.project_type.strip(),
            summary=payload.summary,
            prompt=payload.prompt,
            source_package_id=payload.source_package_id,
            source_project_key=payload.source_project_key,
            localized_content=payload.localized_content,
        )
    )
    session.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
    record_audit(
        session,
        action="project.create",
        entity_type="project",
        entity_id=project.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return project


def create_project_prompt_draft(
    session: Session, payload: ProjectPromptDraftCreate, user: User
) -> ProjectPromptDraftAccepted:
    repo = ProjectRepository(session)
    role = repo.organization_role(payload.organization_id, user.id)
    if user.role != "admin" and role not in {"admin", "owner", "researcher"}:
        raise DomainError("forbidden", "Organization membership is required", status_code=403)
    draft = ProjectPromptDraft(
        organization_id=payload.organization_id,
        created_by=user.id,
        request=payload.model_dump(mode="json"),
    )
    session.add(draft)
    session.flush()
    enqueue_operation(
        session,
        topic="project.prompt_generate",
        resource_type="project_prompt_draft",
        resource_id=draft.id,
        organization_id=payload.organization_id,
        user=user,
        payload={"draft_id": str(draft.id)},
    )
    return ProjectPromptDraftAccepted(draft_id=draft.id)


def require_project_prompt_draft(session: Session, draft_id: uuid.UUID, user: User) -> ProjectPromptDraft:
    draft = session.get(ProjectPromptDraft, draft_id)
    if draft is None:
        raise DomainError("project_prompt_draft_not_found", "Prompt draft was not found", status_code=404)
    if draft.created_by != user.id and user.role != "admin":
        raise DomainError("forbidden", "This prompt draft belongs to another user", status_code=403)
    return draft


def _record_prompt_change(session: Session, project: Project, previous: str | None, reason: str, user: User) -> None:
    """A rewritten brief becomes a decision on the record, not a silent overwrite.

    The prompt is what the goal tree and the open branches were derived from. Changing it
    without a trace leaves everything downstream pointing at text that no longer exists,
    and the previous wording - which is the only way to see what the change actually did -
    is gone. The old text goes into the body for exactly that reason.

    Written through the timeline domain's own service rather than into its table, and
    left `unspecified` on both lane and outcome: this records that the brief changed and
    why, and claims nothing about whether the change was right.
    """
    create_timeline_entry(
        session,
        project,
        TimelineEntryCreate(
            occurred_at=datetime.now(UTC),
            entry_type="decision",
            title="设计任务书（prompt）变更",
            summary=reason[:2000],
            body=(
                f"**变更理由**\n\n{reason}\n\n"
                "**变更前的任务书**\n\n"
                + (previous if previous else "（此前没有任务书）")
            ),
            tags=["prompt"],
        ),
        user,
    )


def update_project(
    session: Session, project: Project, payload: ProjectUpdate, user: User, expected_version: int
) -> Project:
    if project.version != expected_version:
        raise DomainError("version_conflict", "Project was modified by another request", status_code=412)
    changes = payload.model_dump(exclude_unset=True)
    reason = (changes.pop("prompt_change_reason", None) or "").strip()
    previous_prompt = project.prompt
    # Only a real difference counts. Re-saving the same text from a form that round-trips
    # the whole object is not a change and must not demand a justification for one.
    prompt_changed = "prompt" in changes and (changes["prompt"] or "") != (previous_prompt or "")
    if prompt_changed and previous_prompt and not reason:
        raise DomainError(
            "project_prompt_change_reason_required",
            "Changing the design prompt requires `prompt_change_reason`; it is recorded on the project timeline",
            status_code=422,
        )
    for field, value in changes.items():
        setattr(project, field, value)
    project.version += 1
    if prompt_changed and previous_prompt:
        _record_prompt_change(session, project, previous_prompt, reason, user)
    record_audit(
        session,
        action="project.update",
        entity_type="project",
        entity_id=project.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return project


def soft_delete_project(session: Session, project: Project, user: User) -> None:
    if user.role != "admin" and project.owner_id != user.id:
        raise DomainError("forbidden", "Only the project owner can delete this project", status_code=403)
    project.deleted_at = datetime.now(UTC)
    project.version += 1
    record_audit(
        session,
        action="project.delete",
        entity_type="project",
        entity_id=project.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )


def candidate_funnel(session: Session, project_id: uuid.UUID) -> CandidateFunnelResponse:
    rows = {
        status_name: int(count)
        for status_name, count in session.execute(
            select(Candidate.status, func.count(Candidate.id))
            .where(
                Candidate.project_id == project_id,
                Candidate.candidate_kind == "design_candidate",
            )
            .group_by(Candidate.status)
        ).tuples()
    }
    total = sum(rows.values())
    return CandidateFunnelResponse(
        generated=total,
        designed=sum(rows.get(key, 0) for key in ("designed", "folded", "scored", "selected", "ordered")),
        folded=sum(rows.get(key, 0) for key in ("folded", "scored", "selected", "ordered")),
        scored=sum(rows.get(key, 0) for key in ("scored", "selected", "ordered")),
        ordered=rows.get("ordered", 0),
    )


def target_readiness(session: Session, project: Project) -> TargetReadinessResponse:
    target = TargetRepository(session).get(project.primary_target_id) if project.primary_target_id else None
    blockers: list[str] = []
    if target is None:
        blockers.append("primary_target_missing")
    else:
        # A small-molecule target is judged by whether its chemistry resolves, not by
        # whether someone uploaded a protein structure for it.
        from ..targets.identity import readiness_blockers

        blockers.extend(readiness_blockers(target))
    return TargetReadinessResponse(
        stage="ready" if not blockers else "target_setup",
        ready_for_workflow=not blockers,
        blockers=blockers,
        next_action="create_workflow" if not blockers else blockers[0],
        target_id=target.id if target else None,
        structure_artifact_id=target.structure_artifact_id if target else None,
        identity_status=target.identity_status if target else None,
        structure_status=target.structure_status if target else None,
    )


def project_overview(session: Session, project: Project) -> ProjectOverviewResponse:
    def scalar_count(model, *criteria) -> int:
        return int(session.scalar(select(func.count(model.id)).where(*criteria)) or 0)

    latest = session.scalar(
        select(WorkflowRun).where(WorkflowRun.project_id == project.id).order_by(WorkflowRun.created_at.desc()).limit(1)
    )
    readiness = target_readiness(session, project)
    candidate_count = scalar_count(Candidate, Candidate.project_id == project.id)
    experiment_count = scalar_count(ExperimentResult, ExperimentResult.project_id == project.id)
    return ProjectOverviewResponse(
        project=ProjectResponse.model_validate(project),
        funnel=candidate_funnel(session, project.id),
        candidate_count=candidate_count,
        experiment_result_count=experiment_count,
        available_artifact_count=scalar_count(
            Artifact, Artifact.project_id == project.id, Artifact.status == "available"
        ),
        active_job_count=scalar_count(
            Job,
            Job.project_id == project.id,
            Job.status.in_(["pending", "dispatching", "queued", "running", "collecting"]),
        ),
        latest_workflow_id=latest.id if latest else None,
        target_readiness=readiness,
        next_action=(
            readiness.next_action
            if not readiness.ready_for_workflow
            else "review_results"
            if experiment_count
            else "review_candidates"
            if candidate_count
            else "edit_workflow"
        ),
    )


def project_research_summary(session: Session, project: Project) -> ProjectResearchSummaryResponse:
    brief = session.scalar(
        select(ResearchBrief).where(ResearchBrief.project_id == project.id).order_by(ResearchBrief.created_at.desc())
    )
    findings = list(
        session.scalars(
            select(ResearchFinding)
            .where(ResearchFinding.project_id == project.id)
            .order_by(ResearchFinding.created_at.desc())
        )
    )

    def count(model) -> int:
        return int(session.scalar(select(func.count(model.id)).where(model.project_id == project.id)) or 0)

    return ProjectResearchSummaryResponse(
        brief=({key: value for key, value in brief.__dict__.items() if not key.startswith("_")} if brief else None),
        findings=[{key: value for key, value in row.__dict__.items() if not key.startswith("_")} for row in findings],
        literature_document_count=count(LiteratureDocument),
        intelligence_run_count=count(IntelligenceRun),
        knowledge_entry_count=count(KnowledgeEntry),
    )


def _project_package_meta(project: Project) -> dict:
    localized = project.localized_content if isinstance(project.localized_content, dict) else {}
    package = localized.get("package", {})
    return package if isinstance(package, dict) else {}


def _project_package_id(project: Project) -> str:
    package_id = project.source_package_id or _project_package_meta(project).get("id") or ""
    return str(package_id)


def _is_builtin_research_package(project: Project) -> bool:
    return _project_package_id(project).startswith(BUILTIN_RESEARCH_PACKAGE_PREFIXES)


def _normalized_builtin_project_key(value: str | None) -> str | None:
    key = str(value or "").strip().upper()
    return key if key in BUILTIN_RESEARCH_PROJECT_NAMES else None


def _project_localized_names(project: Project) -> set[str]:
    localized = project.localized_content if isinstance(project.localized_content, dict) else {}
    name = localized.get("name", {})
    names = {project.name.strip()}
    if isinstance(name, dict):
        names.update(str(value).strip() for value in name.values() if str(value).strip())
    return names


def _legacy_builtin_research_key(project: Project) -> str | None:
    if _project_package_id(project):
        return None
    names = _project_localized_names(project)
    for key, aliases in BUILTIN_RESEARCH_PROJECT_NAMES.items():
        if project.project_type == BUILTIN_RESEARCH_PROJECT_TYPES[key] and names.intersection(aliases):
            return key
    return None


def _json_refs_builtin_package(value: object) -> bool:
    if isinstance(value, dict):
        if str(value.get("package_id") or value.get("citation") or "").startswith(
            BUILTIN_RESEARCH_PACKAGE_PREFIXES
        ):
            return True
        return any(_json_refs_builtin_package(item) for item in value.values())
    if isinstance(value, list):
        return any(_json_refs_builtin_package(item) for item in value)
    return False


def _has_builtin_research_lineage(session: Session, project: Project) -> bool:
    for value in session.scalars(select(ResearchFinding.evidence).where(ResearchFinding.project_id == project.id)):
        if _json_refs_builtin_package(value):
            return True
    for value in session.scalars(select(KnowledgeEntry.source).where(KnowledgeEntry.project_id == project.id)):
        if _json_refs_builtin_package(value):
            return True
    for value in session.scalars(select(Artifact.lineage).where(Artifact.project_id == project.id)):
        if _json_refs_builtin_package(value):
            return True
    return False


def _builtin_research_project_key(session: Session, project: Project) -> str | None:
    if not _is_builtin_research_package(project):
        legacy_key = _legacy_builtin_research_key(project)
        return legacy_key if legacy_key and _has_builtin_research_lineage(session, project) else None
    source_key = _normalized_builtin_project_key(project.source_project_key)
    if source_key:
        return source_key
    names = _project_localized_names(project)
    for key, aliases in BUILTIN_RESEARCH_PROJECT_NAMES.items():
        if names.intersection(aliases):
            return key
    return None


def _project_completeness_score(session: Session, project: Project) -> tuple[int, int, int, int, int, int, str, str]:
    def count(model, *criteria) -> int:
        return int(session.scalar(select(func.count(model.id)).where(*criteria)) or 0)

    candidates = count(Candidate, Candidate.project_id == project.id, Candidate.candidate_kind == "research_target")
    structures = count(
        Artifact,
        Artifact.project_id == project.id,
        Artifact.artifact_type == "target_structure",
        Artifact.deleted_at.is_(None),
    )
    references = count(LiteratureDocument, LiteratureDocument.project_id == project.id)
    findings = count(ResearchFinding, ResearchFinding.project_id == project.id)
    knowledge = count(KnowledgeEntry, KnowledgeEntry.project_id == project.id)
    return (
        candidates,
        structures,
        references,
        findings,
        knowledge,
        int(project.primary_target_id is not None),
        project.updated_at.isoformat(),
        str(project.id),
    )


def soft_delete_builtin_research_duplicates(
    session: Session, organization_id: uuid.UUID, user: User
) -> list[str]:
    rows = list(
        session.scalars(
            select(Project).where(
                Project.organization_id == organization_id,
                Project.deleted_at.is_(None),
            )
        )
    )
    grouped: dict[str, list[Project]] = {}
    for project in rows:
        key = _builtin_research_project_key(session, project)
        if key:
            grouped.setdefault(key, []).append(project)
    conflicts: list[str] = []
    for key, duplicates in grouped.items():
        if len(duplicates) < 2:
            continue
        retained = max(duplicates, key=lambda row: _project_completeness_score(session, row))
        for duplicate in duplicates:
            if duplicate.id == retained.id:
                continue
            if user.role != "admin" and duplicate.owner_id != user.id:
                conflicts.append(f"{key}: duplicate {duplicate.id} was not deleted because the caller is not its owner")
                continue
            soft_delete_project(session, duplicate, user)
    return conflicts


def dedupe_builtin_research_projects(session: Session, projects: list[Project]) -> list[Project]:
    best_by_key: dict[str, Project] = {}
    for project in projects:
        key = _builtin_research_project_key(session, project)
        if not key:
            continue
        current = best_by_key.get(key)
        if current is None or _project_completeness_score(session, project) > _project_completeness_score(session, current):
            best_by_key[key] = project
    emitted: set[str] = set()
    result: list[Project] = []
    for project in projects:
        key = _builtin_research_project_key(session, project)
        if not key:
            result.append(project)
            continue
        if key in emitted:
            continue
        emitted.add(key)
        result.append(best_by_key.get(key, project))
    return result


def project_library_item(session: Session, project: Project) -> ProjectLibraryItem:
    def count(model, *criteria) -> int:
        return int(session.scalar(select(func.count(model.id)).where(*criteria)) or 0)

    target = TargetRepository(session).get(project.primary_target_id) if project.primary_target_id else None
    package_meta = project.localized_content.get("package", {}) if isinstance(project.localized_content, dict) else {}
    def package_count(key: str, actual: int) -> int:
        expected = package_meta.get(key)
        return max(actual, int(expected)) if isinstance(expected, int | float) else actual

    return ProjectLibraryItem(
        **ProjectResponse.model_validate(project).model_dump(),
        research_candidate_count=package_count(
            "candidate_count",
            count(
                Candidate,
                Candidate.project_id == project.id,
                Candidate.candidate_kind == "research_target",
            ),
        ),
        finding_count=package_count(
            "finding_count", count(ResearchFinding, ResearchFinding.project_id == project.id)
        ),
        reference_count=package_count(
            "reference_count", count(LiteratureDocument, LiteratureDocument.project_id == project.id)
        ),
        knowledge_count=package_count(
            "knowledge_count", count(KnowledgeEntry, KnowledgeEntry.project_id == project.id)
        ),
        structure_count=package_count(
            "structure_count",
            count(
                Artifact,
                Artifact.project_id == project.id,
                Artifact.artifact_type == "target_structure",
                Artifact.deleted_at.is_(None),
            ),
        ),
        primary_structure_ready=bool(target and target.structure_artifact_id),
        package_version=str(package_meta.get("version")) if package_meta.get("version") else None,
        evidence_as_of=str(package_meta.get("as_of")) if package_meta.get("as_of") else None,
    )
