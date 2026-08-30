"""Campaign round advancement and evaluation.

Moved out of ``compute.tasks``, which had grown to hold this domain's tasks alongside a
dozen others. Task names and queue routing are unchanged.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from ..compute.models import Job
from ..compute.repository import ComputeRepository
from ..compute.service import TERMINAL_STATES
from ..core.celery_app import celery_app
from ..core.database import session_scope


@celery_app.task(name="bda_v2.campaign_advance")
def campaign_advance(job_id: str) -> dict:
    """Move the round on now that one of its jobs has settled.

    Any terminal state counts, not only success. While compute emitted an event
    for succeeded jobs alone, a round whose only job failed stayed "running"
    forever, and a round of several jobs was marked failed only if some other job
    in it happened to succeed afterwards.
    """
    from ..campaigns.models import CampaignEvaluation, CampaignRound
    from ..candidates.models import Candidate

    parsed = uuid.UUID(job_id)
    with session_scope() as session:
        job = session.get(Job, parsed)
        if job is None or job.status not in TERMINAL_STATES:
            return {"job_id": job_id, "status": "ignored"}
        round_ = session.scalar(
            select(CampaignRound).where(
                (CampaignRound.submission_id == job.submission_id)
                | ((CampaignRound.submission_id.is_(None)) & (CampaignRound.workflow_run_id == job.workflow_run_id))
            )
        )
        if round_ is None:
            return {"job_id": job_id, "status": "unlinked"}
        jobs = ComputeRepository(session).jobs_for_submission(job.submission_id)
        if not jobs or any(item.status not in TERMINAL_STATES for item in jobs):
            round_.status = "running"
            round_.submission_id = job.submission_id
            return {"job_id": job_id, "status": "running"}
        round_.submission_id = job.submission_id
        if any(item.status != "succeeded" for item in jobs):
            round_.status = "failed"
            return {"job_id": job_id, "status": "failed"}
        candidates = list(
            session.scalars(select(Candidate).where(Candidate.source_job_id.in_([item.id for item in jobs])))
        )
        existing_candidate_ids = set(
            session.scalars(select(CampaignEvaluation.candidate_id).where(CampaignEvaluation.round_id == round_.id))
        )
        for candidate in candidates:
            if candidate.id not in existing_candidate_ids:
                session.add(
                    CampaignEvaluation(
                        round_id=round_.id,
                        candidate_id=candidate.id,
                        metrics=candidate.scores,
                        outcome="pending",
                        notes="Created from completed workflow submission",
                    )
                )
        round_.status = "evaluating"
        round_.version += 1
    return {"job_id": job_id, "status": "evaluating", "candidate_count": len(candidates)}


@celery_app.task(name="bda_v2.campaign_evaluate")
def campaign_evaluate(round_id: str) -> dict:
    from ..campaigns.models import CampaignEvaluation, CampaignRound
    from ..candidates.models import Candidate

    parsed = uuid.UUID(round_id)
    with session_scope() as session:
        round_ = session.get(CampaignRound, parsed)
        if round_ is None:
            return {"round_id": round_id, "status": "missing"}
        jobs = []
        if round_.submission_id:
            jobs = ComputeRepository(session).jobs_for_submission(round_.submission_id)
        elif round_.workflow_run_id:
            jobs = ComputeRepository(session).jobs_for_workflow(round_.workflow_run_id)
        candidates = (
            list(session.scalars(select(Candidate).where(Candidate.source_job_id.in_([job.id for job in jobs]))))
            if jobs
            else []
        )
        existing = set(
            session.scalars(select(CampaignEvaluation.candidate_id).where(CampaignEvaluation.round_id == round_.id))
        )
        for candidate in candidates:
            if candidate.id not in existing:
                session.add(
                    CampaignEvaluation(
                        round_id=round_.id,
                        candidate_id=candidate.id,
                        metrics=candidate.scores,
                        outcome="pending",
                        notes="Automated evaluation awaiting human decision",
                    )
                )
        round_.status = "review"
        round_.version += 1
    return {"round_id": round_id, "status": "review", "candidate_count": len(candidates)}
