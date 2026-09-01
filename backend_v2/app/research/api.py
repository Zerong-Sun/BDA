from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_session
from ..core.etag import etag, parse_if_match
from ..core.pagination import decode_cursor, encode_cursor
from ..core.problem import DomainError
from ..identity.deps import current_user, require_command
from ..identity.models import User
from ..projects.repository import ProjectRepository
from ..projects.service import require_project, require_project_permission
from . import goals
from .copilot_import import import_copilot_research_result, validation_response
from .generation import create_research_generation, import_research_generation, require_research_generation
from .models import ResearchGoal
from .package_catalog import catalog_packages, load_catalog_package
from .package_import import import_research_package
from .repository import ResearchRepository
from .schemas import (
    BriefCreate,
    BriefPage,
    BriefResponse,
    BriefUpdate,
    CopilotResearchImportResponse,
    CopilotResearchResultCreate,
    CopilotResearchValidationResponse,
    FindingCreate,
    FindingPage,
    FindingResponse,
    FindingUpdate,
    ResearchGapResolutionAccepted,
    ResearchGapResolutionCreate,
    ResearchGenerationAccepted,
    ResearchGenerationCreate,
    ResearchGenerationImportCreate,
    ResearchGenerationImportResponse,
    ResearchGenerationResponse,
    ResearchGoalCreate,
    ResearchGoalDeleteResponse,
    ResearchGoalLinkCreate,
    ResearchGoalLinkDeleteResponse,
    ResearchGoalLinkResponse,
    ResearchGoalResponse,
    ResearchGoalTree,
    ResearchGoalUpdate,
    ResearchOverview,
    ResearchPackageCatalogImportCreate,
    ResearchPackageDescriptor,
    ResearchPackageImportCreate,
    ResearchPackageImportResponse,
    ResearchWorkspaceResponse,
)
from .service import (
    create_brief,
    create_finding,
    delete_research_resource,
    request_gap_resolution,
    update_brief,
    update_finding,
)
from .workspace import build_research_workspace

router = APIRouter(tags=["research"])


