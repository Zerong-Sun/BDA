from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.etag import etag, parse_if_match
from ..core.pagination import decode_cursor, encode_cursor
from ..core.problem import DomainError
from ..identity.deps import current_user, require_command
from ..identity.models import User
from ..platform.operations import enqueue_operation
from ..projects.service import require_project
from ..workflows.schemas import WorkflowResponse
from .models import DesignRoute, IntelligenceEvidence, IntelligenceHotspot, IntelligenceReport, IntelligenceRun
from .repository import IntelligenceRepository
from .schemas import (
    EvidenceResponse,
    EvidenceReview,
    ExportResponse,
    HotspotResponse,
    HotspotReview,
    IntelligenceCreate,
    IntelligenceDetail,
    IntelligencePage,
    IntelligenceResponse,
    ReportResponse,
    ReportReview,
    RouteResponse,
)
from .service import (
    apply_route,
    create_run,
)
from .service import (
    review_evidence as review_evidence_service,
)
from .service import (
    review_hotspot as review_hotspot_service,
)
from .service import (
    review_report as review_report_service,
)

router = APIRouter(tags=["intelligence"])


def _run(session: Session, run_id: uuid.UUID, user: User) -> IntelligenceRun:
    row = IntelligenceRepository(session).run(run_id)
    if row is None:
        raise DomainError("intelligence_run_not_found", "Intelligence run was not found", status_code=404)
    require_project(session, row.project_id, user)
    return row


@router.get("/projects/{project_id}/intelligence-runs", response_model=IntelligencePage)
def list_runs(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> IntelligencePage:
    require_project(session, project_id, user)
    rows = IntelligenceRepository(session).list_project(project_id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return IntelligencePage(
        items=[IntelligenceResponse.model_validate(x) for x in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.post(
    "/projects/{project_id}/intelligence-runs",
    response_model=IntelligenceResponse,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "intelligence.run"},
)
def post_run(
    project_id: uuid.UUID,
    payload: IntelligenceCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> IntelligenceResponse:
    return IntelligenceResponse.model_validate(
        create_run(session, require_project(session, project_id, user), payload, user)
    )


@router.get("/intelligence-runs/{run_id}", response_model=IntelligenceDetail)
def get_run(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> IntelligenceDetail:
    row = _run(session, run_id, user)
    report, evidence, hotspots, routes = IntelligenceRepository(session).detail(row.id)
    return IntelligenceDetail(
        run=IntelligenceResponse.model_validate(row),
        report=ReportResponse.model_validate(report) if report else None,
        evidence=[EvidenceResponse.model_validate(item) for item in evidence],
        hotspots=[HotspotResponse.model_validate(item) for item in hotspots],
        routes=[RouteResponse.model_validate(item) for item in routes],
    )


def _report(session: Session, report_id: uuid.UUID, user: User) -> IntelligenceReport:
    row = IntelligenceRepository(session).report(report_id)
    if row is None:
        raise DomainError("intelligence_report_not_found", "Report was not found", status_code=404)
    _run(session, row.run_id, user)
    return row


@router.get("/intelligence-reports/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ReportResponse:
    row = _report(session, report_id, user)
    response.headers["ETag"] = etag(row.version)
    return ReportResponse.model_validate(row)


def _evidence(session: Session, evidence_id: uuid.UUID, user: User) -> IntelligenceEvidence:
    row = IntelligenceRepository(session).evidence(evidence_id)
    if row is None:
        raise DomainError("intelligence_evidence_not_found", "Evidence was not found", status_code=404)
    _run(session, row.run_id, user)
    return row


@router.get("/intelligence-evidence/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(
    evidence_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> EvidenceResponse:
    row = _evidence(session, evidence_id, user)
    response.headers["ETag"] = etag(row.version)
    return EvidenceResponse.model_validate(row)


def _hotspot(session: Session, hotspot_id: uuid.UUID, user: User) -> IntelligenceHotspot:
    row = IntelligenceRepository(session).hotspot(hotspot_id)
    if row is None:
        raise DomainError("intelligence_hotspot_not_found", "Hotspot was not found", status_code=404)
    _run(session, row.run_id, user)
    return row


@router.get("/intelligence-hotspots/{hotspot_id}", response_model=HotspotResponse)
def get_hotspot(
    hotspot_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> HotspotResponse:
    row = _hotspot(session, hotspot_id, user)
    response.headers["ETag"] = etag(row.version)
    return HotspotResponse.model_validate(row)


def _route(session: Session, route_id: uuid.UUID, user: User) -> DesignRoute:
    row = IntelligenceRepository(session).route(route_id)
    if row is None:
        raise DomainError("design_route_not_found", "Design route was not found", status_code=404)
    _run(session, row.run_id, user)
    return row


@router.get("/design-routes/{route_id}", response_model=RouteResponse)
def get_route(
    route_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> RouteResponse:
    row = _route(session, route_id, user)
    response.headers["ETag"] = etag(row.version)
    return RouteResponse.model_validate(row)


@router.patch(
    "/intelligence-reports/{report_id}",
    response_model=ReportResponse,
    openapi_extra={"x-permission": "intelligence.review"},
)
def review_report(
    report_id: uuid.UUID,
    payload: ReportReview,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ReportResponse:
    report = _report(session, report_id, user)
    review_report_service(report, payload, parse_if_match(if_match))
    response.headers["ETag"] = etag(report.version)
    return ReportResponse.model_validate(report)


@router.post(
    "/design-routes/{route_id}/apply",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "intelligence.apply_route"},
)
def post_apply_route(
    route_id: uuid.UUID, session: Session = Depends(get_session), user: User = Depends(require_command)
) -> WorkflowResponse:
    route = _route(session, route_id, user)
    return WorkflowResponse.model_validate(apply_route(session, route, _run(session, route.run_id, user), user))


@router.post(
    "/intelligence-runs/{run_id}/exports",
    response_model=ExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "intelligence.export"},
)
def post_export(
    run_id: uuid.UUID, session: Session = Depends(get_session), user: User = Depends(require_command)
) -> ExportResponse:
    row = _run(session, run_id, user)
    project = require_project(session, row.project_id, user)
    operation = enqueue_operation(
        session,
        topic="intelligence.export",
        resource_type="intelligence_run",
        resource_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"run_id": str(row.id)},
    )
    return ExportResponse(run_id=row.id, operation_id=operation.id)


@router.patch(
    "/intelligence-evidence/{evidence_id}",
    response_model=EvidenceResponse,
    openapi_extra={"x-permission": "intelligence.review"},
)
def review_evidence(
    evidence_id: uuid.UUID,
    payload: EvidenceReview,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> EvidenceResponse:
    row = _evidence(session, evidence_id, user)
    review_evidence_service(row, payload, parse_if_match(if_match))
    response.headers["ETag"] = etag(row.version)
    return EvidenceResponse.model_validate(row)


@router.patch(
    "/intelligence-hotspots/{hotspot_id}",
    response_model=HotspotResponse,
    openapi_extra={"x-permission": "intelligence.review"},
)
def review_hotspot(
    hotspot_id: uuid.UUID,
    payload: HotspotReview,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> HotspotResponse:
    row = _hotspot(session, hotspot_id, user)
    review_hotspot_service(row, payload, parse_if_match(if_match))
    response.headers["ETag"] = etag(row.version)
    return HotspotResponse.model_validate(row)
