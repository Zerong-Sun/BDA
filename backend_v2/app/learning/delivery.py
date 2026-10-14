"""Portable, hashed project learning history with explicit evidence and cost scope."""

from __future__ import annotations

import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.problem import DomainError
from ..experiments.models import ExperimentResult
from ..experiments.schemas import ExperimentResultResponse
from ..projects.models import Project
from . import engine, lifecycle, service
from .models import (
    LearningAssay,
    LearningBatch,
    LearningDataset,
    LearningDecision,
    LearningEvidence,
    LearningModel,
    LearningStudy,
)
from .schemas import (
    AssayResponse,
    BatchResponse,
    DatasetResponse,
    EvidenceResponse,
    LearningDecisionResponse,
    ModelResponse,
    StudyResponse,
)


def export_study(session: Session, project: Project, study_id: uuid.UUID) -> dict:
    study = service.require_record(session, LearningStudy, project, study_id)
    assay = service.require_record(session, LearningAssay, project, study.assay_id)
    content: dict = {
        "study": StudyResponse.model_validate(study).model_dump(mode="json"),
        "assay": AssayResponse.model_validate(assay).model_dump(mode="json"),
    }
    tables: list[
        tuple[
            str,
            type[LearningDataset | LearningModel | LearningDecision | LearningEvidence | LearningBatch],
            type[BaseModel],
        ]
    ] = [
        ("datasets", LearningDataset, DatasetResponse),
        ("models", LearningModel, ModelResponse),
        ("decisions", LearningDecision, LearningDecisionResponse),
        ("evidence", LearningEvidence, EvidenceResponse),
        ("batches", LearningBatch, BatchResponse),
    ]
    for key, cls, schema in tables:
        records = list(
            session.scalars(
                select(cls)
                .where(cls.project_id == project.id, cls.study_id == study_id)
                .order_by(cls.created_at, cls.id)
                .limit(5001)
            )
        )
        if len(records) > 5000:
            raise DomainError("learning_export_limit", "Study exceeds the interactive export limit", status_code=413)
        content[key] = [schema.model_validate(r).model_dump(mode="json") for r in records]
    for dataset in content["datasets"]:
        if engine.digest(dataset["manifest"]) != dataset["digest"]:
            raise DomainError("learning_export_integrity", "Dataset integrity check failed", status_code=409)
    for model in content["models"]:
        if engine.digest(model["parameters"]) != model["evaluation"]["model_digest"]:
            raise DomainError("learning_export_integrity", "Model integrity check failed", status_code=409)
    for decision in content["decisions"]:
        if engine.digest(decision["proposal"]) != decision["proposal_digest"]:
            raise DomainError("learning_export_integrity", "Decision integrity check failed", status_code=409)
    for batch in content["batches"]:
        receipt = batch["receipt"]
        if engine.digest(batch["manifest"]) != batch["digest"] or (
            receipt and engine.digest({k: v for k, v in receipt.items() if k != "checksum"}) != receipt["checksum"]
        ):
            raise DomainError("learning_export_integrity", "Batch integrity check failed", status_code=409)
    results = list(
        session.scalars(
            select(ExperimentResult)
            .where(
                ExperimentResult.project_id == project.id,
                ExperimentResult.result_metadata["learning"]["assay_id"].as_string() == str(assay.id),
            )
            .order_by(ExperimentResult.created_at, ExperimentResult.id)
            .limit(10001)
        )
    )
    if len(results) > 10000:
        raise DomainError("learning_export_limit", "Study exceeds the interactive observation limit", status_code=413)
    content["observations"] = [ExperimentResultResponse.model_validate(r).model_dump(mode="json") for r in results]
    secondary_ids = sorted(
        {d["proposal"]["secondary_model"]["id"] for d in content["decisions"] if d["proposal"].get("secondary_model")}
    )
    content["secondary_evidence"] = [
        service.export_model_context(session, project, uuid.UUID(model_id)) for model_id in secondary_ids
    ]
    content["learning_state_digest"] = lifecycle.learning_state_digest(session, project, study)
    content["cost_summary"] = {
        "currency": study.currency,
        "estimated_experiment_cents": sum(b["manifest"]["estimated_cost_cents"] for b in content["batches"]),
        "reported_experiment_cents": sum(b["receipt"]["actual_cost_cents"] for b in content["batches"] if b["receipt"]),
        "outstanding_receipts": sum(b["receipt"] is None for b in content["batches"]),
        "basis": "Operator-reported totals, including failed samples; excludes compute, labor and invoices",
    }
    content["release_evidence"] = {
        "completed_batches": sum(b["receipt"] is not None for b in content["batches"]),
        "prospective_benefit_verified": False,
        "scientific_release_gate": "Independent real-experiment validation required",
    }
    content["limits"] = [
        "Source artifact bytes are referenced, not embedded; export them through the artifact service",
        "Completed software rounds do not certify wet-lab provenance or scientific benefit",
        "Retrospective model promotion is not prospective validation",
        "External experiments are handed off to a person; no supplier order or payment is submitted",
    ]
    return {"schema_version": 2, "checksum": engine.digest(content), "content": content}