@router.get("/research-packages", response_model=list[ResearchPackageDescriptor])
def get_research_packages(
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[ResearchPackageDescriptor]:
    visible = {
        project.source_package_id
        for project in ProjectRepository(session).list_visible(user, after=None, limit=10_000)
        if project.source_package_id
    }
    return [
        ResearchPackageDescriptor(
            package_id=package["package_id"],
            version=package["version"],
            display_name=package["title"],
            license=package["license"],
            checksum=checksum,
            size=size,
            installed=package["package_id"] in visible,
        )
        for package, checksum, size in catalog_packages()
    ]


@router.post(
    "/projects/{project_id}/research-generations",
    response_model=ResearchGenerationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "research.generation.create"},
)
def post_research_generation(
    project_id: uuid.UUID,
    payload: ResearchGenerationCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ResearchGenerationAccepted:
    return create_research_generation(
        session,
        require_project_permission(session, project_id, user, "research_import"),
        payload,
        user,
    )


@router.get("/research-generations/{generation_id}", response_model=ResearchGenerationResponse)
def get_research_generation(
    generation_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ResearchGenerationResponse:
    row = require_research_generation(session, generation_id, user)
    return ResearchGenerationResponse.model_validate(row)


@router.post(
    "/research-generations/{generation_id}/import",
    response_model=ResearchGenerationImportResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "research.generation.import"},
)
def post_research_generation_import(
    generation_id: uuid.UUID,
    payload: ResearchGenerationImportCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ResearchGenerationImportResponse:
    row = require_research_generation(session, generation_id, user)
    return import_research_generation(session, row, payload.checksum, user)


@router.post(
    "/copilot-research-imports/validate",
    response_model=CopilotResearchValidationResponse,
    openapi_extra={"x-permission": "research.package.import"},
)
def post_copilot_research_validation(
    payload: CopilotResearchResultCreate,
    user: User = Depends(current_user),
) -> CopilotResearchValidationResponse:
    del user
    return validation_response(payload)


@router.post(
    "/copilot-research-imports",
    response_model=CopilotResearchImportResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "research.package.import"},
)
def post_copilot_research_import(
    payload: CopilotResearchResultCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> CopilotResearchImportResponse:
    return import_copilot_research_result(session, payload, user)


@router.post(
    "/research-package-imports",
    response_model=ResearchPackageImportResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "research.package.import"},
)
def post_research_package_import(
    payload: ResearchPackageCatalogImportCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ResearchPackageImportResponse:
    package, _, _ = load_catalog_package(payload.package_id, payload.version, payload.checksum)
    return import_research_package(
        session,
        ResearchPackageImportCreate(organization_id=payload.organization_id, package=package),
        user,
    )


@router.post(
    "/research-package-imports/legacy-payload",
    response_model=ResearchPackageImportResponse,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
    openapi_extra={"x-permission": "research.package.import"},
)
def post_legacy_research_package_import(
    payload: ResearchPackageImportCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ResearchPackageImportResponse:
    settings = get_settings()
    if settings.is_production and not settings.allow_legacy_research_package_payload:
        raise DomainError(
            "legacy_research_package_payload_disabled",
            "Raw research package payloads are disabled in production",
            status_code=403,
        )
    return import_research_package(session, payload, user)


@router.get("/projects/{project_id}/research", response_model=ResearchOverview)
def get_research(
    project_id: uuid.UUID, session: Session = Depends(get_session), user: User = Depends(current_user)
) -> ResearchOverview:
    require_project(session, project_id, user)
    briefs, findings = ResearchRepository(session).overview(project_id)
    return ResearchOverview(
        briefs=[BriefResponse.model_validate(x) for x in briefs],
        findings=[FindingResponse.model_validate(x) for x in findings],
    )


@router.get("/projects/{project_id}/research-workspace", response_model=ResearchWorkspaceResponse)
def get_research_workspace(
    project_id: uuid.UUID, session: Session = Depends(get_session), user: User = Depends(current_user)
) -> ResearchWorkspaceResponse:
    project = require_project(session, project_id, user)
    return build_research_workspace(session, project)


@router.post(
    "/projects/{project_id}/research-targets/{research_target_id}/gap-resolutions",
    response_model=ResearchGapResolutionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "research.gaps.resolve"},
)
def post_research_gap_resolution(
    project_id: uuid.UUID,
    research_target_id: uuid.UUID,
    payload: ResearchGapResolutionCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ResearchGapResolutionAccepted:
    project = require_project_permission(session, project_id, user, "research_import")
    return request_gap_resolution(session, project, research_target_id, payload, user)


@router.post(
    "/projects/{project_id}/research-briefs",
    response_model=BriefResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "research.brief.create"},
)
def post_brief(
    project_id: uuid.UUID,
    payload: BriefCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> BriefResponse:
    return BriefResponse.model_validate(
        create_brief(session, require_project_permission(session, project_id, user, "write"), payload, user)
    )


@router.get("/projects/{project_id}/research-briefs", response_model=BriefPage)
def list_briefs(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> BriefPage:
    require_project(session, project_id, user)
    rows = ResearchRepository(session).list_briefs(project_id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return BriefPage(
        items=[BriefResponse.model_validate(item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get("/research-briefs/{brief_id}", response_model=BriefResponse)
def get_brief(
    brief_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> BriefResponse:
    row = ResearchRepository(session).brief(brief_id)
    if row is None:
        raise DomainError("research_brief_not_found", "Research brief was not found", status_code=404)
    require_project(session, row.project_id, user)
    response.headers["ETag"] = etag(row.version)
    return BriefResponse.model_validate(row)


@router.patch(
    "/research-briefs/{brief_id}",
    response_model=BriefResponse,
    openapi_extra={"x-permission": "research.brief.update"},
)
def patch_brief(
    brief_id: uuid.UUID,
    payload: BriefUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> BriefResponse:
    row = ResearchRepository(session).brief(brief_id)
    if row is None:
        raise DomainError("research_brief_not_found", "Research brief was not found", status_code=404)
    project = require_project_permission(session, row.project_id, user, "write")
    updated = update_brief(session, project, row, payload, user, parse_if_match(if_match))
    response.headers["ETag"] = etag(updated.version)
    return BriefResponse.model_validate(updated)


@router.delete(
    "/research-briefs/{brief_id}",
    response_model=BriefResponse,
    openapi_extra={"x-permission": "research.brief.delete"},
)
def delete_brief(
    brief_id: uuid.UUID,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> BriefResponse:
    row = ResearchRepository(session).brief(brief_id)
    if row is None:
        raise DomainError("research_brief_not_found", "Research brief was not found", status_code=404)
    project = require_project_permission(session, row.project_id, user, "write")
    response = BriefResponse.model_validate(row)
    delete_research_resource(session, project, row, user, parse_if_match(if_match))
    return response


@router.post(
    "/projects/{project_id}/research-findings",
    response_model=FindingResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "research.finding.create"},
)
def post_finding(
    project_id: uuid.UUID,
    payload: FindingCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> FindingResponse:
    return FindingResponse.model_validate(
        create_finding(session, require_project_permission(session, project_id, user, "write"), payload, user)
    )


@router.get("/projects/{project_id}/research-findings", response_model=FindingPage)
def list_findings(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> FindingPage:
    require_project(session, project_id, user)
    rows = ResearchRepository(session).list_findings(project_id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return FindingPage(
        items=[FindingResponse.model_validate(item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get("/research-findings/{finding_id}", response_model=FindingResponse)
def get_finding(
    finding_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> FindingResponse:
    row = ResearchRepository(session).finding(finding_id)
    if row is None:
        raise DomainError("research_finding_not_found", "Research finding was not found", status_code=404)
    require_project(session, row.project_id, user)
    response.headers["ETag"] = etag(row.version)
    return FindingResponse.model_validate(row)


@router.patch(
    "/research-findings/{finding_id}",
    response_model=FindingResponse,
    openapi_extra={"x-permission": "research.finding.update"},
)
def patch_finding(
    finding_id: uuid.UUID,
    payload: FindingUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> FindingResponse:
    row = ResearchRepository(session).finding(finding_id)
    if row is None:
        raise DomainError("research_finding_not_found", "Research finding was not found", status_code=404)
    project = require_project_permission(session, row.project_id, user, "write")
    updated = update_finding(session, project, row, payload, user, parse_if_match(if_match))
    response.headers["ETag"] = etag(updated.version)
    return FindingResponse.model_validate(updated)


@router.delete(
    "/research-findings/{finding_id}",
    response_model=FindingResponse,
    openapi_extra={"x-permission": "research.finding.delete"},
)
def delete_finding(
    finding_id: uuid.UUID,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> FindingResponse:
    row = ResearchRepository(session).finding(finding_id)
    if row is None:
        raise DomainError("research_finding_not_found", "Research finding was not found", status_code=404)
    project = require_project_permission(session, row.project_id, user, "write")
    response = FindingResponse.model_validate(row)
    delete_research_resource(session, project, row, user, parse_if_match(if_match))
    return response


# --- Research goal tree ------------------------------------------------------


def _require_goal(session: Session, goal_id: uuid.UUID, user: User) -> ResearchGoal:
    goal = goals.require_goal(session, goal_id)
    require_project_permission(session, goal.project_id, user, "write")
    return goal


@router.get("/projects/{project_id}/research-goals", response_model=ResearchGoalTree)
def get_research_goals(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ResearchGoalTree:
    require_project(session, project_id, user)
    rows = goals.tree(session, project_id)
    grouped = goals.links_for(session, [row.id for row in rows])
    return ResearchGoalTree(
        items=[
            ResearchGoalResponse(
                **{
                    field: getattr(row, field)
                    for field in (
                        "id", "project_id", "parent_id", "title", "detail",
                        "status", "sort_order", "tags", "version", "created_at", "updated_at",
                    )
                },
                links=[
                    ResearchGoalLinkResponse.model_validate(link) for link in grouped.get(row.id, [])
                ],
            )
            for row in rows
        ]
    )


@router.post(
    "/projects/{project_id}/research-goals",
    response_model=ResearchGoalResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "research.goal.create"},
)
def post_research_goal(
    project_id: uuid.UUID,
    payload: ResearchGoalCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ResearchGoalResponse:
    require_project_permission(session, project_id, user, "write")
    goal = goals.create_goal(
        session,
        project_id,
        user.id,
        title=payload.title,
        detail=payload.detail,
        parent_id=payload.parent_id,
        tags=payload.tags,
    )
    return ResearchGoalResponse.model_validate(goal)


@router.patch(
    "/research-goals/{goal_id}",
    response_model=ResearchGoalResponse,
    openapi_extra={"x-permission": "research.goal.update"},
)
def patch_research_goal(
    goal_id: uuid.UUID,
    payload: ResearchGoalUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ResearchGoalResponse:
    goal = _require_goal(session, goal_id, user)
    expected = parse_if_match(if_match)
    if goal.version != expected:
        raise DomainError(
            "version_conflict",
            "Goal was modified by someone else; reload before retrying.",
            status_code=412,
        )
    updated = goals.update_goal(
        session,
        goal,
        title=payload.title,
        detail=payload.detail,
        status=payload.status,
        parent_id=payload.parent_id,
        reparent=payload.reparent,
        tags=payload.tags,
    )
    response.headers["ETag"] = etag(updated.version)
    return ResearchGoalResponse.model_validate(updated)


@router.delete(
    "/research-goals/{goal_id}",
    response_model=ResearchGoalDeleteResponse,
    openapi_extra={"x-permission": "research.goal.delete"},
)
def delete_research_goal(
    goal_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ResearchGoalDeleteResponse:
    goal = _require_goal(session, goal_id, user)
    removed = goals.delete_goal(session, goal)
    return ResearchGoalDeleteResponse(id=goal_id, removed_goals=removed)


@router.post(
    "/research-goals/{goal_id}/links",
    response_model=ResearchGoalLinkResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "research.goal.update"},
)
def post_research_goal_link(
    goal_id: uuid.UUID,
    payload: ResearchGoalLinkCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ResearchGoalLinkResponse:
    goal = _require_goal(session, goal_id, user)
    link = goals.attach(
        session,
        goal,
        user.id,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        note=payload.note,
    )
    return ResearchGoalLinkResponse.model_validate(link)


@router.delete(
    "/research-goals/{goal_id}/links/{link_id}",
    response_model=ResearchGoalLinkDeleteResponse,
    openapi_extra={"x-permission": "research.goal.update"},
)
def delete_research_goal_link(
    goal_id: uuid.UUID,
    link_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ResearchGoalLinkDeleteResponse:
    goal = _require_goal(session, goal_id, user)
    goals.detach(session, goal, link_id)
    return ResearchGoalLinkDeleteResponse(id=link_id)
