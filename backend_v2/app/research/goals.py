"""The research goal tree: service rules for the trace that spans dry and wet work.

Kept out of `service.py` because that file already carries briefs, findings and
generation. Nothing here reaches into another domain's repository; a link is
stored by `(resource_type, resource_id)` and the existence check goes through
the owning domain's own table.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.problem import DomainError
from .models import (
    GOAL_LINK_TYPES,
    GOAL_STATUSES,
    DecisionTreeDraft,
    ResearchGoal,
    ResearchGoalLink,
)

#: How deep a goal tree may go. Not a storage limit - a guard against a cycle
#: introduced by a bad re-parent turning every read into an infinite walk.
MAX_DEPTH = 12


def _decision_contract(session: Session, project_id: uuid.UUID, value: dict | None) -> dict:
    from ..literature.evidence_notes import NOTE_KIND
    from ..literature.models import LiteratureClaim, LiteratureDocument, LiteratureEvidence
    from .schemas import ResearchDecisionContract

    contract = ResearchDecisionContract.model_validate(value or {})
    if contract.evidence_note_ids:
        available = set(session.scalars(select(LiteratureClaim.id).join(
            LiteratureDocument, LiteratureDocument.id == LiteratureClaim.document_id,
        ).join(LiteratureEvidence, LiteratureEvidence.claim_id == LiteratureClaim.id).where(
                LiteratureDocument.project_id == project_id,
                LiteratureClaim.id.in_(contract.evidence_note_ids),
                LiteratureClaim.attributes["curation_kind"].as_string() == NOTE_KIND,
                LiteratureEvidence.evidence_type == NOTE_KIND)))
        if available != set(contract.evidence_note_ids):
            raise DomainError("research_decision_evidence_mismatch", "Every linked evidence note must exist in this project", status_code=422)
    return contract.model_dump(mode="json")


def _goal(session: Session, goal_id: uuid.UUID) -> ResearchGoal:
    goal = session.get(ResearchGoal, goal_id)
    if goal is None:
        raise DomainError("research_goal_not_found", "Research goal was not found", status_code=404)
    return goal


def _depth_of(session: Session, goal: ResearchGoal) -> int:
    depth = 0
    cursor: ResearchGoal | None = goal
    seen: set[uuid.UUID] = set()
    while cursor is not None and cursor.parent_id is not None:
        if cursor.id in seen:
            raise DomainError(
                "research_goal_cycle",
                "This goal's ancestry contains a cycle; re-parent it before continuing.",
                status_code=409,
            )
        seen.add(cursor.id)
        cursor = session.get(ResearchGoal, cursor.parent_id)
        depth += 1
        if depth > MAX_DEPTH:
            break
    return depth


def create_goal(
    session: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    title: str,
    detail: str = "",
    parent_id: uuid.UUID | None = None,
    tags: list[str] | None = None,
    decision_contract: dict | None = None,
) -> ResearchGoal:
    validated_contract = _decision_contract(session, project_id, decision_contract)
    if parent_id is not None:
        parent = _goal(session, parent_id)
        if parent.project_id != project_id:
            raise DomainError(
                "research_goal_cross_project",
                "A goal cannot hang under a goal from another project.",
                status_code=422,
            )
        if _depth_of(session, parent) + 1 > MAX_DEPTH:
            raise DomainError(
                "research_goal_too_deep",
                f"Goal nesting is limited to {MAX_DEPTH} levels.",
                status_code=422,
            )
    # Append within the parent rather than renumbering siblings on every insert.
    next_order = session.scalar(
        select(func.coalesce(func.max(ResearchGoal.sort_order), -1) + 1).where(
            ResearchGoal.project_id == project_id,
            ResearchGoal.parent_id == parent_id,
        )
    )
    goal = ResearchGoal(
        project_id=project_id,
        parent_id=parent_id,
        title=title,
        detail=detail,
        decision_contract=validated_contract,
        tags=list(tags or []),
        sort_order=int(next_order or 0),
        created_by=user_id,
    )
    session.add(goal)
    session.flush()
    return goal


def update_goal(
    session: Session,
    goal: ResearchGoal,
    *,
    title: str | None = None,
    detail: str | None = None,
    status: str | None = None,
    parent_id: uuid.UUID | None = None,
    reparent: bool = False,
    tags: list[str] | None = None,
    decision_contract: dict | None = None,
) -> ResearchGoal:
    # Validate scoped references before changing any goal fields.
    validated_contract = _decision_contract(session, goal.project_id, decision_contract) if decision_contract is not None else None
    if title is not None:
        goal.title = title
    if detail is not None:
        goal.detail = detail
    if tags is not None:
        goal.tags = list(tags)
    if validated_contract is not None:
        goal.decision_contract = validated_contract
    if status is not None:
        if status not in GOAL_STATUSES:
            raise DomainError(
                "research_goal_bad_status",
                f"status must be one of {', '.join(GOAL_STATUSES)}",
                status_code=422,
            )
        goal.status = status
    if reparent:
        if parent_id == goal.id:
            raise DomainError(
                "research_goal_cycle", "A goal cannot be its own parent.", status_code=422
            )
        if parent_id is not None:
            parent = _goal(session, parent_id)
            if parent.project_id != goal.project_id:
                raise DomainError(
                    "research_goal_cross_project",
                    "A goal cannot hang under a goal from another project.",
                    status_code=422,
                )
            # Walking up from the new parent must not meet this goal, or the
            # subtree becomes unreachable from any root and reads never end.
            cursor: ResearchGoal | None = parent
            hops = 0
            while cursor is not None:
                if cursor.id == goal.id:
                    raise DomainError(
                        "research_goal_cycle",
                        "That move would put the goal inside its own subtree.",
                        status_code=422,
                    )
                cursor = session.get(ResearchGoal, cursor.parent_id) if cursor.parent_id else None
                hops += 1
                if hops > MAX_DEPTH:
                    break
        goal.parent_id = parent_id
    goal.version += 1
    session.flush()
    return goal


def require_goal(session: Session, goal_id: uuid.UUID, *, for_update: bool = False) -> ResearchGoal:
    """Load a goal or fail. The API layer must not query the session itself."""
    if for_update:
        goal = session.scalar(select(ResearchGoal).where(ResearchGoal.id == goal_id).with_for_update())
        if goal is None:
            raise DomainError("research_goal_not_found", "Research goal was not found", status_code=404)
        return goal
    return _goal(session, goal_id)


def subtree_size(session: Session, goal: ResearchGoal) -> int:
    """How many goals a delete would take, so the response can say so."""
    total = 1
    frontier = [goal.id]
    depth = 0
    while frontier and depth <= MAX_DEPTH:
        children = list(
            session.scalars(select(ResearchGoal.id).where(ResearchGoal.parent_id.in_(frontier)))
        )
        total += len(children)
        frontier = children
        depth += 1
    return total


def delete_goal(session: Session, goal: ResearchGoal) -> int:
    """Removes the goal and its subtree, returning how many goals went.

    The evidence itself is untouched: links cascade, the results, candidates and
    findings they pointed at do not.
    """
    removed = subtree_size(session, goal)
    session.delete(goal)
    session.flush()
    return removed


def attach(
    session: Session,
    goal: ResearchGoal,
    user_id: uuid.UUID,
    *,
    resource_type: str,
    resource_id: uuid.UUID,
    note: str = "",
) -> ResearchGoalLink:
    if resource_type not in GOAL_LINK_TYPES:
        raise DomainError(
            "research_goal_bad_link_type",
            f"resource_type must be one of {', '.join(GOAL_LINK_TYPES)}",
            status_code=422,
        )
    # UUIDs are references, not authorization. A caller may read both projects
    # and still must never splice another project's evidence into this goal.
    from ..candidates.models import Candidate
    from ..compute.models import Job
    from ..experiments.models import ExperimentResult
    from ..timeline.models import ProjectTimelineEntry
    from ..wetlab.models import Protein
    from .models import ResearchFinding

    resource_models = {
        "candidate": Candidate,
        "job": Job,
        "experiment_result": ExperimentResult,
        "timeline_entry": ProjectTimelineEntry,
        "protein": Protein,
        "finding": ResearchFinding,
    }
    resource = session.get(resource_models[resource_type], resource_id)
    if resource is None or getattr(resource, "project_id", None) != goal.project_id:
        raise DomainError(
            "research_goal_resource_not_found",
            "Linked evidence was not found in this project",
            status_code=404,
        )
    existing = session.scalar(
        select(ResearchGoalLink).where(
            ResearchGoalLink.goal_id == goal.id,
            ResearchGoalLink.resource_type == resource_type,
            ResearchGoalLink.resource_id == resource_id,
        )
    )
    if existing is not None:
        # Attaching twice is a double-click, not a second piece of evidence.
        return existing
    link = ResearchGoalLink(
        goal_id=goal.id,
        resource_type=resource_type,
        resource_id=resource_id,
        note=note,
        created_by=user_id,
    )
    session.add(link)
    session.flush()
    return link


def detach(session: Session, goal: ResearchGoal, link_id: uuid.UUID) -> None:
    link = session.get(ResearchGoalLink, link_id)
    if link is None or link.goal_id != goal.id:
        raise DomainError("research_goal_link_not_found", "Link was not found", status_code=404)
    session.delete(link)
    session.flush()


def tree(session: Session, project_id: uuid.UUID) -> list[ResearchGoal]:
    """Every goal in the project, ordered so a caller can nest them in one pass."""
    return list(
        session.scalars(
            select(ResearchGoal)
            .where(ResearchGoal.project_id == project_id)
            .order_by(ResearchGoal.parent_id.is_(None).desc(), ResearchGoal.sort_order, ResearchGoal.id)
        )
    )


def links_for(session: Session, goal_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[ResearchGoalLink]]:
    """Links for many goals in one query, so rendering a tree is not N+1."""
    if not goal_ids:
        return {}
    grouped: dict[uuid.UUID, list[ResearchGoalLink]] = {goal_id: [] for goal_id in goal_ids}
    for link in session.scalars(
        select(ResearchGoalLink).where(ResearchGoalLink.goal_id.in_(goal_ids))
    ):
        grouped[link.goal_id].append(link)
    return grouped


def import_decision_tree(
    session: Session,
    project,
    user,
    proposal,
) -> tuple[list[ResearchGoal], list]:
    """Land a reviewed proposal as goals, open decisions, and the links between them.

    Takes the tree the *person* submitted, never a stored draft id. That is the whole
    mechanism: the per-item review cannot be skipped because no endpoint accepts a draft
    directly. What a model proposed and what a project committed to are different things,
    and this project's writer invariant says only the orchestrator turns one into the
    other.

    Every branch lands as ``outcome="unspecified"`` with empty provenance and no
    ``decision_ref``. They are questions, not conclusions: the tree view already marks
    them "no evidence linked", which is the correct reading of a branch nobody has
    answered yet, and decision numbers are the orchestrator's to allocate.
    """
    from ..timeline.schemas import TimelineEntryCreate
    from ..timeline.service import create_entry as create_timeline_entry

    created_goals: dict[str, ResearchGoal] = {}
    ordered: list[ResearchGoal] = []

    def plant(nodes, parent_id: uuid.UUID | None) -> None:
        for index, node in enumerate(nodes):
            goal = create_goal(
                session,
                project.id,
                user.id,
                title=node.title,
                detail=node.detail,
                parent_id=parent_id,
            )
            goal.sort_order = index
            created_goals[node.title] = goal
            ordered.append(goal)
            plant(node.children, goal.id)

    plant(proposal.goals, None)
    session.flush()

    entries = []
    for branch in proposal.branches:
        entry = create_timeline_entry(
            session,
            project,
            TimelineEntryCreate(
                occurred_at=datetime.now(UTC),
                entry_type="decision",
                lane=branch.lane,
                title=branch.title,
                summary=branch.summary,
                outcome="unspecified",
                alternatives=[a.model_dump() for a in branch.alternatives],
                tags=["bootstrap"],
            ),
            user,
            # A model drafted these branches and a person accepted them one at a time
            # (`POST /projects/{id}/decision-tree` takes a reviewed proposal, never a
            # draft id). That is neither a human judgement nor an unreviewed agent one,
            # and recording it as either would lose the distinction the column exists for.
            decided_by="agent_proposed_human_confirmed",
        )
        entries.append(entry)
        # `goal_title` was checked against the proposal's own goals by the schema, so a
        # missing key here would be a bug in `plant`, not bad input.
        attach(
            session,
            created_goals[branch.goal_title],
            user.id,
            resource_type="timeline_entry",
            resource_id=entry.id,
        )
    session.flush()
    return ordered, entries


def require_decision_tree_draft(session: Session, draft_id: uuid.UUID) -> DecisionTreeDraft:
    draft = session.get(DecisionTreeDraft, draft_id)
    if draft is None:
        raise DomainError("decision_tree_draft_not_found", "Decision tree draft was not found", status_code=404)
    return draft


def create_decision_tree_draft(session: Session, project, user, payload):
    """Queue a draft of the starting tree, derived from the project's own prompt.

    Refuses without a prompt rather than asking a model to invent goals from a project
    name. The prompt is the brief; a tree drafted from anything less is a guess wearing
    the same shape as a plan.
    """
    from ..platform.operations import enqueue_operation
    from .schemas import DecisionTreeDraftAccepted

    if not (project.prompt or "").strip():
        raise DomainError(
            "project_prompt_missing",
            "This project has no design prompt yet; write one before drafting its decision tree",
            status_code=409,
        )
    draft = DecisionTreeDraft(
        project_id=project.id,
        created_by=user.id,
        request={
            "llm_provider_id": str(payload.llm_provider_id) if payload.llm_provider_id else None,
            "project_type": project.project_type,
            # The prompt is copied in, not referenced: a draft has to stay interpretable
            # after the prompt it came from is rewritten, and rewriting is now a recorded
            # decision precisely because it happens.
            "prompt": project.prompt,
        },
    )
    session.add(draft)
    session.flush()
    enqueue_operation(
        session,
        topic="research.decision_tree_draft",
        resource_type="research_decision_tree_draft",
        resource_id=draft.id,
        organization_id=project.organization_id,
        user=user,
        payload={"draft_id": str(draft.id)},
    )
    return DecisionTreeDraftAccepted(draft_id=draft.id)
