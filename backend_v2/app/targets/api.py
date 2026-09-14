from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from ..artifacts.repository import ArtifactRepository
from ..core.database import get_session
from ..core.pagination import decode_cursor, encode_cursor
from ..core.problem import DomainError
from ..identity.deps import current_user, require_command
from ..identity.models import User
from ..platform.operations import enqueue_operation
from ..projects.service import require_project
from . import hotspots
from .repository import TargetRepository
from .schemas import (
    HotspotSetCreate,
    HotspotSetPage,
    HotspotSetRejection,
    HotspotSetResponse,
    PrimaryTargetUpdate,
    TargetPage,
    TargetResponse,
    TargetStructureAttach,
    TargetStructureImport,
    TargetStructureImportAccepted,
    TargetStructurePrepare,
    TargetStructureReview,
    TargetStructureRevisionPage,
    TargetStructureRevisionResponse,
    TargetStructureView,
    TargetUpdate,
    TargetUpsert,
)
from .service import (
    attach_structure,
    create_target,
    mark_structure_importing,
    prepare_structure_revision,
    review_structure_revision,
    select_primary_target,
    update_target,
)

router = APIRouter(tags=["targets"])


def _version(value: str | None) -> int:
    if not value:
        raise DomainError("precondition_required", "If-Match is required", status_code=428)
    try:
        return int(value.strip('W/"'))
    except ValueError as exc:
        raise DomainError(
            "invalid_if_match", "If-Match must contain a numeric resource version", status_code=422
        ) from exc


