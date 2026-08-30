from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.pagination import decode_cursor, encode_cursor
from ..core.problem import DomainError
from ..identity.deps import current_user, require_command
from ..identity.models import User
from .repository import ProjectRepository
from .schemas import (
    CandidateFunnelResponse,
    DeleteResponse,
    ProjectCreate,
    ProjectLibraryPage,
    ProjectOverviewResponse,
    ProjectPage,
    ProjectPromptDraftAccepted,
    ProjectPromptDraftCreate,
    ProjectPromptDraftResponse,
    ProjectResearchSummaryResponse,
    ProjectResponse,
    ProjectUpdate,
    TargetReadinessResponse,
)
from .service import (
    candidate_funnel as candidate_funnel_service,
)
from .service import (
    create_project,
    create_project_prompt_draft,
    dedupe_builtin_research_projects,
    require_project,
    require_project_prompt_draft,
    soft_delete_project,
    update_project,
)
from .service import project_library_item as project_library_item_service
from .service import (
    project_overview as project_overview_service,
)
from .service import (
    project_research_summary as project_research_summary_service,
)
from .service import (
    target_readiness as target_readiness_service,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _version_header(value: str | None) -> int:
    if not value:
        raise DomainError("precondition_required", "If-Match is required", status_code=428)
    try:
        return int(value.strip('W/"'))
    except ValueError as exc:
        raise DomainError(
            "invalid_if_match", "If-Match must contain a numeric resource version", status_code=422
        ) from exc


@router.get("", response_model=ProjectPage)
def list_projects(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ProjectPage:
    items = dedupe_builtin_research_projects(
        session,
        ProjectRepository(session).list_visible(user, after=decode_cursor(cursor), limit=1000),
    )
    has_next = len(items) > limit
    page = items[:limit]
    return ProjectPage(
        items=[ProjectResponse.model_validate(item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if has_next and page else None,
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "project.create"},
)
def post_project(
    payload: ProjectCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ProjectResponse:
    return ProjectResponse.model_validate(create_project(session, payload, user))


@router.post(
    "/prompt-drafts",
    response_model=ProjectPromptDraftAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "project.prompt_draft.create"},
)
def post_project_prompt_draft(
    payload: ProjectPromptDraftCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ProjectPromptDraftAccepted:
    return create_project_prompt_draft(session, payload, user)


@router.get("/prompt-drafts/{draft_id}", response_model=ProjectPromptDraftResponse)
def get_project_prompt_draft(
    draft_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ProjectPromptDraftResponse:
    return ProjectPromptDraftResponse.model_validate(require_project_prompt_draft(session, draft_id, user))


@router.get("/library", response_model=ProjectLibraryPage)
def project_library(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ProjectLibraryPage:
    items = dedupe_builtin_research_projects(
        session,
        ProjectRepository(session).list_visible(user, after=decode_cursor(cursor), limit=1000),
    )
    has_next = len(items) > limit
    page = items[:limit]
    return ProjectLibraryPage(
        items=[project_library_item_service(session, item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if has_next and page else None,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ProjectResponse:
    project = require_project(session, project_id, user)
    response.headers["ETag"] = f'W/"{project.version}"'
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse, openapi_extra={"x-permission": "project.update"})
def patch_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ProjectResponse:
    project = update_project(
        session, require_project(session, project_id, user), payload, user, _version_header(if_match)
    )
    response.headers["ETag"] = f'W/"{project.version}"'
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", response_model=DeleteResponse, openapi_extra={"x-permission": "project.delete"})
def delete_project(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> DeleteResponse:
    project = require_project(session, project_id, user)
    soft_delete_project(session, project, user)
    return DeleteResponse(id=project.id, deleted=True)


@router.get("/{project_id}/candidate-funnel", response_model=CandidateFunnelResponse)
def candidate_funnel(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> CandidateFunnelResponse:
    require_project(session, project_id, user)
    return candidate_funnel_service(session, project_id)


@router.get("/{project_id}/target-readiness", response_model=TargetReadinessResponse)
def target_readiness(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> TargetReadinessResponse:
    return target_readiness_service(session, require_project(session, project_id, user))


@router.get("/{project_id}/overview", response_model=ProjectOverviewResponse)
def project_overview(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ProjectOverviewResponse:
    project = require_project(session, project_id, user)
    return project_overview_service(session, project)


@router.get("/{project_id}/research-summary", response_model=ProjectResearchSummaryResponse)
def project_research_summary(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ProjectResearchSummaryResponse:
    project = require_project(session, project_id, user)
    return project_research_summary_service(session, project)
