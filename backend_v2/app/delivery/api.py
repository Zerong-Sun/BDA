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
from .repository import DeliveryRepository
from .schemas import DeliveryAccepted, DeliveryCreate, DeliveryPage, DeliveryResponse, ResultSummary
from .service import create_delivery, result_summary

router = APIRouter(tags=["delivery"])


@router.get("/projects/{project_id}/result-summary", response_model=ResultSummary)
def get_result_summary(
    project_id: uuid.UUID, session: Session = Depends(get_session), user: User = Depends(current_user)
) -> ResultSummary:
    return result_summary(session, require_project(session, project_id, user))


@router.get("/projects/{project_id}/delivery-packages", response_model=DeliveryPage)
def list_delivery(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> DeliveryPage:
    require_project(session, project_id, user)
    rows = DeliveryRepository(session).list_project(project_id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return DeliveryPage(
        items=[DeliveryResponse.model_validate(row) for row in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get("/delivery-packages/{package_id}", response_model=DeliveryResponse)
def get_delivery(
    package_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> DeliveryResponse:
    package = DeliveryRepository(session).get(package_id)
    if package is None:
        raise DomainError("delivery_package_not_found", "Delivery package was not found", status_code=404)
    require_project(session, package.project_id, user)
    response.headers["ETag"] = f'W/"{package.version}"'
    return DeliveryResponse.model_validate(package)


@router.post(
    "/projects/{project_id}/delivery-packages",
    response_model=DeliveryAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "delivery.create"},
)
def post_delivery(
    project_id: uuid.UUID,
    payload: DeliveryCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> DeliveryAccepted:
    project = require_project(session, project_id, user)
    package, operation = create_delivery(session, project, payload, user)
    return DeliveryAccepted(
        operation_id=operation.id,
        delivery_package=DeliveryResponse.model_validate(package),
    )
