"""Learning evidence, experiment handoffs and receipts on the existing campaign trunk."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..campaigns import service as campaigns
from ..campaigns.models import Campaign, CampaignRound
from ..campaigns.schemas import CampaignCreate, DecisionCreate, DecisionReview, EvaluationCreate, RoundCreate
from ..core.problem import DomainError
from ..experiments.models import ExperimentResult
from ..identity.models import User
from ..projects.models import Project
from ..research.models import ResearchGoal
from ..workflows.models import WorkflowRun
from . import engine, service
from .models import LearningAssay, LearningBatch, LearningDecision, LearningEvidence, LearningModel, LearningStudy
from .schemas import BatchComplete, BatchCreate, EvidenceCreate, EvidenceWithdraw, ObservationCreate


def _result(session: Session, project: Project, record_id: uuid.UUID) -> ExperimentResult:
    row = session.get(ExperimentResult, record_id)
    if row is None or row.project_id != project.id:
        raise DomainError("experiment_result_not_found", "Project experiment result was not found", status_code=404)
    return row


def _artifact(session: Session, project: Project, record_id: uuid.UUID) -> Artifact:
    row = session.get(Artifact, record_id)
    if row is None or row.project_id != project.id or row.status != "available":
        raise DomainError("learning_source_unavailable", "Project source artifact is not available", status_code=404)
    return row


def learning_state_digest(session: Session, project: Project, study: LearningStudy) -> str:
    results = list(
        session.scalars(
            select(ExperimentResult)
            .where(
                ExperimentResult.project_id == project.id,
                ExperimentResult.result_metadata["learning"]["assay_id"].as_string() == str(study.assay_id),
            )
            .order_by(ExperimentResult.id)
            .limit(10001)
        )
    )
    if len(results) > 10000:
        raise DomainError("learning_state_limit", "Study exceeds the interactive observation limit", status_code=413)
    evidence = list(
        session.scalars(
            select(LearningEvidence).where(LearningEvidence.study_id == study.id).order_by(LearningEvidence.id)
        )
    )
    referenced_results = {
        uuid.UUID(s["id"]) for e in evidence if not e.withdrawal for s in e.sources.get("results", [])
    }
    referenced_artifacts = {
        uuid.UUID(s["id"]) for e in evidence if not e.withdrawal for s in e.sources.get("artifacts", [])
    }
    known = {r.id for r in results}
    source_state = []
    for result_id in sorted(referenced_results - known, key=str):
        result = session.get(ExperimentResult, result_id)
        source_state.append(
            [str(result_id), result.version, result.value, result.result_metadata]
            if result
            else [str(result_id), "missing"]
        )
    artifacts = sorted({r.source_artifact_id for r in results if r.source_artifact_id} | referenced_artifacts, key=str)
    artifact_state = []
    for artifact_id in artifacts:
        a = session.get(Artifact, artifact_id)
        artifact_state.append(
            [str(artifact_id), a.version, a.status, a.checksum_sha256] if a else [str(artifact_id), "missing"]
        )
    successors = list(
        session.scalars(
            select(LearningStudy.id).where(LearningStudy.supersedes_id == study.id).order_by(LearningStudy.id)
        )
    )
    return engine.digest(
        {
            "study": [str(study.id), study.version, study.goal_snapshot],
            "results": [[str(r.id), r.version, r.value, r.unit, r.result_metadata] for r in results],
            "artifacts": artifact_state,
            "referenced_results": source_state,
            "evidence": [[str(e.id), e.version, e.sources, e.withdrawal] for e in evidence],
            "successors": [str(i) for i in successors],
        }
    )


def check_current(session: Session, project: Project, row: LearningDecision, study: LearningStudy) -> None:
    service.require_record(session, LearningAssay, project, study.assay_id, lock=True)
    if engine.digest(row.proposal) != row.proposal_digest:
        raise DomainError("learning_proposal_integrity", "Proposal digest does not match", status_code=409)
    model = service.require_record(session, LearningModel, project, row.model_id)
    if model.status != "promoted" or model.version != row.proposal["model_version"]:
        raise DomainError("learning_decision_stale", "Recompute with the currently promoted model", status_code=409)
    service._check_model_integrity(model)
    service._check_model_sources(session, project, model)
    goal = session.get(ResearchGoal, study.research_goal_id) if study.research_goal_id else None
    if goal is None or goal.version != study.goal_snapshot["version"]:
        raise DomainError("learning_goal_changed", "Freeze a new study for the changed research goal", status_code=409)
    if session.scalar(select(LearningStudy.id).where(LearningStudy.supersedes_id == study.id).limit(1)):
        raise DomainError("learning_study_superseded", "Use the revised study contract", status_code=409)
    expected_state = row.proposal.get("learning_state_digest")
    if not expected_state or expected_state != learning_state_digest(session, project, study):
        raise DomainError(
            "learning_evidence_changed", "Evidence changed; generate a new proposal before proceeding", status_code=409
        )
    secondary = row.proposal.get("secondary_model")
    if secondary:
        other = service.require_record(session, LearningModel, project, uuid.UUID(secondary["id"]))
        other_study = service.require_record(session, LearningStudy, project, other.study_id)
        other_goal = session.get(ResearchGoal, other_study.research_goal_id) if other_study.research_goal_id else None
        if (
            other.status != "promoted"
            or other.version != secondary["version"]
            or other_goal is None
            or other_goal.version != other_study.goal_snapshot["version"]
        ):
            raise DomainError(
                "learning_secondary_changed",
                "Secondary model or goal changed; regenerate the proposal",
                status_code=409,
            )
        service._check_model_integrity(other)
        service._check_model_sources(session, project, other)
        if secondary.get("learning_state_digest") != learning_state_digest(session, project, other_study):
            raise DomainError(
                "learning_secondary_changed", "Secondary evidence changed; regenerate the proposal", status_code=409
            )
    for item in row.proposal["selected"]:
        candidate = service._candidate(session, project, uuid.UUID(item["candidate_id"]))
        try:
            sequence_digest = service._features(candidate)["sequence_sha256"]
        except ValueError:
            sequence_digest = None
        if candidate.version != item["candidate_version"] or sequence_digest != item["sequence_sha256"]:
            raise DomainError("learning_candidate_changed", "Recompute after candidate changes", status_code=409)


def create_evidence(session: Session, project: Project, user: User, payload: EvidenceCreate) -> LearningEvidence:
    service.require_record(session, LearningStudy, project, payload.study_id, lock=True)
    results = [_result(session, project, i) for i in sorted(set(payload.result_ids), key=str)]
    if payload.kind == "fact" and any(r.result_metadata.get("learning_withdrawal") for r in results):
        raise DomainError(
            "learning_evidence_source_withdrawn", "Withdrawn observations cannot support a new fact", status_code=409
        )
    artifacts = [_artifact(session, project, i) for i in sorted(set(payload.artifact_ids), key=str)]
    sources = {
        "results": [
            {"id": str(r.id), "version": r.version, "value": r.value, "unit": r.unit, "metadata": r.result_metadata}
            for r in results
        ],
        "artifacts": [{"id": str(a.id), "version": a.version, "sha256": a.checksum_sha256} for a in artifacts],
    }
    return service._save(
        session,
        project,
        user,
        LearningEvidence(
            project_id=project.id,
            study_id=payload.study_id,
            kind=payload.kind,
            statement=payload.statement,
            sources=sources,
            created_by=user.id,
        ),
        "learning.evidence.create",
    )


def withdraw_evidence(
    session: Session, project: Project, user: User, record_id: uuid.UUID, payload: EvidenceWithdraw, expected: int
) -> LearningEvidence:
    row = service.require_record(session, LearningEvidence, project, record_id)
    service.require_record(session, LearningStudy, project, row.study_id, lock=True)
    row = service.require_record(session, LearningEvidence, project, record_id, lock=True)
    if row.version != expected:
        raise DomainError("version_conflict", "Evidence changed; reload before withdrawal", status_code=412)
    if row.withdrawal:
        raise DomainError("learning_evidence_withdrawn", "Evidence is already withdrawn", status_code=409)
    row.withdrawal = {"rationale": payload.rationale, "by": str(user.id), "at": datetime.now(UTC).isoformat()}
    row.version += 1
    return service._save(session, project, user, row, "learning.evidence.withdraw")


def create_batch(session: Session, project: Project, user: User, payload: BatchCreate, expected: int) -> LearningBatch:
    decision = service.require_record(session, LearningDecision, project, payload.decision_id)
    study = service.require_record(session, LearningStudy, project, decision.study_id, lock=True)
    decision = service.require_record(session, LearningDecision, project, decision.id, lock=True)
    if decision.version != expected:
        raise DomainError("version_conflict", "Decision changed; reload before handoff", status_code=412)
    existing = session.scalar(select(LearningBatch).where(LearningBatch.decision_id == decision.id))
    if existing is not None:
        if payload.campaign_id and payload.campaign_id != existing.campaign_id:
            raise DomainError(
                "learning_handoff_conflict", "Decision already belongs to another campaign", status_code=409
            )
        if payload.workflow_run_id and str(payload.workflow_run_id) != existing.manifest.get("workflow_run_id"):
            raise DomainError(
                "learning_handoff_conflict", "Decision already belongs to another workflow", status_code=409
            )
        return existing
    if decision.review_status != "approved" or decision.proposal["action"] != "review_batch":
        raise DomainError("learning_batch_unapproved", "An approved, non-stop proposal is required", status_code=409)
    check_current(session, project, decision, study)
    previous = list(
        session.scalars(
            select(LearningBatch).where(LearningBatch.study_id == study.id).order_by(LearningBatch.created_at)
        )
    )
    if len(previous) >= study.max_rounds:
        raise DomainError("learning_round_limit", "Study round limit reached; revise the contract", status_code=409)
    if any(r.receipt is None for r in previous):
        raise DomainError(
            "learning_round_open", "Receive the outstanding batch before opening the next round", status_code=409
        )
    campaign_id = payload.campaign_id or (previous[-1].campaign_id if previous else None)
    if campaign_id:
        campaign = session.scalar(
            select(Campaign).where(Campaign.id == campaign_id, Campaign.project_id == project.id).with_for_update()
        )
        if campaign is None:
            raise DomainError("campaign_not_found", "Project campaign was not found", status_code=404)
    else:
        campaign = campaigns.create_campaign(
            session,
            project,
            CampaignCreate(
                name=study.name, objective=study.goal_snapshot["title"], config={"learning_study_id": str(study.id)}
            ),
            user,
        )
    workflow = (
        session.scalar(select(WorkflowRun).where(WorkflowRun.id == payload.workflow_run_id).with_for_update())
        if payload.workflow_run_id
        else None
    )
    if payload.workflow_run_id and (workflow is None or workflow.project_id != project.id):
        raise DomainError("workflow_not_found", "Project workflow was not found", status_code=404)
    if workflow and session.scalar(
        select(CampaignRound.id).where(CampaignRound.workflow_run_id == workflow.id).limit(1)
    ):
        raise DomainError(
            "learning_workflow_already_linked",
            "A workflow can supply only one campaign round; create a new run for this batch",
            status_code=409,
        )
    round_ = campaigns.create_round(
        session, campaign, RoundCreate(hypothesis=payload.rationale, workflow_run_id=payload.workflow_run_id)
    )
    record = campaigns.create_decision(
        session,
        round_,
        DecisionCreate(
            decision="learning_batch",
            rationale=payload.rationale,
            parameter_patch={"learning_decision_id": str(decision.id), "proposal_digest": decision.proposal_digest},
        ),
        user,
    )
    campaigns.review_decision(record, DecisionReview(approve=True), record.version, user)
    batch_id = uuid.uuid4()
    manifest = {
        "schema_version": 1,
        "decision_id": str(decision.id),
        "proposal_digest": decision.proposal_digest,
        "assay_id": str(study.assay_id),
        "batch_key": f"learning:{batch_id}",
        "round_number": round_.round_number,
        "currency": study.currency,
        "estimated_cost_cents": decision.proposal["estimated_cost_cents"],
        "candidates": decision.proposal["selected"],
        "rationale": payload.rationale,
        "external_submission": False,
        "workflow_run_id": str(workflow.id) if workflow else None,
        "workflow_version": workflow.version if workflow else None,
        "budget_reserved": False,
        "instructions": "Use batch_key, candidate_id, exact assay unit and an explicit status for every sample. Upload source evidence; failed samples remain part of the receipt.",
    }
    return service._save(
        session,
        project,
        user,
        LearningBatch(
            id=batch_id,
            project_id=project.id,
            study_id=study.id,
            decision_id=decision.id,
            campaign_id=campaign.id,
            round_id=round_.id,
            manifest=manifest,
            digest=engine.digest(manifest),
            created_by=user.id,
        ),
        "learning.batch.create",
    )


def complete_batch(
    session: Session, project: Project, user: User, record_id: uuid.UUID, payload: BatchComplete, expected: int
) -> LearningBatch:
    row = service.require_record(session, LearningBatch, project, record_id)
    study = service.require_record(session, LearningStudy, project, row.study_id, lock=True)
    row = service.require_record(session, LearningBatch, project, record_id, lock=True)
    if row.version != expected:
        raise DomainError("version_conflict", "Batch changed; reload before receiving results", status_code=412)
    if row.receipt is not None:
        raise DomainError(
            "learning_batch_received", "Batch already received; its receipt is immutable", status_code=409
        )
    if engine.digest(row.manifest) != row.digest:
        raise DomainError("learning_batch_integrity", "Batch manifest digest does not match", status_code=409)
    service.require_record(session, LearningAssay, project, study.assay_id, lock=True)
    expected_candidates = {c["candidate_id"] for c in row.manifest["candidates"]}
    all_batch_results = list(
        session.scalars(
            select(ExperimentResult)
            .where(ExperimentResult.project_id == project.id, ExperimentResult.batch_key == row.manifest["batch_key"])
            .limit(1001)
        )
    )
    active_results = {r.id for r in all_batch_results if not r.result_metadata.get("learning_withdrawal")}
    if len(all_batch_results) > 1000 or set(payload.result_ids) != active_results:
        raise DomainError(
            "learning_receipt_omits_results",
            "Receive every active result in this batch, including repeats and failures (maximum 1000)",
            status_code=422,
        )
    observations = []
    actual_candidates: set[str] = set()
    for result_id in payload.result_ids:
        result = _result(session, project, result_id)
        try:
            observation = ObservationCreate.model_validate(result.result_metadata.get("learning", {}))
        except ValueError as exc:
            raise DomainError(
                "learning_result_contract", "Receipt results need validated learning metadata", status_code=422
            ) from exc
        if (
            observation.assay_id != study.assay_id
            or observation.batch_key != row.manifest["batch_key"]
            or result.batch_key != observation.batch_key
        ):
            raise DomainError(
                "learning_batch_mismatch", "Receipt result belongs to another assay or batch", status_code=422
            )
        if (
            result.value != observation.value
            or result.unit != observation.unit
            or result.candidate_id != observation.candidate_id
            or result.source_artifact_id != observation.source_artifact_id
            or result.unit != study.goal_snapshot["unit"]
        ):
            raise DomainError(
                "learning_result_contract", "Receipt result disagrees with its measurement contract", status_code=422
            )
        _artifact(session, project, observation.source_artifact_id)
        if observation.sample_role == "candidate":
            actual_candidates.add(str(observation.candidate_id))
        observations.append((result, observation))
    if actual_candidates != expected_candidates:
        raise DomainError(
            "learning_batch_incomplete",
            "Every selected candidate needs an explicit result, including failed or missing samples",
            status_code=422,
        )
    round_ = session.get(CampaignRound, row.round_id)
    assert round_ is not None
    for result, observation in observations:
        campaigns.create_evaluation(
            session,
            round_,
            EvaluationCreate(
                candidate_id=result.candidate_id,
                metrics={
                    "result_id": str(result.id),
                    "result_version": result.version,
                    "value": result.value,
                    "unit": result.unit,
                    "status": observation.status,
                    "qc_accepted": observation.qc_accepted,
                },
                outcome="measured" if observation.status == "measured" and observation.qc_accepted else "excluded",
                notes=observation.note,
            ),
        )
    campaigns.mark_round_evaluating(round_)
    receipt = {
        "result_ids": [str(r.id) for r, _ in observations],
        "result_versions": {str(r.id): r.version for r, _ in observations},
        "actual_cost_cents": payload.actual_cost_cents,
        "currency": study.currency,
        "cost_basis": "operator_reported_experiment_total",
        "over_estimate": payload.actual_cost_cents > row.manifest["estimated_cost_cents"],
        "note": payload.note,
        "received_by": str(user.id),
        "received_at": datetime.now(UTC).isoformat(),
        "failed_or_missing": sum(o.status in {"failed", "missing"} for _, o in observations),
        "measured_qc_accepted": sum(o.status == "measured" and o.qc_accepted for _, o in observations),
    }
    row.receipt = {**receipt, "checksum": engine.digest(receipt)}
    row.version += 1
    return service._save(session, project, user, row, "learning.batch.receive")
