from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from ..core.database import SessionFactory, get_session
from ..core.pagination import decode_cursor, encode_cursor
from ..core.problem import DomainError
from ..core.sse import observed_sse
from ..identity.deps import current_user, require_command, streaming_user
from ..identity.models import User
from ..projects.service import require_project, require_project_permission
from ..workflows.repository import WorkflowRepository
from .repository import ComputeRepository
from .schemas import (
    CancelResponse,
    ComputeDraftCreate,
    ComputeDraftPage,
    ComputeDraftResponse,
    JobLogEntry,
    JobLogPage,
    JobPage,
    JobResponse,
    SubmissionCreate,
    SubmissionResponse,
)
from .service import confirm_draft, create_compute_draft, create_submission, request_cancel, retry_job

router = APIRouter(tags=["compute"])


def _submission_response(submission, jobs) -> SubmissionResponse:
    return SubmissionResponse(
        id=submission.id,
        workflow_run_id=submission.workflow_run_id,
        project_id=submission.project_id,
        status=submission.status,
        compute_backend=submission.compute_backend,
        jobs=[JobResponse.model_validate(job) for job in jobs],
        created_at=submission.created_at,
    )


@router.get("/compute-drafts", response_model=ComputeDraftPage)
def list_compute_drafts(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ComputeDraftPage:
    require_project(session, project_id, user)
    after = decode_cursor(cursor)
    rows = ComputeRepository(session).list_drafts(project_id, after=after, limit=limit)
    page = rows[:limit]
    return ComputeDraftPage(
        items=[ComputeDraftResponse.model_validate(row) for row in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get("/compute-drafts/{draft_id}", response_model=ComputeDraftResponse)
def get_compute_draft(
    draft_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ComputeDraftResponse:
    row = ComputeRepository(session).draft(draft_id)
    if row is None:
        raise DomainError("compute_draft_not_found", "Compute draft was not found", status_code=404)
    require_project(session, row.project_id, user)
    return ComputeDraftResponse.model_validate(row)


@router.post(
    "/workflow-runs/{workflow_id}/submissions",
    response_model=SubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "workflow.submit"},
)
def submit_workflow(
    workflow_id: uuid.UUID,
    payload: SubmissionCreate,
    idempotency_key: str = Header(min_length=8, max_length=160, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> SubmissionResponse:
    workflow = WorkflowRepository(session).get(workflow_id)
    if workflow is None:
        raise DomainError("workflow_not_found", "Workflow run was not found", status_code=404)
    project = require_project_permission(session, workflow.project_id, user, "compute")
    submission, jobs = create_submission(
        session,
        workflow=workflow,
        project=project,
        payload=payload,
        idempotency_key=idempotency_key,
        user=user,
    )
    return _submission_response(submission, jobs)


@router.get("/jobs", response_model=JobPage)
def list_jobs(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> JobPage:
    require_project(session, project_id, user)
    items = ComputeRepository(session).list_project_jobs(project_id, after=decode_cursor(cursor), limit=limit)
    has_next = len(items) > limit
    page = items[:limit]
    return JobPage(
        items=[JobResponse.model_validate(item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if has_next and page else None,
    )


@router.get("/workflow-runs/{workflow_id}/jobs", response_model=JobPage)
def list_workflow_jobs(
    workflow_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> JobPage:
    workflow = WorkflowRepository(session).get(workflow_id)
    if workflow is None:
        raise DomainError("workflow_not_found", "Workflow run was not found", status_code=404)
    require_project(session, workflow.project_id, user)
    jobs = ComputeRepository(session).jobs_for_workflow(workflow_id)
    return JobPage(items=[JobResponse.model_validate(job) for job in jobs])


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> JobResponse:
    job = ComputeRepository(session).job(job_id)
    if job is None:
        raise DomainError("job_not_found", "Job was not found", status_code=404)
    require_project(session, job.project_id, user)
    return JobResponse.model_validate(job)


@router.get("/jobs/{job_id}/logs", response_model=JobLogPage)
def get_job_logs(
    job_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> JobLogPage:
    job = ComputeRepository(session).job(job_id)
    if job is None:
        raise DomainError("job_not_found", "Job was not found", status_code=404)
    require_project(session, job.project_id, user)
    after = decode_cursor(cursor)
    events = ComputeRepository(session).events_page(job.id, after=after, limit=limit)
    page = events[:limit]
    return JobLogPage(
        items=[
            JobLogEntry(
                id=event.id,
                event=event.event_type,
                message=str(event.payload.get("message") or event.payload.get("error") or event.event_type),
                level=str(event.payload.get("level") or ("error" if "fail" in event.event_type else "info")),
                created_at=event.created_at,
            )
            for event in page
        ],
        next_cursor=encode_cursor(page[-1].id) if len(events) > limit and page else None,
    )


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=CancelResponse,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "job.cancel"},
)
def cancel_job(
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> CancelResponse:
    job = ComputeRepository(session).job(job_id)
    if job is None:
        raise DomainError("job_not_found", "Job was not found", status_code=404)
    project = require_project_permission(session, job.project_id, user, "compute")
    request_cancel(session, job, project, user)
    return CancelResponse(id=job.id, status=job.status)


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "job.retry"},
)
def retry_failed_job(
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> JobResponse:
    job = ComputeRepository(session).job(job_id)
    if job is None:
        raise DomainError("job_not_found", "Job was not found", status_code=404)
    project = require_project_permission(session, job.project_id, user, "compute")
    return JobResponse.model_validate(retry_job(session, job, project, user))


@router.get("/jobs/{job_id}/events")
def job_events(job_id: uuid.UUID, user: User = Depends(streaming_user)) -> EventSourceResponse:
    with SessionFactory() as session:
        job = ComputeRepository(session).job(job_id)
        if job is None:
            raise DomainError("job_not_found", "Job was not found", status_code=404)
        require_project(session, job.project_id, user)

    async def stream() -> AsyncIterator[dict[str, str]]:
        cursor: datetime | None = None
        while True:
            with SessionFactory() as event_session:
                events = ComputeRepository(event_session).events_after(job_id, cursor)
                current = ComputeRepository(event_session).job(job_id)
                payloads = [
                    {
                        "id": str(item.id),
                        "event": item.event_type,
                        "data": json.dumps(item.payload),
                    }
                    for item in events
                ]
                if events:
                    cursor = events[-1].created_at
                terminal = current is None or current.status in {"succeeded", "failed", "cancelled"}
            for payload in payloads:
                yield payload
            if terminal:
                yield {"event": "done", "data": json.dumps({"job_id": str(job_id)})}
                return
            await asyncio.sleep(1)

    return EventSourceResponse(observed_sse("jobs", stream()))


@router.post(
    "/compute-drafts",
    response_model=ComputeDraftResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "compute_draft.create"},
)
def post_compute_draft(
    payload: ComputeDraftCreate, session: Session = Depends(get_session), user: User = Depends(require_command)
) -> ComputeDraftResponse:
    require_project_permission(session, payload.project_id, user, "compute")
    row = create_compute_draft(session, payload, user)
    return ComputeDraftResponse.model_validate(row)


@router.post(
    "/compute-drafts/{draft_id}/confirm",
    response_model=ComputeDraftResponse,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "compute_draft.confirm"},
)
def confirm_compute_draft(
    draft_id: uuid.UUID, session: Session = Depends(get_session), user: User = Depends(require_command)
) -> ComputeDraftResponse:
    row = ComputeRepository(session).draft(draft_id)
    if row is None:
        raise DomainError("compute_draft_not_found", "Compute draft was not found", status_code=404)
    project = require_project_permission(session, row.project_id, user, "compute")
    confirm_draft(session, row, project, user)
    return ComputeDraftResponse.model_validate(row)
