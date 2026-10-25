"""Resource identifiers must preserve project boundaries even for global admins."""
from __future__ import annotations

import uuid

import pytest
from backend_v2.app.campaigns.models import CampaignEvaluation, CampaignRound
from backend_v2.app.campaigns.schemas import CampaignCreate, EvaluationCreate, RoundCreate
from backend_v2.app.campaigns.service import create_campaign, create_evaluation, create_round
from backend_v2.app.candidates.schemas import CandidateCreate
from backend_v2.app.candidates.service import create_candidate
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import User
from backend_v2.app.projects.models import Project
from backend_v2.app.targets.api import import_target_structure
from backend_v2.app.targets.models import Target
from backend_v2.app.targets.schemas import TargetStructureImport
from backend_v2.app.workflows.models import WorkflowRun
from backend_v2.tests.test_research_goals import _evidence, _project
from backend_v2.tests.test_research_goals import session as reference_session  # noqa: F401
from sqlalchemy import func, select


@pytest.fixture(name="session")
def security_session(request):
    return request.getfixturevalue("reference_session")


def test_campaign_references_are_confined_to_the_campaign_project(session) -> None:
    project_id, user_id = _project(session, "ours")
    other_id, other_user_id = _project(session, "theirs")
    project, user = session.get(Project, project_id), session.get(User, user_id)
    campaign = create_campaign(session, project, CampaignCreate(name="Campaign"), user)
    foreign_workflow = WorkflowRun(project_id=other_id, created_by=other_user_id, name="Private")
    local_workflow = WorkflowRun(project_id=project_id, created_by=user_id, name="Ours")
    session.add_all([foreign_workflow, local_workflow])
    session.flush()
    for workflow_id in (foreign_workflow.id, uuid.uuid4()):
        with pytest.raises(DomainError, match="in this project"):
            create_round(session, campaign, RoundCreate(workflow_run_id=workflow_id))
    assert session.scalar(select(func.count()).select_from(CampaignRound)) == 0
    round_ = create_round(session, campaign, RoundCreate(workflow_run_id=local_workflow.id))
    foreign_candidate = _evidence(session, other_id, other_user_id, "candidate")
    for candidate_id in (foreign_candidate.id, uuid.uuid4()):
        with pytest.raises(DomainError, match="in this project"):
            create_evaluation(session, round_, EvaluationCreate(candidate_id=candidate_id))
    assert session.scalar(select(func.count()).select_from(CampaignEvaluation)) == 0
    local_candidate = _evidence(session, project_id, user_id, "candidate")
    assert create_evaluation(session, round_, EvaluationCreate(candidate_id=local_candidate.id)).candidate_id == local_candidate.id


def test_candidate_provenance_cannot_reference_another_projects_job(session) -> None:
    project_id, user_id = _project(session, "ours")
    other_id, other_user_id = _project(session, "theirs")
    project, user = session.get(Project, project_id), session.get(User, user_id)
    foreign_job = _evidence(session, other_id, other_user_id, "job")
    for job_id in (foreign_job.id, uuid.uuid4()):
        with pytest.raises(DomainError, match="same project"):
            create_candidate(session, project, CandidateCreate(candidate_key="candidate", name="Candidate", source_job_id=job_id), user)
    local_job = _evidence(session, project_id, user_id, "job")
    assert create_candidate(session, project, CandidateCreate(candidate_key="candidate", name="Candidate", source_job_id=local_job.id), user).source_job_id == local_job.id


def test_target_import_rejects_invalid_artifacts_before_enqueuing(session) -> None:
    from backend_v2.app.artifacts.models import Artifact
    from backend_v2.app.platform.models import Operation

    project_id, user_id = _project(session, "ours")
    other_id, _ = _project(session, "theirs")
    user = session.get(User, user_id)
    user.role = "admin"
    target = Target(project_id=project_id, name="Our target")
    foreign = Artifact(project_id=other_id, created_by=user_id, filename="private.pdb", artifact_type="structure", content_type="chemical/x-pdb", object_key="private", size_bytes=1, checksum_sha256="a" * 64)
    unavailable = Artifact(project_id=project_id, created_by=user_id, filename="pending.pdb", artifact_type="structure", content_type="chemical/x-pdb", object_key="pending", size_bytes=1, checksum_sha256="b" * 64, status="failed")
    session.add_all([target, foreign, unavailable])
    session.flush()
    for artifact_id in (foreign.id, unavailable.id, uuid.uuid4()):
        with pytest.raises(DomainError, match="Available project artifact"):
            import_target_structure(target.id, TargetStructureImport(source="artifact", artifact_id=artifact_id), session, user)
    assert session.scalar(select(func.count()).select_from(Operation)) == 0
    assert target.structure_status != "importing"


