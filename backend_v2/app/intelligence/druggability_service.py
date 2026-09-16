"""Starting a druggability assessment, and reading one back.

A druggability assessment is an `IntelligenceRun` whose `query.kind` names it,
so its report and evidence rows reuse the tables target intelligence already
has - reviewable, versioned, exportable - without a second schema for "a run
that gathered evidence about a target". It runs on its own outbox topic
(`intelligence.druggability`), because the work is different: target
intelligence reads the project's own records, and this reads public sources.

Keyed by UniProt accession, and refused without one. The identifier chain is
UniProt -> the Open Targets id UniProt itself cross-references; a target known
only by name would have to be resolved by guessing, which is the failure the
researcher charter forbids.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.problem import DomainError
from ..identity.models import User
from ..platform.operations import enqueue_operation
from ..projects.models import Project
from ..targets.models import Target
from .models import IntelligenceReport, IntelligenceRun

DRUGGABILITY_KIND = "druggability"
TOPIC = "intelligence.druggability"


def create_druggability_run(
    session: Session,
    project: Project,
    target_id: uuid.UUID,
    user: User,
    *,
    trial_term: str = "",
    candidate_id: uuid.UUID | None = None,
    source: dict[str, Any] | None = None,
) -> IntelligenceRun:
    target = session.get(Target, target_id)
    if target is None or target.project_id != project.id:
        raise DomainError("target_not_found", "Target does not belong to this project", status_code=404)
    if not str(target.uniprot_accession or "").strip():
        raise DomainError(
            "target_uniprot_missing",
            "A druggability assessment is keyed by UniProt accession, and this target has none. "
            "Resolve the target's identity first; it is not guessed from the name.",
            status_code=422,
        )
    # Checked separately, so the error names the value the caller can change.
    # Blaming a "trial term" the caller never supplied sends them looking for
    # an argument they did not pass.
    supplied = trial_term.strip()
    if len(supplied) > 200:
        raise DomainError("trial_term_too_long", "The trial search term is longer than 200 characters.", status_code=422)
    term = supplied or str(target.name or "").strip()
    if not term:
        raise DomainError(
            "trial_term_missing",
            "This target has no name to search trials by. Supply a trial term.",
            status_code=422,
        )
    if len(term) > 200:
        raise DomainError(
            "target_name_too_long",
            f"The target's name is {len(term)} characters, too long to use as a trial search term. "
            "Supply a shorter trial_term.",
            status_code=422,
        )
    candidate_sequence = None
    if candidate_id is not None:
        from ..candidates.models import Candidate
        from ..sequences.service import analyse

        candidate = session.get(Candidate, candidate_id)
        if candidate is None or candidate.project_id != project.id:
            raise DomainError("candidate_not_found", "Candidate does not belong to this project", status_code=404)
        # Freeze measurements of the exact requested sequence before queueing.
        # A later candidate edit must not silently change what this run assessed.
        candidate_sequence = analyse(session, project.id, candidate_id=candidate_id)
    row = IntelligenceRun(
        project_id=project.id,
        target_id=target.id,
        created_by=user.id,
        query={
            **(source or {}), "kind": DRUGGABILITY_KIND, "trial_term": term,
            "candidate_id": str(candidate_id) if candidate_id else None,
            "candidate_sequence": candidate_sequence,
        },
    )
    session.add(row)
    session.flush()
    enqueue_operation(
        session,
        topic=TOPIC,
        resource_type="intelligence_run",
        resource_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"run_id": str(row.id)},
    )
    return row


def read_assessment(session: Session, project_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
    """The saved report for one druggability run in this project.

    Another project's run, and a target-intelligence run, are the same 404:
    telling them apart would disclose which ids exist elsewhere, and a
    target-intelligence report read as a druggability report would be a
    report about something else.
    """
    run = session.get(IntelligenceRun, run_id)
    if run is None or run.project_id != project_id or (run.query or {}).get("kind") != DRUGGABILITY_KIND:
        raise DomainError("druggability_run_not_found", "No such druggability assessment in this project.", status_code=404)
    report = session.scalar(select(IntelligenceReport).where(IntelligenceReport.run_id == run.id))
    return {
        "intelligence_run_id": str(run.id),
        "target_id": str(run.target_id),
        "status": run.status,
        "trial_term": (run.query or {}).get("trial_term"),
        # A run still in the queue has no report, and says so rather than
        # returning an empty one that would read as "nothing found".
        "report": report.content if report else None,
        "summary": report.summary if report else None,
        "review_status": report.review_status if report else None,
        "note": None if report else "The assessment has not finished; nothing has been saved yet.",
    }
