from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..audit.service import record_audit
from ..candidates.models import Candidate
from ..core.problem import DomainError
from ..experiments.models import ExperimentResult
from ..experiments.schemas import ExperimentResultCreate
from ..experiments.service import create_idempotent_result
from ..identity.models import User
from ..projects.models import Project
from ..research import goals
from ..research.models import ResearchGoal
from ..timeline.schemas import TimelineEntryCreate
from ..timeline.service import create_entry
from . import engine
from .models import LearningAssay, LearningDataset, LearningDecision, LearningModel, LearningStudy
from .repository import LearningRepository, Record
from .schemas import (
    AssayCreate,
    DatasetCreate,
    LearningDecisionCreate,
    LearningDecisionReview,
    ModelReview,
    ObservationCreate,
    StudyCreate,
)


def require_record(
    session: Session, cls: type[Record], project: Project, record_id: uuid.UUID, *, lock: bool = False
) -> Record:
    row = LearningRepository(session).get(cls, project.id, record_id, lock=lock)
    if row is None:
        raise DomainError("learning_record_not_found", "Project learning record was not found", status_code=404)
    return row


def _save(session: Session, project: Project, user: User, row: Record, action: str) -> Record:
    session.add(row)
    session.flush()
    record_audit(
        session,
        action=action,
        entity_type=row.__tablename__,
        entity_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return row


def create_assay(session: Session, project: Project, user: User, payload: AssayCreate) -> LearningAssay:
    return _save(
        session,
        project,
        user,
        LearningAssay(project_id=project.id, created_by=user.id, **payload.model_dump()),
        "learning.assay.create",
    )


def create_study(session: Session, project: Project, user: User, payload: StudyCreate) -> LearningStudy:
    assay = require_record(session, LearningAssay, project, payload.assay_id)
    goal = session.get(ResearchGoal, payload.research_goal_id)
    if goal is None or goal.project_id != project.id:
        raise DomainError("research_goal_not_found", "Project research goal was not found", status_code=404)
    return _save(
        session,
        project,
        user,
        LearningStudy(
            project_id=project.id,
            created_by=user.id,
            goal_snapshot={
                "id": str(goal.id),
                "version": goal.version,
                "title": goal.title,
                "detail": goal.detail,
                "assay_version": assay.version,
                "unit": assay.unit,
            },
            **payload.model_dump(),
        ),
        "learning.study.create",
    )


def create_observation(session: Session, project: Project, user: User, payload: ObservationCreate) -> ExperimentResult:
    assay = require_record(session, LearningAssay, project, payload.assay_id, lock=True)
    if payload.unit != assay.unit:
        raise DomainError("learning_unit_mismatch", "Observation unit must match the assay contract", status_code=422)
    candidate = _candidate(session, project, payload.candidate_id)
    fingerprint = engine.digest(payload.model_dump(mode="json"))
    key = f"learning-observation:{project.id}:{fingerprint}"
    values = payload.model_dump(mode="json")
    return create_idempotent_result(
        session,
        project,
        ExperimentResultCreate(
            candidate_id=candidate.id,
            source_artifact_id=payload.source_artifact_id,
            batch_key=payload.batch_key,
            experiment_type="learning_assay",
            value=payload.value,
            unit=payload.unit,
            pass_status="unknown",
            conclusion=payload.note,
            failure_reason=payload.note if payload.status in {"failed", "missing"} else None,
            result_metadata={"learning": values, "assay_version": assay.version},
        ),
        user,
        request_key=key,
    )


def _candidate(session: Session, project: Project, candidate_id: uuid.UUID) -> Candidate:
    row = session.get(Candidate, candidate_id)
    if row is None or row.project_id != project.id:
        raise DomainError("candidate_not_found", "Project candidate was not found", status_code=404)
    return row


def _features(candidate: Candidate) -> dict:
    sequence = candidate.properties.get("sequence")
    if not isinstance(sequence, str):
        raise ValueError("Candidate has no canonical sequence")
    return engine.features(sequence)


def freeze_dataset(session: Session, project: Project, user: User, payload: DatasetCreate) -> LearningDataset:
    study = require_record(session, LearningStudy, project, payload.study_id, lock=True)
    assay = require_record(session, LearningAssay, project, study.assay_id)
    included, excluded, sources = [], [], []
    for result_id in sorted(payload.result_ids, key=str):
        result = session.get(ExperimentResult, result_id)
        if result is None or result.project_id != project.id:
            raise DomainError("experiment_result_not_found", "Project experiment result was not found", status_code=404)
        context = result.result_metadata.get("learning", {})
        if not isinstance(context, dict) or context.get("assay_id") != str(assay.id) or result.unit != assay.unit:
            raise DomainError(
                "learning_assay_mismatch", "Every result must belong to this exact assay contract", status_code=422
            )
        try:
            observation = ObservationCreate.model_validate(context)
        except ValidationError as exc:
            raise DomainError(
                "learning_observation_invalid", "Result has invalid learning metadata", status_code=422
            ) from exc
        if (
            observation.value != result.value
            or observation.unit != result.unit
            or observation.candidate_id != result.candidate_id
            or observation.source_artifact_id != result.source_artifact_id
            or observation.batch_key != result.batch_key
        ):
            raise DomainError("learning_observation_invalid", "Result and learning metadata disagree", status_code=422)
        sources.append(
            {
                "id": str(result.id),
                "version": result.version,
                "value": result.value,
                "unit": result.unit,
                "source_artifact_id": str(result.source_artifact_id),
                "metadata": result.result_metadata,
            }
        )
        reason = None
        if not context.get("qc_accepted"):
            reason = "qc_not_accepted"
        elif context.get("status") != "measured" or result.value is None:
            reason = "failed_missing_or_censored"
        artifact = session.get(Artifact, result.source_artifact_id) if result.source_artifact_id else None
        if artifact is None or artifact.project_id != project.id or artifact.status != "available":
            reason = "source_artifact_unavailable"
        if not result.candidate_id:
            reason = "candidate_unlinked"
        vector = None
        candidate = None
        if reason is None and result.candidate_id:
            candidate = _candidate(session, project, result.candidate_id)
            try:
                vector = _features(candidate)
            except ValueError:
                reason = "candidate_sequence_unavailable"
        if reason is not None:
            excluded.append({"result_id": str(result.id), "reason": reason})
            continue
        assert vector is not None and artifact is not None and candidate is not None
        included.append(
            {
                "result_id": str(result.id),
                "result_version": result.version,
                "candidate_id": str(result.candidate_id),
                "candidate_version": candidate.version,
                "artifact_sha256": artifact.checksum_sha256,
                "value": result.value,
                "batch_key": result.batch_key,
                "replicate_key": context["replicate_key"],
                "replicate_type": context["replicate_type"],
                **vector,
            }
        )
    manifest = {
        "schema_version": 1,
        "study_id": str(study.id),
        "study_version": study.version,
        "goal": study.goal_snapshot,
        "assay": {
            "id": str(assay.id),
            "version": assay.version,
            "method": assay.method,
            "conditions": assay.conditions,
            "unit": assay.unit,
        },
        "included": included,
        "excluded": excluded,
        "sources": sources,
    }
    checksum = engine.digest(manifest)
    key = f"learning-dataset:{project.id}:{checksum}"
    existing = session.scalar(select(LearningDataset).where(LearningDataset.legacy_id == key))
    if existing is not None:
        return existing
    return _save(
        session,
        project,
        user,
        LearningDataset(
            project_id=project.id,
            created_by=user.id,
            study_id=study.id,
            manifest=manifest,
            digest=checksum,
            legacy_id=key,
        ),
        "learning.dataset.freeze",
    )


def train_model(session: Session, project: Project, user: User, dataset_id: uuid.UUID) -> LearningModel:
    dataset = require_record(session, LearningDataset, project, dataset_id, lock=True)
    if engine.digest(dataset.manifest) != dataset.digest:
        raise DomainError("learning_dataset_integrity", "Frozen dataset digest does not match", status_code=409)
    try:
        parameters, evaluation = engine.train(dataset.manifest["included"])
    except ValueError as exc:
        raise DomainError("learning_insufficient_data", str(exc), status_code=422) from exc
    key = f"learning-model:{dataset.id}:{engine.ALGORITHM}"
    existing = session.scalar(select(LearningModel).where(LearningModel.legacy_id == key))
    if existing is not None:
        return existing
    evaluation["dataset_digest"] = dataset.digest
    evaluation["model_digest"] = engine.digest(parameters)
    return _save(
        session,
        project,
        user,
        LearningModel(
            project_id=project.id,
            created_by=user.id,
            study_id=dataset.study_id,
            dataset_id=dataset.id,
            algorithm=engine.ALGORITHM,
            parameters=parameters,
            evaluation=evaluation,
            status="shadow",
            legacy_id=key,
        ),
        "learning.model.train",
    )


def review_model(
    session: Session, project: Project, user: User, model_id: uuid.UUID, payload: ModelReview, expected: int
) -> LearningModel:
    model = require_record(session, LearningModel, project, model_id)
    # Serialize promotions within the study before locking model rows, avoiding
    # A->study->B / B->study->A deadlocks from concurrent model reviews.
    require_record(session, LearningStudy, project, model.study_id, lock=True)
    model = require_record(session, LearningModel, project, model_id, lock=True)
    if model.version != expected:
        raise DomainError("version_conflict", "Model was changed; reload before review", status_code=412)
    _check_model_integrity(model)
    if payload.action == "promote":
        if model.status != "shadow":
            raise DomainError("learning_model_final", "Only a shadow model can be promoted", status_code=409)
        if not model.evaluation["eligible_for_promotion"]:
            raise DomainError(
                "learning_model_not_eligible", "Model did not beat its frozen mean baseline", status_code=409
            )
        others = session.scalars(
            select(LearningModel).where(
                LearningModel.study_id == model.study_id,
                LearningModel.status == "promoted",
                LearningModel.id != model.id,
            )
        )
        for old in others:
            old.status = "retired"
            old.version += 1
            _save(session, project, user, old, "learning.model.supersede")
        model.status = "promoted"
    else:
        model.status = "retired"
    history = [
        *model.evaluation.get("reviews", []),
        {
            "action": payload.action,
            "rationale": payload.rationale,
            "reviewed_by": str(user.id),
            "at": datetime.now(UTC).isoformat(),
        },
    ]
    model.evaluation = {**model.evaluation, "reviews": history}
    model.version += 1
    return _save(session, project, user, model, "learning.model." + payload.action)


def create_decision(
    session: Session, project: Project, user: User, payload: LearningDecisionCreate
) -> LearningDecision:
    study = require_record(session, LearningStudy, project, payload.study_id)
    model = require_record(session, LearningModel, project, payload.model_id)
    if model.study_id != study.id or model.status == "retired":
        raise DomainError("learning_model_mismatch", "Choose a current model from this study", status_code=409)
    _check_model_integrity(model)
    pool = []
    for item in payload.candidates:
        candidate = _candidate(session, project, item.candidate_id)
        try:
            vector = _features(candidate)
        except ValueError as exc:
            raise DomainError("learning_candidate_sequence", str(exc), status_code=422) from exc
        pool.append(
            {
                "candidate_id": str(candidate.id),
                "candidate_version": candidate.version,
                "candidate_name": candidate.name,
                "cost_cents": item.cost_cents,
                **vector,
            }
        )
    proposal = engine.propose(
        model.parameters,
        pool,
        direction=study.direction,
        budget=study.batch_budget_cents,
        batch_size=study.max_batch_size,
        exploration_fraction=payload.exploration_fraction,
    )
    proposal.update(
        {
            "model_id": str(model.id),
            "model_version": model.version,
            "model_status": model.status,
            "dataset_id": str(model.dataset_id),
            "dataset_digest": model.evaluation["dataset_digest"],
            "study_version": study.version,
            "goal": study.goal_snapshot,
            "currency": study.currency,
            "threshold": study.threshold,
            "direction": study.direction,
            "status": "shadow" if model.status == "shadow" else "proposed",
        }
    )
    return _save(
        session,
        project,
        user,
        LearningDecision(
            project_id=project.id,
            study_id=study.id,
            model_id=model.id,
            created_by=user.id,
            proposal=proposal,
            proposal_digest=engine.digest(proposal),
        ),
        "learning.decision.create",
    )


def _check_model_integrity(model: LearningModel) -> None:
    if engine.digest(model.parameters) != model.evaluation["model_digest"]:
        raise DomainError("learning_model_integrity", "Model parameters do not match their digest", status_code=409)


def review_decision(
    session: Session,
    project: Project,
    user: User,
    decision_id: uuid.UUID,
    payload: LearningDecisionReview,
    expected: int,
) -> LearningDecision:
    row = require_record(session, LearningDecision, project, decision_id)
    study = require_record(session, LearningStudy, project, row.study_id, lock=True)
    row = require_record(session, LearningDecision, project, decision_id, lock=True)
    if row.version != expected:
        raise DomainError("version_conflict", "Decision was changed; reload before review", status_code=412)
    if engine.digest(row.proposal) != row.proposal_digest:
        raise DomainError("learning_proposal_integrity", "Proposal digest does not match", status_code=409)
    if row.review_status != "pending":
        raise DomainError("learning_decision_final", "Create a new proposal to revise this decision", status_code=409)
    if payload.approve:
        model = require_record(session, LearningModel, project, row.model_id)
        if model.status != "promoted" or model.version != row.proposal["model_version"]:
            raise DomainError("learning_decision_stale", "Recompute with the currently promoted model", status_code=409)
        _check_model_integrity(model)
        goal = session.get(ResearchGoal, study.research_goal_id) if study.research_goal_id else None
        if goal is None or goal.version != study.goal_snapshot["version"]:
            raise DomainError(
                "learning_goal_changed", "Freeze a new study for the changed research goal", status_code=409
            )
        for item in row.proposal["selected"]:
            candidate = _candidate(session, project, uuid.UUID(item["candidate_id"]))
            try:
                sequence_digest = _features(candidate)["sequence_sha256"]
            except ValueError:
                sequence_digest = None
            if candidate.version != item["candidate_version"] or sequence_digest != item["sequence_sha256"]:
                raise DomainError("learning_candidate_changed", "Recompute after candidate changes", status_code=409)
    row.review_status = "approved" if payload.approve else "rejected"
    row.review_note, row.reviewed_by = payload.rationale, user.id
    entry = create_entry(
        session,
        project,
        TimelineEntryCreate(
            occurred_at=datetime.now(UTC),
            entry_type="decision",
            title=f"Learning batch: {row.review_status}",
            body=payload.rationale,
            provenance={"candidate_ids": [i["candidate_id"] for i in row.proposal["selected"]]},
            tags=["learning", "v2.6"],
        ),
        user,
    )
    row.timeline_entry_id = entry.id
    if study.research_goal_id:
        goal = session.get(ResearchGoal, study.research_goal_id)
        if goal is not None:
            goals.attach(session, goal, user.id, resource_type="timeline_entry", resource_id=entry.id)
    row.version += 1
    return _save(session, project, user, row, "learning.decision.review")


def export_decision(session: Session, project: Project, decision_id: uuid.UUID) -> dict:
    from .schemas import AssayResponse, DatasetResponse, LearningDecisionResponse, ModelResponse, StudyResponse

    decision = require_record(session, LearningDecision, project, decision_id)
    model = require_record(session, LearningModel, project, decision.model_id)
    study = require_record(session, LearningStudy, project, decision.study_id)
    dataset = require_record(session, LearningDataset, project, model.dataset_id)
    assay = require_record(session, LearningAssay, project, study.assay_id)
    _check_model_integrity(model)
    if (
        engine.digest(dataset.manifest) != dataset.digest
        or engine.digest(decision.proposal) != decision.proposal_digest
    ):
        raise DomainError("learning_export_integrity", "Evidence package integrity check failed", status_code=409)
    content = {
        "assay": AssayResponse.model_validate(assay).model_dump(mode="json"),
        "study": StudyResponse.model_validate(study).model_dump(mode="json"),
        "dataset": DatasetResponse.model_validate(dataset).model_dump(mode="json"),
        "model": ModelResponse.model_validate(model).model_dump(mode="json"),
        "decision": LearningDecisionResponse.model_validate(decision).model_dump(mode="json"),
        "limits": [
            "Raw artifact bytes are referenced, not embedded",
            "Model review state is current; proposal records the decision-time version",
            "Review does not authorize experimental execution or spending",
        ],
    }
    return {"schema_version": 1, "checksum": engine.digest(content), "content": content}
