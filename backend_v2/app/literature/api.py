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
from .models import (
    LiteratureDocument,
    LiteratureSearchRun,
    LiteratureSubscription,
)
from .repository import LiteratureRepository
from .schemas import (
    AsyncOperation,
    ChunkPage,
    ChunkResponse,
    ClaimPage,
    ClaimResponse,
    DocumentDetail,
    DocumentPage,
    DocumentResponse,
    EvidencePage,
    EvidenceResponse,
    LiteratureIngest,
    LiteratureSearchCreate,
    LiteratureSearchDetail,
    LiteratureSearchPage,
    LiteratureSearchResponse,
    RelationPage,
    RelationResponse,
    RetrievalTracePage,
    RetrievalTraceResponse,
    ReviewUpdate,
    SubscriptionCreate,
    SubscriptionPage,
    SubscriptionResponse,
    SubscriptionUpdate,
)
from .service import create_search, ingest, review_resource, subscribe, update_subscription

router = APIRouter(tags=["literature"])


@router.get("/projects/{project_id}/literature/documents", response_model=DocumentPage)
def list_documents(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> DocumentPage:
    require_project(session, project_id, user)
    rows = LiteratureRepository(session).list_documents(project_id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return DocumentPage(
        items=[DocumentResponse.model_validate(x) for x in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.post(
    "/projects/{project_id}/literature/ingestions",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "literature.ingest"},
)
def post_ingestion(
    project_id: uuid.UUID,
    payload: LiteratureIngest,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> DocumentResponse:
    return DocumentResponse.model_validate(ingest(session, require_project(session, project_id, user), payload, user))


@router.post(
    "/projects/{project_id}/literature/searches",
    response_model=LiteratureSearchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "literature.ingest"},
)
def post_search(
    project_id: uuid.UUID,
    payload: LiteratureSearchCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> LiteratureSearchResponse:
    row = create_search(session, require_project(session, project_id, user), payload, user)
    return LiteratureSearchResponse.model_validate(row)


@router.get("/projects/{project_id}/literature/searches", response_model=LiteratureSearchPage)
def list_searches(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> LiteratureSearchPage:
    require_project(session, project_id, user)
    rows = LiteratureRepository(session).list_search_runs(project_id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return LiteratureSearchPage(
        items=[LiteratureSearchResponse.model_validate(row) for row in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


def _search_run(session: Session, search_run_id: uuid.UUID, user: User) -> LiteratureSearchRun:
    row = LiteratureRepository(session).search_run(search_run_id)
    if row is None:
        raise DomainError("literature_search_not_found", "Literature search was not found", status_code=404)
    require_project(session, row.project_id, user)
    return row


@router.get("/literature/searches/{search_run_id}", response_model=LiteratureSearchDetail)
def get_search(
    search_run_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> LiteratureSearchDetail:
    row = _search_run(session, search_run_id, user)
    traces = LiteratureRepository(session).traces_for_search(row.id)
    return LiteratureSearchDetail(
        search=LiteratureSearchResponse.model_validate(row),
        traces=[RetrievalTraceResponse.model_validate(trace) for trace in traces],
    )


@router.post(
    "/projects/{project_id}/literature/subscriptions",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "literature.subscribe"},
)
def post_subscription(
    project_id: uuid.UUID,
    payload: SubscriptionCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> SubscriptionResponse:
    return SubscriptionResponse.model_validate(
        subscribe(session, require_project(session, project_id, user), payload, user)
    )


def _document(session: Session, document_id: uuid.UUID, user: User) -> LiteratureDocument:
    row = LiteratureRepository(session).document(document_id)
    if row is None:
        raise DomainError("literature_document_not_found", "Literature document was not found", status_code=404)
    require_project(session, row.project_id, user)
    return row


@router.get("/literature/documents/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> DocumentDetail:
    document = _document(session, document_id, user)
    chunks, claims, evidence = LiteratureRepository(session).document_detail(document.id)
    return DocumentDetail(
        document=DocumentResponse.model_validate(document),
        chunks=[ChunkResponse.model_validate(row) for row in chunks],
        claims=[ClaimResponse.model_validate(row) for row in claims],
        evidence=[EvidenceResponse.model_validate(row) for row in evidence],
    )


@router.get("/literature/chunks/{chunk_id}", response_model=ChunkResponse)
def get_chunk(
    chunk_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ChunkResponse:
    row = LiteratureRepository(session).chunk(chunk_id)
    if row is None:
        raise DomainError("literature_chunk_not_found", "Literature chunk was not found", status_code=404)
    _document(session, row.document_id, user)
    response.headers["ETag"] = etag(row.version)
    return ChunkResponse.model_validate(row)


@router.get("/literature/documents/{document_id}/chunks", response_model=ChunkPage)
def list_chunks(
    document_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ChunkPage:
    _document(session, document_id, user)
    after = decode_cursor(cursor)
    rows = LiteratureRepository(session).list_chunks(document_id, after, limit)
    page = rows[:limit]
    return ChunkPage(
        items=[ChunkResponse.model_validate(row) for row in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get("/literature/documents/{document_id}/retrieval-traces", response_model=RetrievalTracePage)
def list_document_retrieval_traces(
    document_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> RetrievalTracePage:
    _document(session, document_id, user)
    rows = LiteratureRepository(session).list_document_traces(document_id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return RetrievalTracePage(
        items=[RetrievalTraceResponse.model_validate(row) for row in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get("/literature/claims/{claim_id}", response_model=ClaimResponse)
def get_claim(
    claim_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ClaimResponse:
    row = LiteratureRepository(session).claim(claim_id)
    if row is None:
        raise DomainError("literature_claim_not_found", "Literature claim was not found", status_code=404)
    _document(session, row.document_id, user)
    response.headers["ETag"] = etag(row.version)
    return ClaimResponse.model_validate(row)


@router.get("/literature/claims/{claim_id}/evidence", response_model=EvidencePage)
def list_evidence(
    claim_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> EvidencePage:
    claim = LiteratureRepository(session).claim(claim_id)
    if claim is None:
        raise DomainError("literature_claim_not_found", "Literature claim was not found", status_code=404)
    _document(session, claim.document_id, user)
    after = decode_cursor(cursor)
    rows = LiteratureRepository(session).list_evidence(claim_id, after, limit)
    page = rows[:limit]
    return EvidencePage(
        items=[EvidenceResponse.model_validate(row) for row in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get("/literature/evidence/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(
    evidence_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> EvidenceResponse:
    repository = LiteratureRepository(session)
    row = repository.evidence(evidence_id)
    if row is None:
        raise DomainError("literature_evidence_not_found", "Literature evidence was not found", status_code=404)
    claim = repository.claim(row.claim_id)
    if claim is None:
        raise DomainError("literature_claim_not_found", "Literature claim was not found", status_code=404)
    _document(session, claim.document_id, user)
    response.headers["ETag"] = etag(row.version)
    return EvidenceResponse.model_validate(row)


@router.get("/projects/{project_id}/literature/claims", response_model=ClaimPage)
def list_claims(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    review_status: str | None = Query(default=None),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ClaimPage:
    require_project(session, project_id, user)
    after = decode_cursor(cursor)
    rows = LiteratureRepository(session).list_claims(project_id, after, limit, review_status)
    page = rows[:limit]
    return ClaimPage(
        items=[ClaimResponse.model_validate(row) for row in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.patch(
    "/literature/claims/{claim_id}",
    response_model=ClaimResponse,
    openapi_extra={"x-permission": "literature.review"},
)
def review_claim(
    claim_id: uuid.UUID,
    payload: ReviewUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ClaimResponse:
    row = LiteratureRepository(session).claim(claim_id)
    if row is None:
        raise DomainError("literature_claim_not_found", "Literature claim was not found", status_code=404)
    _document(session, row.document_id, user)
    review_resource(row, payload, parse_if_match(if_match), user)
    response.headers["ETag"] = etag(row.version)
    return ClaimResponse.model_validate(row)


@router.get("/projects/{project_id}/literature/relations", response_model=RelationPage)
def list_relations(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    review_status: str | None = Query(default=None),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> RelationPage:
    require_project(session, project_id, user)
    after = decode_cursor(cursor)
    rows = LiteratureRepository(session).list_relations(project_id, after, limit, review_status)
    page = rows[:limit]
    return RelationPage(
        items=[RelationResponse.model_validate(row) for row in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.post(
    "/projects/{project_id}/literature/relation-detections",
    response_model=AsyncOperation,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "literature.detect_relations"},
)
def detect_relations(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> AsyncOperation:
    project = require_project(session, project_id, user)
    operation = enqueue_operation(
        session,
        topic="literature.relations.detect",
        resource_type="project",
        resource_id=project_id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
    )
    return AsyncOperation(id=operation.id)


@router.get("/literature/relations/{relation_id}", response_model=RelationResponse)
def get_relation(
    relation_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> RelationResponse:
    row = LiteratureRepository(session).relation(relation_id)
    if row is None:
        raise DomainError("literature_relation_not_found", "Literature relation was not found", status_code=404)
    require_project(session, row.project_id, user)
    response.headers["ETag"] = etag(row.version)
    return RelationResponse.model_validate(row)


@router.patch(
    "/literature/relations/{relation_id}",
    response_model=RelationResponse,
    openapi_extra={"x-permission": "literature.review"},
)
def review_relation(
    relation_id: uuid.UUID,
    payload: ReviewUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> RelationResponse:
    row = LiteratureRepository(session).relation(relation_id)
    if row is None:
        raise DomainError("literature_relation_not_found", "Literature relation was not found", status_code=404)
    require_project(session, row.project_id, user)
    review_resource(row, payload, parse_if_match(if_match), user)
    response.headers["ETag"] = etag(row.version)
    return RelationResponse.model_validate(row)


@router.get("/projects/{project_id}/literature/subscriptions", response_model=SubscriptionPage)
def list_subscriptions(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> SubscriptionPage:
    require_project(session, project_id, user)
    rows = LiteratureRepository(session).list_subscriptions(project_id)
    return SubscriptionPage(items=[SubscriptionResponse.model_validate(row) for row in rows])


def _subscription(session: Session, subscription_id: uuid.UUID, user: User) -> LiteratureSubscription:
    row = LiteratureRepository(session).subscription(subscription_id)
    if row is None:
        raise DomainError("literature_subscription_not_found", "Subscription was not found", status_code=404)
    require_project(session, row.project_id, user)
    return row


@router.get("/literature/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
def get_subscription(
    subscription_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> SubscriptionResponse:
    row = _subscription(session, subscription_id, user)
    response.headers["ETag"] = etag(row.version)
    return SubscriptionResponse.model_validate(row)


@router.patch(
    "/literature/subscriptions/{subscription_id}",
    response_model=SubscriptionResponse,
    openapi_extra={"x-permission": "literature.subscribe"},
)
def patch_subscription(
    subscription_id: uuid.UUID,
    payload: SubscriptionUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> SubscriptionResponse:
    row = _subscription(session, subscription_id, user)
    update_subscription(row, payload, parse_if_match(if_match))
    response.headers["ETag"] = etag(row.version)
    return SubscriptionResponse.model_validate(row)


@router.post(
    "/literature/subscriptions/{subscription_id}/runs",
    response_model=AsyncOperation,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "literature.subscribe"},
)
def run_subscription(
    subscription_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> AsyncOperation:
    row = _subscription(session, subscription_id, user)
    project = require_project(session, row.project_id, user)
    operation = enqueue_operation(
        session,
        topic="literature.subscription.run",
        resource_type="literature_subscription",
        resource_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
    )
    return AsyncOperation(id=operation.id)
