from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..core.problem import DomainError
from ..identity.models import User
from ..platform.operations import enqueue_operation
from ..projects.models import Project
from .models import (
    LiteratureClaim,
    LiteratureDocument,
    LiteratureRelation,
    LiteratureSearchRun,
    LiteratureSubscription,
)
from .schemas import (
    LiteratureIngest,
    LiteratureSearchCreate,
    ReviewUpdate,
    SubscriptionCreate,
    SubscriptionUpdate,
)


def ingest(session: Session, project: Project, payload: LiteratureIngest, user: User) -> LiteratureDocument:
    values = payload.model_dump(exclude={"metadata"})
    row = LiteratureDocument(project_id=project.id, metadata_json=payload.metadata, **values)
    session.add(row)
    session.flush()
    enqueue_operation(
        session,
        topic="literature.ingest",
        resource_type="literature_document",
        resource_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"document_id": str(row.id)},
    )
    return row


def subscribe(session: Session, project: Project, payload: SubscriptionCreate, user: User) -> LiteratureSubscription:
    row = LiteratureSubscription(project_id=project.id, created_by=user.id, **payload.model_dump())
    session.add(row)
    session.flush()
    enqueue_operation(
        session,
        topic="literature.subscription.run",
        resource_type="literature_subscription",
        resource_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"subscription_id": str(row.id)},
    )
    return row


def create_search(
    session: Session,
    project: Project,
    payload: LiteratureSearchCreate,
    user: User,
) -> LiteratureSearchRun:
    row = LiteratureSearchRun(
        project_id=project.id,
        query=payload.query,
        sources=list(payload.sources),
        requested_limit=payload.limit,
        fetch_full_text=payload.fetch_full_text,
        extract_claims=payload.extract_claims,
        created_by=user.id,
    )
    session.add(row)
    session.flush()
    enqueue_operation(
        session,
        topic="literature.search",
        resource_type="literature_search",
        resource_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"search_run_id": str(row.id)},
    )
    return row


def review_resource(
    row: LiteratureClaim | LiteratureRelation,
    payload: ReviewUpdate,
    expected_version: int,
    user: User,
):
    if row.version != expected_version:
        raise DomainError("version_conflict", "Literature resource was modified", status_code=412)
    row.review_status = payload.review_status
    row.reviewed_by = user.id
    row.reviewed_at = datetime.now(UTC)
    row.version += 1
    return row


def update_subscription(
    row: LiteratureSubscription, payload: SubscriptionUpdate, expected_version: int
) -> LiteratureSubscription:
    if row.version != expected_version:
        raise DomainError("version_conflict", "Literature subscription was modified", status_code=412)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    row.version += 1
    return row
