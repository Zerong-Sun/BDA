"""Turning a stage of a frozen protocol into a real object on the main trunk.

Until this existed, `execute_campaign` reserved budget, marked the first stage ready, and
stopped. `autopilot_stages.resource_type` / `resource_id` had been reserved for the
answer since the table was created and nothing ever wrote them, so an automatic campaign
produced nothing a person could open, review or correct.

Two rules shape everything here, and both come from failures the platform has already had.

**One execution trunk.** An adapter creates the *same* objects the Workflow canvas
creates - a `workflow_runs` row, through the workflows domain's own service - and the
stage points at it. It does not get an Autopilot-private mirror of the run. A mirror
would mean a candidate a person rejected by hand is still live for the next automatic
stage, with nothing anywhere reporting a disagreement.

**Query before creating.** Every adapter is idempotent under redelivery, and the key is
derived from the stage id rather than from anything the worker holds in memory: Celery
redelivers, and a second run created by a retry costs real cluster time. This is the same
discipline `compute/adapters.py` applies to `ensure_submitted` - look at external state
first, act second.

What an adapter deliberately does *not* do is invent a compute submission. A frozen spec
that names no route gets a `draft` run and a stage that says so; a person opens it in the
Workflow page and finishes it. That is the handoff the dual-mode plan is about, not a gap
in it - guessing a route from a sentence is how you spend GPU hours on a question nobody
asked.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..identity.models import User
from ..projects.models import Project
from ..workflows.models import WorkflowRun
from ..workflows.schemas import WorkflowCreate
from ..workflows.service import create_workflow
from .models import AutopilotCampaign, AutopilotStage

#: `(resource_type, resource_id)`, written straight onto the stage.
StageResource = tuple[str, uuid.UUID]


class StageAdapter(Protocol):
    """What every stage adapter has to provide.

    Returning ``None`` means "this stage has no trunk object of its own" - a review stage
    is a human step, not a resource - and is not an error.
    """

    def ensure_stage_resource(
        self, session: Session, campaign: AutopilotCampaign, stage: AutopilotStage
    ) -> StageResource | None: ...


def idempotency_key(stage: AutopilotStage) -> str:
    """Stable across redeliveries, unique per stage, and readable in a database.

    Stored in the trunk object's ``legacy_id``, which carries a unique constraint - so a
    duplicate delivery loses the race at the database rather than quietly creating a
    second run that also looks legitimate.
    """
    return f"autopilot-stage:{stage.id}"


class WorkflowRunAdapter:
    """A compute stage becomes a workflow run in the project the campaign belongs to.

    The graph comes from the frozen spec when it carries one under ``workflow``. When it
    does not, the run is created empty and stays a draft: the stage has still landed
    somewhere a person can open, which is the whole point, and nothing has been submitted
    on a guess.
    """

    def ensure_stage_resource(
        self, session: Session, campaign: AutopilotCampaign, stage: AutopilotStage
    ) -> StageResource | None:
        key = idempotency_key(stage)
        existing = session.scalar(select(WorkflowRun).where(WorkflowRun.legacy_id == key))
        if existing is not None:
            return ("workflow_run", existing.id)

        project = session.get(Project, campaign.project_id)
        # The campaign's confirmer, not a robot account: they approved this protocol, and
        # the run has to be attributable to a real person for the project's permission
        # checks to mean anything.
        user = session.get(User, campaign.created_by)
        if project is None or user is None:
            return None

        spec: dict = campaign.frozen_spec if isinstance(campaign.frozen_spec, dict) else {}
        declared = spec.get("workflow")
        graph: dict = declared if isinstance(declared, dict) else {}
        payload = WorkflowCreate(
            name=f"{campaign.name} · {stage.stage_key}"[:200],
            nodes=graph.get("nodes") or [],
            edges=graph.get("edges") or [],
        )
        run = create_workflow(session, project, payload, user)
        run.legacy_id = key
        session.flush()
        return ("workflow_run", run.id)


#: Which stage keys have a trunk object today. A key that is absent is not a failure: it
#: means the stage is still a human step, and the campaign says so rather than pretending.
ADAPTERS: dict[str, StageAdapter] = {
    "compute": WorkflowRunAdapter(),
    "design": WorkflowRunAdapter(),
}


def adapter_for(stage_key: str) -> StageAdapter | None:
    return ADAPTERS.get(stage_key)


def ensure_stage_resource(
    session: Session, campaign: AutopilotCampaign, stage: AutopilotStage
) -> StageResource | None:
    """Resolve and run the adapter for a stage, writing the pointer onto the stage.

    Safe to call twice: the adapter finds what it made last time, and the stage ends up
    with the same pointer it already had.
    """
    adapter = adapter_for(stage.stage_key)
    if adapter is None:
        return None
    resource = adapter.ensure_stage_resource(session, campaign, stage)
    if resource is None:
        return None
    stage.resource_type, stage.resource_id = resource
    return resource