def test_protein_candidate_links_cannot_cross_projects_on_create_or_update(session) -> None:
    from backend_v2.app.wetlab.schemas import ProteinCreate, ProteinUpdate
    from backend_v2.app.wetlab.service import create_protein, update_protein

    project_id, user_id = _project(session, "ours")
    other_id, other_user_id = _project(session, "theirs")
    foreign = _evidence(session, other_id, other_user_id, "candidate")
    local = _evidence(session, project_id, user_id, "candidate")
    for candidate_id in (foreign.id, uuid.uuid4()):
        with pytest.raises(DomainError, match="in this project"):
            create_protein(session, project_id, user_id, ProteinCreate(name="Construct", sequence="MAAA", candidate_id=candidate_id))
    protein = create_protein(session, project_id, user_id, ProteinCreate(name="Construct", sequence="MAAA", candidate_id=local.id))
    for candidate_id in (foreign.id, uuid.uuid4()):
        with pytest.raises(DomainError, match="in this project"):
            update_protein(session, protein, ProteinUpdate(name="Unexpected mutation", candidate_id=candidate_id))
        assert protein.candidate_id == local.id
        assert protein.name == "Construct"


def test_registry_provider_list_and_detail_hide_other_projects_byok(session) -> None:
    from backend_v2.app.identity.models import OrganizationMember
    from backend_v2.app.registry.api import get_llm_provider, list_llm_providers
    from backend_v2.app.registry.models import LLMProvider
    from fastapi import Response

    project_id, user_id = _project(session, "ours")
    other_id, _ = _project(session, "theirs")
    user = session.get(User, user_id)
    user.role = "researcher"
    project = session.get(Project, project_id)
    session.add(OrganizationMember(organization_id=project.organization_id, user_id=user_id, role="researcher"))
    providers = [
        LLMProvider(id=uuid.UUID(int=1), name=f"Project {other_id} BYOK", provider_type="openai", model="private-model", endpoint="https://private.example/v1", credential_ref="private"),
        LLMProvider(id=uuid.UUID(int=2), name="Shared provider", provider_type="openai", model="shared-model", endpoint="https://shared.example/v1", credential_ref="shared"),
        LLMProvider(id=uuid.UUID(int=3), name=f"Project {project_id} BYOK", provider_type="openai", model="ours", endpoint="https://ours.example/v1", credential_ref="ours"),
    ]
    session.add_all(providers)
    session.flush()
    first = list_llm_providers(cursor=None, limit=1, session=session, user=user)
    assert [item.id for item in first.items] == [providers[1].id]
    assert first.next_cursor is not None
    second = list_llm_providers(cursor=first.next_cursor, limit=1, session=session, user=user)
    assert [item.id for item in second.items] == [providers[2].id]
    assert second.next_cursor is None
    with pytest.raises(DomainError):
        get_llm_provider(providers[0].id, Response(), session, user)
    assert get_llm_provider(providers[2].id, Response(), session, user).id == providers[2].id
    user.role = "admin"
    assert len(list_llm_providers(cursor=None, limit=50, session=session, user=user).items) == 3


def test_campaign_workers_refuse_legacy_cross_project_links(session, monkeypatch) -> None:
    from contextlib import contextmanager

    from backend_v2.app.campaigns import tasks

    project_id, user_id = _project(session, "ours")
    other_id, other_user_id = _project(session, "theirs")
    campaign = create_campaign(session, session.get(Project, project_id), CampaignCreate(name="Campaign"), session.get(User, user_id))
    foreign_job = _evidence(session, other_id, other_user_id, "job")
    foreign_job.status = "succeeded"
    # Simulate a corrupt link persisted before the security update. Workers must
    # fence it again, independently of validation on the interactive write path.
    round_ = CampaignRound(campaign_id=campaign.id, round_number=1, workflow_run_id=foreign_job.workflow_run_id)
    session.add(round_)
    session.flush()

    @contextmanager
    def scope():
        yield session

    monkeypatch.setattr(tasks, "session_scope", scope)
    assert tasks.campaign_advance.run(str(foreign_job.id))["status"] == "unlinked"
    with pytest.raises(ValueError, match="campaign_job_project_mismatch"):
        tasks.campaign_evaluate.run(str(round_.id))
    assert round_.submission_id is None
    assert session.scalar(select(func.count()).select_from(CampaignEvaluation)) == 0


