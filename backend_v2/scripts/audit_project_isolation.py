"""Read-only audit of stored project references; never repairs or deletes records.

Run with PYTHONPATH=. and an enabled global administrator's UUID. The report
contains identifiers and relation names only, never project content or secrets.
An exit code of 1 means references need review; 0 means the checked relations
are consistent in the inspected snapshot, not that all security risks are absent.
"""
from __future__ import annotations

import argparse
import json
import uuid

from backend_v2.app.artifacts.models import Artifact, ArtifactLineageEdge
from backend_v2.app.campaigns.models import Campaign, CampaignEvaluation, CampaignRound
from backend_v2.app.candidates.models import Candidate
from backend_v2.app.compute.models import Job, JobSubmission
from backend_v2.app.core.database import SessionFactory, set_request_rls_context
from backend_v2.app.experiments.models import ExperimentResult
from backend_v2.app.identity.models import User
from backend_v2.app.projects.models import Project
from backend_v2.app.research.models import ResearchBrief, ResearchFinding, ResearchGoal, ResearchGoalLink
from backend_v2.app.targets.models import Target, TargetStructureRevision
from backend_v2.app.timeline.models import ProjectTimelineEntry
from backend_v2.app.wetlab.models import Protein
from backend_v2.app.workflows.models import WorkflowRun
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session


def audit_project_references(session: Session) -> list[dict[str, str | None]]:
    """Inspect persisted references, including legacy writes bypassing services."""
    issues: list[dict[str, str | None]] = []

    def inspect(relation, owner_id, owner_project, reference_id, target, *joins, extra=None):
        # Aliases let self-references (goal.parent, workflow.derived_from) use
        # exactly the same check as references to another domain.
        from sqlalchemy.orm import aliased

        linked = aliased(target)
        query = select(owner_id, owner_project, reference_id, linked.project_id).select_from(owner_id.class_)
        for model, condition in joins:
            query = query.join(model, condition)
        query = query.outerjoin(linked, linked.id == reference_id).where(
            reference_id.is_not(None), or_(linked.id.is_(None), linked.project_id != owner_project),
        )
        if extra is not None:
            query = query.where(extra)
        for entity_id, project_id, linked_id, linked_project in session.execute(query):
            issues.append({
                "relation": relation, "resource_id": str(entity_id), "project_id": str(project_id),
                "referenced_id": str(linked_id),
                "referenced_project_id": str(linked_project) if linked_project is not None else None,
            })

    for owner, field, target in (
        (Candidate, "structure_artifact_id", Artifact), (Candidate, "complex_artifact_id", Artifact),
        (Candidate, "source_job_id", Job), (Protein, "candidate_id", Candidate),
        (ExperimentResult, "candidate_id", Candidate), (ExperimentResult, "source_artifact_id", Artifact),
        (Target, "structure_artifact_id", Artifact), (ResearchFinding, "supersedes_id", ResearchFinding),
        (ResearchFinding, "brief_id", ResearchBrief),
        (ProjectTimelineEntry, "supersedes_id", ProjectTimelineEntry),
        (ProjectTimelineEntry, "caused_by_id", ProjectTimelineEntry),
        (ArtifactLineageEdge, "parent_artifact_id", Artifact),
        (ArtifactLineageEdge, "child_artifact_id", Artifact),
        (ResearchGoal, "parent_id", ResearchGoal), (WorkflowRun, "derived_from_id", WorkflowRun),
        (Job, "workflow_run_id", WorkflowRun), (Job, "submission_id", JobSubmission),
        (JobSubmission, "workflow_run_id", WorkflowRun),
    ):
        inspect(f"{owner.__tablename__}.{field}", owner.id, owner.project_id, getattr(owner, field), target)
    inspect("projects.primary_target_id", Project.id, Project.id, Project.primary_target_id, Target)
    campaign_join = (Campaign, Campaign.id == CampaignRound.campaign_id)
    inspect("campaign_rounds.workflow_run_id", CampaignRound.id, Campaign.project_id,
            CampaignRound.workflow_run_id, WorkflowRun, campaign_join)
    inspect("campaign_rounds.submission_id", CampaignRound.id, Campaign.project_id,
            CampaignRound.submission_id, JobSubmission, campaign_join)
    inspect("campaign_evaluations.candidate_id", CampaignEvaluation.id, Campaign.project_id,
            CampaignEvaluation.candidate_id, Candidate,
            (CampaignRound, CampaignRound.id == CampaignEvaluation.round_id), campaign_join)
    for field in ("source_artifact_id", "prepared_artifact_id"):
        inspect(f"target_structure_revisions.{field}", TargetStructureRevision.id, Target.project_id,
                getattr(TargetStructureRevision, field), Artifact,
                (Target, Target.id == TargetStructureRevision.target_id))
    for kind, model in (
        ("candidate", Candidate), ("job", Job), ("experiment_result", ExperimentResult),
        ("finding", ResearchFinding), ("protein", Protein),
    ):
        inspect(f"research_goal_links.{kind}", ResearchGoalLink.id, ResearchGoal.project_id,
                ResearchGoalLink.resource_id, model, (ResearchGoal, ResearchGoal.id == ResearchGoalLink.goal_id),
                extra=ResearchGoalLink.resource_type == kind)
    inspect("research_goal_links.timeline_entry", ResearchGoalLink.id, ResearchGoal.project_id,
            ResearchGoalLink.resource_id, ProjectTimelineEntry,
            (ResearchGoal, ResearchGoal.id == ResearchGoalLink.goal_id),
            extra=ResearchGoalLink.resource_type == "timeline_entry")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-user-id", required=True, type=uuid.UUID)
    args = parser.parse_args()
    with SessionFactory() as session:
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        user = session.get(User, args.admin_user_id)
        if user is None or not user.enabled or user.role != "admin":
            parser.error("--admin-user-id must identify an enabled global administrator")
        set_request_rls_context(session, user_id=user.id, is_global_admin=True)
        issues = audit_project_references(session)
        session.rollback()
    print(json.dumps({"issue_count": len(issues), "issues": issues}, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
