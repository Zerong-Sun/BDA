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
from . import engine, validation
from .models import LearningAssay, LearningBatch, LearningDataset, LearningDecision, LearningModel, LearningStudy
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
    if payload.supersedes_id:
        previous = require_record(session, LearningStudy, project, payload.supersedes_id, lock=True)
        if previous.research_goal_id != goal.id:
            raise DomainError("learning_revision_goal", "A revision must retain its research goal", status_code=422)
    if payload.stop_on_threshold and payload.threshold is None:
        raise DomainError("learning_stop_threshold", "Stopping on target requires a numeric threshold", status_code=422)
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
                "selection_constraints": payload.selection_constraints.model_dump(mode="json"),
            },
            **payload.model_dump(exclude={"selection_constraints"}),
        ),
        "learning.study.create",
    )


def validate_observation(
    session: Session, project: Project, payload: ObservationCreate
) -> tuple[LearningAssay, Candidate, str, dict]:
    assay = require_record(session, LearningAssay, project, payload.assay_id, lock=True)
    if payload.unit != assay.unit:
        raise DomainError("learning_unit_mismatch", "Observation unit must match the assay contract", status_code=422)
    candidate = _candidate(session, project, payload.candidate_id)
    fingerprint = engine.digest(payload.model_dump(mode="json"))
    key = f"learning-observation:{project.id}:{fingerprint}"
    values = payload.model_dump(mode="json")
    if payload.measurement_key:
        key = f"learning-measurement:{project.id}:" + engine.digest(
            [str(assay.id), str(payload.source_artifact_id), payload.measurement_key]
        )
    keys = [key]
    if (
        not payload.measurement_key
        and not payload.family_key
        and not payload.observed_at
        and payload.sample_role == "candidate"
    ):
        legacy = payload.model_dump(
            mode="json", exclude={"family_key", "observed_at", "sample_role", "measurement_key"}
        )
        keys.append(f"learning-observation:{project.id}:{engine.digest(legacy)}")
    existing = session.scalar(
        select(ExperimentResult)
        .where(ExperimentResult.project_id == project.id, ExperimentResult.legacy_id.in_(keys))
        .order_by(ExperimentResult.created_at)
        .limit(1)
    )
    if (
        existing is not None
        and ObservationCreate.model_validate(existing.result_metadata.get("learning")).model_dump(mode="json") != values
    ):
        raise DomainError(
            "learning_measurement_conflict",
            "Measurement key already identifies different data; withdraw the original and use a new measurement key",
            status_code=409,
        )
    if existing is not None:
        key = existing.legacy_id or key
    if payload.batch_key.startswith("learning:"):
        try:
            batch_id = uuid.UUID(payload.batch_key.removeprefix("learning:"))
        except ValueError as exc:
            raise DomainError("learning_batch_key", "Malformed learning batch key", status_code=422) from exc
        batch = require_record(session, LearningBatch, project, batch_id)
        if batch.manifest["assay_id"] != str(assay.id):
            raise DomainError("learning_batch_mismatch", "Batch uses a different assay", status_code=422)
        if batch.receipt is not None and existing is None:
            raise DomainError(
                "learning_batch_received",
                "Batch is already received; use a new batch for additional results",
                status_code=409,
            )
    artifact = session.get(Artifact, payload.source_artifact_id)
    if artifact is None or artifact.project_id != project.id or artifact.status != "available":
        raise DomainError("learning_source_unavailable", "Project source artifact is not available", status_code=404)
    return assay, candidate, key, values


def create_observation(session: Session, project: Project, user: User, payload: ObservationCreate) -> ExperimentResult:
    assay, candidate, key, values = validate_observation(session, project, payload)
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
        if result.result_metadata.get("learning_withdrawal"):
            reason = "measurement_withdrawn"
        elif not context.get("qc_accepted"):
            reason = "qc_not_accepted"
        elif observation.sample_role != "candidate":
            reason = "assay_control"
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
                "family_key": observation.family_key,
                "observed_at": observation.observed_at.isoformat() if observation.observed_at else None,
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