def test_readonly_audit_detects_legacy_corruption_without_changing_data(session) -> None:
    from backend_v2.app.research import goals
    from backend_v2.app.research.models import ResearchGoalLink
    from backend_v2.scripts.audit_project_isolation import audit_project_references

    project_id, user_id = _project(session, "ours")
    other_id, other_user_id = _project(session, "theirs")
    foreign_job = _evidence(session, other_id, other_user_id, "job")
    candidate = _evidence(session, project_id, user_id, "candidate")
    goal = goals.create_goal(session, project_id, user_id, title="Our question")
    assert audit_project_references(session) == []
    candidate.source_job_id = foreign_job.id
    link = ResearchGoalLink(goal_id=goal.id, resource_type="candidate", resource_id=uuid.uuid4(), created_by=user_id)
    session.add(link)
    session.flush()
    issues = audit_project_references(session)
    assert {issue["relation"] for issue in issues} == {"candidates.source_job_id", "research_goal_links.candidate"}
    assert candidate.source_job_id == foreign_job.id
    assert session.get(ResearchGoalLink, link.id) is link
    assert not session.dirty and not session.deleted


def test_finding_create_rejects_foreign_briefs_and_audit_detects_legacy_links(session) -> None:
    from backend_v2.app.research.models import ResearchBrief, ResearchFinding
    from backend_v2.app.research.schemas import FindingCreate
    from backend_v2.app.research.service import create_finding
    from backend_v2.scripts.audit_project_isolation import audit_project_references

    project_id, user_id = _project(session, "ours")
    other_id, other_user_id = _project(session, "theirs")
    project, user = session.get(Project, project_id), session.get(User, user_id)
    foreign = ResearchBrief(project_id=other_id, created_by=other_user_id, title="Private brief")
    local = ResearchBrief(project_id=project_id, created_by=user_id, title="Our brief")
    session.add_all([foreign, local])
    session.flush()
    for brief_id in (foreign.id, uuid.uuid4()):
        with pytest.raises(DomainError) as error:
            create_finding(session, project, FindingCreate(title="Finding", content="Evidence", brief_id=brief_id), user)
        assert error.value.error_code == "research_brief_not_found"
    assert session.scalar(select(func.count()).select_from(ResearchFinding)) == 0
    finding = create_finding(session, project, FindingCreate(title="Finding", content="Evidence", brief_id=local.id), user)
    assert audit_project_references(session) == []
    finding.brief_id = foreign.id  # legacy corruption must be detected, not repaired
    session.flush()
    issues = audit_project_references(session)
    assert [issue["relation"] for issue in issues] == ["research_findings.brief_id"]
    assert finding.brief_id == foreign.id


@pytest.mark.parametrize("timeline_field", ["supersedes_id", "caused_by_id"])
@pytest.mark.parametrize("lineage_field", ["parent_artifact_id", "child_artifact_id"])
def test_audit_checks_timeline_and_artifact_lineage_links(session, timeline_field, lineage_field) -> None:
    from backend_v2.app.artifacts.models import Artifact, ArtifactLineageEdge
    from backend_v2.scripts.audit_project_isolation import audit_project_references

    project_id, user_id = _project(session, "ours")
    other_id, other_user_id = _project(session, "theirs")
    entry = _evidence(session, project_id, user_id, "timeline_entry")
    foreign_entry = _evidence(session, other_id, other_user_id, "timeline_entry")
    artifacts = [Artifact(project_id=owner_id, created_by=user_id, filename="evidence.pdb", artifact_type="structure",
                          content_type="chemical/x-pdb", object_key=str(uuid.uuid4()), size_bytes=1,
                          checksum_sha256="a" * 64) for owner_id in (project_id, other_id)]
    session.add_all(artifacts)
    session.flush()
    lineage = ArtifactLineageEdge(project_id=project_id, parent_artifact_id=artifacts[0].id,
                                  child_artifact_id=artifacts[0].id, relation="derived_from")
    setattr(lineage, lineage_field, artifacts[1].id)
    setattr(entry, timeline_field, foreign_entry.id)
    session.add(lineage)
    session.flush()
    assert {issue["relation"] for issue in audit_project_references(session)} == {
        f"project_timeline_entries.{timeline_field}", f"artifact_lineage_edges.{lineage_field}",
    }
