from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.pagination import decode_cursor, encode_cursor
from ..core.problem import DomainError
from ..identity.deps import current_user, require_command
from ..identity.models import User
from ..projects.service import require_project
from .repository import ArtifactRepository
from .schemas import (
    ArtifactLineageEdgeResponse,
    ArtifactLineageResponse,
    ArtifactPage,
    ArtifactResponse,
    UploadComplete,
    UploadCreate,
    UploadResponse,
)
from .service import complete_upload, create_upload
from .storage import ObjectStorage

router = APIRouter(tags=["artifacts"])


def _response(item, *, with_url: bool = False) -> ArtifactResponse:
    response = ArtifactResponse.model_validate(item)
    if with_url and item.status == "available":
        response.download_url = ObjectStorage().download_url(item.object_key)
    return response


@router.post(
    "/artifact-uploads",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "artifact.upload"},
)
def post_upload(
    payload: UploadCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> UploadResponse:
    project = require_project(session, payload.project_id, user)
    upload, url = create_upload(session, project, payload, user)
    return UploadResponse(
        id=upload.id,
        project_id=upload.project_id,
        status=upload.status,
        upload_url=url,
        expires_at=upload.expires_at,
        required_headers={"Content-Type": upload.content_type},
    )


@router.post(
    "/artifact-uploads/{upload_id}/complete",
    response_model=ArtifactResponse,
    openapi_extra={"x-permission": "artifact.upload.complete"},
)
def post_complete(
    upload_id: uuid.UUID,
    payload: UploadComplete,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ArtifactResponse:
    upload = ArtifactRepository(session).upload(upload_id, for_update=True)
    if upload is None:
        raise DomainError("upload_not_found", "Artifact upload was not found", status_code=404)
    project = require_project(session, upload.project_id, user)
    return _response(complete_upload(session, upload, payload, project, user), with_url=True)


@router.get("/artifacts", response_model=ArtifactPage)
def list_artifacts(
    project_id: uuid.UUID,
    artifact_type: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ArtifactPage:
    require_project(session, project_id, user)
    items = ArtifactRepository(session).list_project(
        project_id,
        after=decode_cursor(cursor),
        limit=limit,
        artifact_type=artifact_type,
    )
    has_next = len(items) > limit
    page = items[:limit]
    return ArtifactPage(
        items=[_response(item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if has_next and page else None,
    )


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
def get_artifact(
    artifact_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ArtifactResponse:
    item = ArtifactRepository(session).artifact(artifact_id)
    if item is None:
        raise DomainError("artifact_not_found", "Artifact was not found", status_code=404)
    require_project(session, item.project_id, user)
    response.headers["ETag"] = f'W/"{item.version}"'
    return _response(item, with_url=True)


@router.get("/artifacts/{artifact_id}/lineage", response_model=ArtifactLineageResponse)
def get_artifact_lineage(
    artifact_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ArtifactLineageResponse:
    repository = ArtifactRepository(session)
    item = repository.artifact(artifact_id)
    if item is None:
        raise DomainError("artifact_not_found", "Artifact was not found", status_code=404)
    require_project(session, item.project_id, user)
    upstream, downstream = repository.lineage(item.id)
    return ArtifactLineageResponse(
        artifact=_response(item),
        upstream=[ArtifactLineageEdgeResponse.model_validate(edge) for edge in upstream],
        downstream=[ArtifactLineageEdgeResponse.model_validate(edge) for edge in downstream],
    )