def train_model(
    session: Session,
    project: Project,
    user: User,
    dataset_id: uuid.UUID,
    algorithm: str = "knn",
    strategy: str = "sequence",
    calibrate: bool = False,
) -> LearningModel:
    dataset = require_record(session, LearningDataset, project, dataset_id, lock=True)
    if engine.digest(dataset.manifest) != dataset.digest:
        raise DomainError("learning_dataset_integrity", "Frozen dataset digest does not match", status_code=409)
    try:
        parameters, evaluation = validation.train(dataset.manifest["included"], algorithm, strategy, calibrate)
    except ValueError as exc:
        raise DomainError("learning_insufficient_data", str(exc), status_code=422) from exc
    algorithm_name = f"composition-{algorithm}-{strategy}-v2" + ("-conformal" if calibrate else "")
    key = f"learning-model:{dataset.id}:{algorithm_name}"
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
            algorithm=algorithm_name,
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
    if payload.action in {"promote", "rollback"}:
        _check_model_sources(session, project, model)
        required_status = "retired" if payload.action == "rollback" else "shadow"
        if model.status != required_status:
            raise DomainError("learning_model_final", "Only a shadow model can be promoted", status_code=409)
        if payload.action == "rollback" and not any(
            r["action"] in {"promote", "rollback"} for r in model.evaluation.get("reviews", [])
        ):
            raise DomainError(
                "learning_rollback_unreviewed", "Rollback requires a previously promoted model", status_code=409
            )
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
    study = require_record(session, LearningStudy, project, payload.study_id, lock=True)
    model = require_record(session, LearningModel, project, payload.model_id)
    if model.study_id != study.id or model.status == "retired":
        raise DomainError("learning_model_mismatch", "Choose a current model from this study", status_code=409)
    _check_model_integrity(model)
    _check_model_sources(session, project, model)
    secondary = None
    secondary_study = None
    if payload.secondary_model_id:
        secondary = require_record(session, LearningModel, project, payload.secondary_model_id)
        secondary_study = require_record(session, LearningStudy, project, secondary.study_id)
        if secondary.id == model.id or secondary.status == "retired" or secondary_study.assay_id == study.assay_id:
            raise DomainError(
                "learning_secondary_model", "Choose a current model of a different assay", status_code=422
            )
        _check_model_integrity(secondary)
        _check_model_sources(session, project, secondary)
    batches = list(session.scalars(select(LearningBatch).where(LearningBatch.study_id == study.id)))
    stop_reason = "stop_round_limit" if len(batches) >= study.max_rounds else None
    if study.stop_on_threshold and study.threshold is not None:
        dataset = require_record(session, LearningDataset, project, model.dataset_id)
        values = [p["value"] for p in validation.aggregate(dataset.manifest["included"])]
        if max(values) >= study.threshold if study.direction == "maximize" else min(values) <= study.threshold:
            stop_reason = "stop_target_reached"
    pool = []
    constraints = study.goal_snapshot.get("selection_constraints", {})
    constrained_out = []
    for item in payload.candidates:
        candidate = _candidate(session, project, item.candidate_id)
        try:
            vector = _features(candidate)
        except ValueError as exc:
            raise DomainError("learning_candidate_sequence", str(exc), status_code=422) from exc
        sequence = "".join(candidate.properties["sequence"].split()).upper()
        if (
            not constraints.get("min_length", 1) <= len(sequence) <= constraints.get("max_length", 10000)
            or any(motif in sequence for motif in constraints.get("forbidden_motifs", []))
            or item.cost_cents > (constraints.get("max_candidate_cost_cents") or 100_000_000)
        ):
            constrained_out.append({"candidate_id": str(candidate.id), "reason": "frozen_selection_constraint"})
            continue
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
        retest_candidates=[str(i) for i in payload.retest_candidates],
        secondary_parameters=secondary.parameters if secondary else None,
        secondary_direction=secondary_study.direction if secondary_study else "maximize",
        stop_reason=stop_reason,
        allow_out_of_domain=constraints.get("allow_out_of_domain", True),
    )
    proposal["excluded"].extend(constrained_out)
    proposal["selection_constraints"] = constraints
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
            "secondary_model": {
                "id": str(secondary.id),
                "version": secondary.version,
                "study_id": str(secondary.study_id),
                "direction": secondary_study.direction,
                "unit": secondary_study.goal_snapshot["unit"],
                "status": secondary.status,
            }
            if secondary and secondary_study
            else None,
        }
    )
    from .lifecycle import learning_state_digest

    proposal["learning_state_digest"] = learning_state_digest(session, project, study)
    if secondary_study:
        proposal["secondary_model"]["learning_state_digest"] = learning_state_digest(session, project, secondary_study)
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


