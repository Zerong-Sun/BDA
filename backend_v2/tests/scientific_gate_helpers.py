"""Synthetic, explicitly reviewed source contracts for workflow execution tests."""

import uuid

from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.literature.models import LiteratureChunk, LiteratureDocument
from backend_v2.app.workflows.scientific_gates import (
    ScientificEvidenceCreate,
    ScientificEvidenceReview,
    binding,
    review_evidence,
    save_evidence,
)


def candidate_payload(env, workflow, edge):
    session = env["session"]
    document = LiteratureDocument(
        project_id=workflow.project_id, title="Synthetic gate calibration", source="synthetic", external_id="test-only"
    )
    session.add(document)
    session.flush()
    chunk = LiteratureChunk(
        document_id=document.id,
        position=0,
        content="Synthetic measurements support this test threshold only; no biological claim is made.",
    )
    report = Artifact(
        project_id=workflow.project_id,
        created_by=env["user"].id,
        artifact_type="analysis_report",
        filename="calibration.md",
        content_type="text/markdown",
        object_key=f"test/{uuid.uuid4()}",
        size_bytes=10,
        checksum_sha256="b" * 64,
    )
    raw = Artifact(
        project_id=workflow.project_id,
        created_by=env["user"].id,
        artifact_type="dataset",
        filename="controls.csv",
        content_type="text/csv",
        object_key=f"test/{uuid.uuid4()}",
        size_bytes=10,
        checksum_sha256="c" * 64,
    )
    session.add_all([chunk, report, raw])
    session.flush()
    current = binding(session, workflow, edge)
    methods = current["required_methods"]
    return ScientificEvidenceCreate(
        workflow_version=workflow.version,
        sources=[
            {
                "document_id": document.id,
                "chunk_id": chunk.id,
                "quote": chunk.content,
                "locator": "Synthetic table 1",
                "supported_methods": list({m["method_key"] for m in methods.values()}),
            }
        ],
        parameters=[
            {
                "path": path,
                "value": value,
                "unit": "synthetic",
                "meaning": "Synthetic regression threshold only",
                **methods[path],
                "source_indexes": [0],
            }
            for path, value in current["required_parameters"].items()
        ],
        calibration={
            "artifact_id": report.id,
            "raw_data_artifact_ids": [raw.id],
            "positive_controls": ["synthetic-positive"],
            "negative_controls": ["synthetic-negative"],
            "construct": "Synthetic test fixture",
            "protocol": "Synthetic calibration; not biological evidence",
            "acceptance_criteria": "Synthetic positive passes and negative fails",
            "summary": "Synthetic calibration for workflow execution regression tests",
        },
        applicability="Only synthetic workflow regression cases; not for biological decisions",
    )


def approve_test_gate(env, workflow, edge=None):
    edge = edge or workflow.graph["edges"][0]
    payload = candidate_payload(env, workflow, edge)
    candidate = save_evidence(workflow.id, edge["id"], payload, env["session"], env["user"])
    review_evidence(
        workflow.id,
        edge["id"],
        uuid.UUID(candidate["id"]),
        ScientificEvidenceReview(
            workflow_version=workflow.version,
            decision="approve",
            rationale="Synthetic test fixture checked against positive and negative controls",
        ),
        env["session"],
        env["user"],
    )
    return candidate
