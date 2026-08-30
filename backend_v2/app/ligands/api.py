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
from .catalog import LIGANDS
from .repository import LigandRepository
from .schemas import (
    LigandCatalogItem,
    LigandImportAccepted,
    LigandImportCreate,
    LigandImportPage,
    LigandImportResponse,
)
from .service import create_import

router = APIRouter(tags=["ligands"])


@router.get("/ligands", response_model=list[LigandCatalogItem])
def list_ligands(
    query: str | None = Query(default=None), user: User = Depends(current_user)
) -> list[LigandCatalogItem]:
    term = (query or "").strip().lower()
    return [
        LigandCatalogItem(
            id=ligand_id,
            name=str(item["name"]),
            source="pubchem",
            metadata={"cid": item["cid"]},
        )
        for ligand_id, item in LIGANDS.items()
        if not term or term in ligand_id or term in str(item["name"]).lower()
    ]


@router.post(
    "/projects/{project_id}/ligand-imports",
    response_model=LigandImportAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "ligand.import"},
)
def post_ligand_import(
    project_id: uuid.UUID,
    payload: LigandImportCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> LigandImportAccepted:
    row, operation = create_import(session, require_project(session, project_id, user), payload, user)
    return LigandImportAccepted(
        operation_id=operation.id,
        ligand_import=LigandImportResponse.model_validate(row),
    )


@router.get("/projects/{project_id}/ligand-imports", response_model=LigandImportPage)
def list_ligand_imports(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> LigandImportPage:
    require_project(session, project_id, user)
    rows = LigandRepository(session).list_project(project_id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return LigandImportPage(
        items=[LigandImportResponse.model_validate(item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get("/ligand-imports/{import_id}", response_model=LigandImportResponse)
def get_ligand_import(
    import_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> LigandImportResponse:
    row = LigandRepository(session).get(import_id)
    if row is None:
        raise DomainError("ligand_import_not_found", "Ligand import was not found", status_code=404)
    require_project(session, row.project_id, user)
    response.headers["ETag"] = f'W/"{row.version}"'
    return LigandImportResponse.model_validate(row)