@router.get("/projects/{project_id}/targets", response_model=TargetPage)
def list_targets(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> TargetPage:
    require_project(session, project_id, user)
    rows = TargetRepository(session).list_project(project_id, after=decode_cursor(cursor), limit=limit)
    page = rows[:limit]
    return TargetPage(
        items=[TargetResponse.model_validate(row) for row in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.post(
    "/projects/{project_id}/targets",
    response_model=TargetResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "target.create"},
)
def post_target(
    project_id: uuid.UUID,
    payload: TargetUpsert,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> TargetResponse:
    return TargetResponse.model_validate(
        create_target(session, require_project(session, project_id, user), payload, user)
    )


@router.get("/targets/{target_id}", response_model=TargetResponse)
def get_target(
    target_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> TargetResponse:
    target = TargetRepository(session).get(target_id)
    if target is None:
        raise DomainError("target_not_found", "Target was not found", status_code=404)
    require_project(session, target.project_id, user)
    response.headers["ETag"] = f'W/"{target.version}"'
    return TargetResponse.model_validate(target)


@router.patch("/targets/{target_id}", response_model=TargetResponse, openapi_extra={"x-permission": "target.update"})
def patch_target(
    target_id: uuid.UUID,
    payload: TargetUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> TargetResponse:
    target = TargetRepository(session).get(target_id)
    if target is None:
        raise DomainError("target_not_found", "Target was not found", status_code=404)
    project = require_project(session, target.project_id, user)
    updated = update_target(session, project, target, payload, user, _version(if_match))
    response.headers["ETag"] = f'W/"{updated.version}"'
    return TargetResponse.model_validate(updated)


@router.put(
    "/projects/{project_id}/primary-target",
    response_model=TargetResponse,
    openapi_extra={"x-permission": "target.select_primary"},
)
def put_primary_target(
    project_id: uuid.UUID,
    payload: PrimaryTargetUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> TargetResponse:
    project = require_project(session, project_id, user)
    target = TargetRepository(session).get(payload.target_id)
    if target is None or target.project_id != project.id:
        raise DomainError("target_not_found", "Target does not belong to this project", status_code=404)
    select_primary_target(project, target)
    return TargetResponse.model_validate(target)


@router.get("/projects/{project_id}/primary-target", response_model=TargetResponse)
def get_primary_target(
    project_id: uuid.UUID, session: Session = Depends(get_session), user: User = Depends(current_user)
) -> TargetResponse:
    project = require_project(session, project_id, user)
    target = TargetRepository(session).get(project.primary_target_id) if project.primary_target_id else None
    if target is None:
        raise DomainError("target_not_found", "Project has no primary target", status_code=404)
    return TargetResponse.model_validate(target)


def _target(session: Session, target_id: uuid.UUID, user: User):
    target = TargetRepository(session).get(target_id)
    if target is None:
        raise DomainError("target_not_found", "Target was not found", status_code=404)
    project = require_project(session, target.project_id, user)
    return target, project


@router.put(
    "/targets/{target_id}/structure-artifact",
    response_model=TargetResponse,
    openapi_extra={"x-permission": "target.structure.attach"},
)
def attach_structure_artifact(
    target_id: uuid.UUID,
    payload: TargetStructureAttach,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> TargetResponse:
    target, _ = _target(session, target_id, user)
    artifact = ArtifactRepository(session).artifact(payload.artifact_id)
    if artifact is None or artifact.project_id != target.project_id or artifact.status != "available":
        raise DomainError("artifact_not_found", "Available project artifact was not found", status_code=404)
    attach_structure(target, artifact, _version(if_match))
    response.headers["ETag"] = f'W/"{target.version}"'
    return TargetResponse.model_validate(target)


@router.post(
    "/targets/{target_id}/structure-imports",
    response_model=TargetStructureImportAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "target.structure.import"},
)
def import_target_structure(
    target_id: uuid.UUID,
    payload: TargetStructureImport,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> TargetStructureImportAccepted:
    target, project = _target(session, target_id, user)
    if payload.source == "pdb" and not payload.pdb_id:
        raise DomainError("pdb_id_required", "pdb_id is required for a PDB import", status_code=422)
    if payload.source == "artifact" and not payload.artifact_id:
        raise DomainError("artifact_id_required", "artifact_id is required for an artifact import", status_code=422)
    operation = enqueue_operation(
        session,
        topic="target.structure.import",
        resource_type="target",
        resource_id=target.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"target_id": str(target.id), **payload.model_dump(mode="json")},
    )
    if payload.attach_to_target:
        mark_structure_importing(target)
    return TargetStructureImportAccepted(operation_id=operation.id, target_id=target.id)


@router.get(
    "/targets/{target_id}/structure-revisions",
    response_model=TargetStructureRevisionPage,
)
def list_structure_revisions(
    target_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> TargetStructureRevisionPage:
    target, _ = _target(session, target_id, user)
    after = decode_cursor(cursor)
    rows = TargetRepository(session).list_revisions(target.id, after=after, limit=limit)
    page = rows[:limit]
    return TargetStructureRevisionPage(
        items=[TargetStructureRevisionResponse.model_validate(row) for row in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get(
    "/target-structure-revisions/{revision_id}",
    response_model=TargetStructureRevisionResponse,
)
def get_structure_revision(
    revision_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> TargetStructureRevisionResponse:
    revision = TargetRepository(session).revision(revision_id)
    if revision is None:
        raise DomainError("structure_revision_not_found", "Structure revision was not found", status_code=404)
    _target(session, revision.target_id, user)
    response.headers["ETag"] = f'W/"{revision.version}"'
    return TargetStructureRevisionResponse.model_validate(revision)


@router.get("/targets/{target_id}/structure", response_model=TargetStructureView)
def get_target_structure(
    target_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> TargetStructureView:
    target, _ = _target(session, target_id, user)
    latest, approved = TargetRepository(session).structure_state(target.id)
    return TargetStructureView(
        target_id=target.id,
        structure_status=target.structure_status,
        current_artifact_id=target.structure_artifact_id,
        approved_revision_id=approved,
        latest_revision=TargetStructureRevisionResponse.model_validate(latest) if latest else None,
    )


@router.post(
    "/targets/{target_id}/structure-revisions",
    response_model=TargetStructureRevisionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "target.structure.prepare"},
)
def prepare_structure(
    target_id: uuid.UUID,
    payload: TargetStructurePrepare,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> TargetStructureRevisionResponse:
    target, project = _target(session, target_id, user)
    artifact = ArtifactRepository(session).artifact(payload.source_artifact_id)
    if artifact is None or artifact.project_id != target.project_id or artifact.status != "available":
        raise DomainError("artifact_not_found", "Available project artifact was not found", status_code=404)
    revision = prepare_structure_revision(session, target, project, artifact, payload, user)
    return TargetStructureRevisionResponse.model_validate(revision)


@router.post(
    "/target-structure-revisions/{revision_id}/review",
    response_model=TargetStructureRevisionResponse,
    openapi_extra={"x-permission": "target.structure.review"},
)
def review_structure(
    revision_id: uuid.UUID,
    payload: TargetStructureReview,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> TargetStructureRevisionResponse:
    revision = TargetRepository(session).revision(revision_id)
    if revision is None:
        raise DomainError("structure_revision_not_found", "Structure revision was not found", status_code=404)
    target, _ = _target(session, revision.target_id, user)
    review_structure_revision(revision, target, payload, _version(if_match))
    response.headers["ETag"] = f'W/"{revision.version}"'
    return TargetStructureRevisionResponse.model_validate(revision)



# --- Hotspot sets ------------------------------------------------------------
#
# Which residues a design targets, as an object rather than a sentence. The
# split below is the whole point: an operator proposes through its tool and can
# never confirm, a person confirms here and only a confirmed set may reach a
# job.


def _hotspot_set(session: Session, hotspot_set_id: uuid.UUID, user: User):
    row = hotspots.require(session, hotspot_set_id)
    require_project(session, row.project_id, user)
    return row


@router.get("/projects/{project_id}/hotspot-sets", response_model=HotspotSetPage)
def list_hotspot_sets(
    project_id: uuid.UUID,
    target_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status", max_length=24),
    limit: int = Query(default=hotspots.DEFAULT_LIMIT, ge=1, le=hotspots.MAX_LIMIT),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> HotspotSetPage:
    """Hotspot sets in this project, newest first.

    Proposed, confirmed and rejected are all returned: a set that was considered
    and refused is part of the record, and a list that hid it would make the
    same proposal look new the second time.
    """
    require_project(session, project_id, user)
    rows = hotspots.sets(
        session, project_id=project_id, target_id=target_id, status=status_filter, limit=limit
    )
    return HotspotSetPage(items=[HotspotSetResponse.model_validate(row) for row in rows])


@router.post(
    "/targets/{target_id}/hotspot-sets",
    response_model=HotspotSetResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "target.update"},
)
def create_hotspot_set(
    target_id: uuid.UUID,
    payload: HotspotSetCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> HotspotSetResponse:
    """A set a person picked, confirmed on arrival.

    There is no `origin` field on the payload. A client that could send one
    could mint a confirmed set on an operator's behalf, which is exactly what
    the column exists to distinguish.
    """
    target = TargetRepository(session).get(target_id)
    if target is None:
        raise DomainError("target_not_found", "Target was not found", status_code=404)
    require_project(session, target.project_id, user)
    row = hotspots.record(
        session,
        project_id=target.project_id,
        target_id=target.id,
        user_id=user.id,
        label=payload.label,
        residues=[residue.model_dump(exclude_none=True) for residue in payload.residues],
        origin="human",
        structure_artifact_id=payload.structure_artifact_id,
        rationale=payload.rationale,
        evidence_refs=payload.evidence_refs,
    )
    return HotspotSetResponse.model_validate(row)


@router.post(
    "/hotspot-sets/{hotspot_set_id}/confirmations",
    response_model=HotspotSetResponse,
    openapi_extra={"x-permission": "target.update"},
)
def confirm_hotspot_set(
    hotspot_set_id: uuid.UUID,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> HotspotSetResponse:
    """A person takes responsibility for this set; only then can a job use it."""
    row = _hotspot_set(session, hotspot_set_id, user)
    if _version(if_match) != row.version:
        raise DomainError(
            "version_conflict", "Reload the hotspot set before confirming it.", status_code=412
        )
    hotspots.confirm(session, row, user=user)
    return HotspotSetResponse.model_validate(row)


@router.post(
    "/hotspot-sets/{hotspot_set_id}/rejections",
    response_model=HotspotSetResponse,
    openapi_extra={"x-permission": "target.update"},
)
def reject_hotspot_set(
    hotspot_set_id: uuid.UUID,
    payload: HotspotSetRejection,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> HotspotSetResponse:
    """Refuse a proposal, keeping it and the reason in the record."""
    row = _hotspot_set(session, hotspot_set_id, user)
    if _version(if_match) != row.version:
        raise DomainError(
            "version_conflict", "Reload the hotspot set before rejecting it.", status_code=412
        )
    hotspots.reject(session, row, user=user, reason=payload.reason)
    return HotspotSetResponse.model_validate(row)