def _check_model_sources(session: Session, project: Project, model: LearningModel) -> None:
    """New results may coexist with an older model; changed/withdrawn sources may not."""
    dataset = require_record(session, LearningDataset, project, model.dataset_id)
    if engine.digest(dataset.manifest) != dataset.digest:
        raise DomainError("learning_dataset_integrity", "Frozen dataset digest does not match", status_code=409)
    for source in dataset.manifest.get("sources", []):
        result = session.get(ExperimentResult, uuid.UUID(source["id"]))
        if (
            result is None
            or result.project_id != project.id
            or result.version != source["version"]
            or result.value != source["value"]
            or result.unit != source["unit"]
            or result.result_metadata != source["metadata"]
            or str(result.source_artifact_id) != source["source_artifact_id"]
        ):
            raise DomainError(
                "learning_source_changed",
                "Model source results changed; freeze and train a new dataset",
                status_code=409,
            )
    for included in dataset.manifest.get("included", []):
        result = session.get(ExperimentResult, uuid.UUID(included["result_id"]))
        artifact = session.get(Artifact, result.source_artifact_id) if result and result.source_artifact_id else None
        candidate = session.get(Candidate, uuid.UUID(included["candidate_id"]))
        try:
            same_sequence = (
                candidate is not None and _features(candidate)["sequence_sha256"] == included["sequence_sha256"]
            )
        except ValueError:
            same_sequence = False
        if (
            artifact is None
            or artifact.project_id != project.id
            or artifact.status != "available"
            or artifact.checksum_sha256 != included["artifact_sha256"]
            or not same_sequence
        ):
            raise DomainError("learning_source_changed", "Model source artifact or sequence changed", status_code=409)


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
        from .lifecycle import check_current

        check_current(session, project, row, study)
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
    secondary = decision.proposal.get("secondary_model")
    if secondary:
        content["secondary_evidence"] = export_model_context(session, project, uuid.UUID(secondary["id"]))
    return {"schema_version": 1, "checksum": engine.digest(content), "content": content}


def export_model_context(session: Session, project: Project, model_id: uuid.UUID) -> dict:
    """Include the source contract and frozen data behind another assay's prediction."""
    from .schemas import AssayResponse, DatasetResponse, ModelResponse, StudyResponse

    model = require_record(session, LearningModel, project, model_id)
    study = require_record(session, LearningStudy, project, model.study_id)
    assay = require_record(session, LearningAssay, project, study.assay_id)
    dataset = require_record(session, LearningDataset, project, model.dataset_id)
    _check_model_integrity(model)
    if engine.digest(dataset.manifest) != dataset.digest or model.evaluation["dataset_digest"] != dataset.digest:
        raise DomainError("learning_export_integrity", "Secondary dataset integrity check failed", status_code=409)
    return {
        "study": StudyResponse.model_validate(study).model_dump(mode="json"),
        "assay": AssayResponse.model_validate(assay).model_dump(mode="json"),
        "dataset": DatasetResponse.model_validate(dataset).model_dump(mode="json"),
        "model": ModelResponse.model_validate(model).model_dump(mode="json"),
    }
