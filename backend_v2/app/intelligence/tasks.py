"""Target intelligence runs and exports.

Moved out of ``compute.tasks``, which had grown to hold this domain's tasks alongside a
dozen others. Task names and queue routing are unchanged.
"""

from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import select

from ..artifacts.models import Artifact
from ..artifacts.storage import ObjectStorage
from ..core.celery_app import celery_app
from ..core.database import SessionFactory, session_scope


@celery_app.task(name="bda_v2.intelligence_run")
def intelligence_run(run_id: str) -> dict:
    from ..intelligence.models import (
        DesignRoute,
        IntelligenceEvidence,
        IntelligenceHotspot,
        IntelligenceReport,
        IntelligenceRun,
    )
    from ..knowledge.models import KnowledgeEntry
    from ..literature.models import LiteratureClaim, LiteratureDocument
    from ..targets.models import Target

    parsed = uuid.UUID(run_id)
    with session_scope() as session:
        row = session.get(IntelligenceRun, parsed)
        if row and row.status == "pending":
            target = session.get(Target, row.target_id)
            knowledge = list(
                session.scalars(
                    select(KnowledgeEntry)
                    .where(KnowledgeEntry.project_id == row.project_id)
                    .order_by(KnowledgeEntry.created_at.desc())
                    .limit(20)
                )
            )
            claims = list(
                session.scalars(
                    select(LiteratureClaim)
                    .join(LiteratureDocument, LiteratureDocument.id == LiteratureClaim.document_id)
                    .where(LiteratureDocument.project_id == row.project_id)
                    .order_by(LiteratureClaim.created_at.desc())
                    .limit(50)
                )
            )
            evidence_items = []
            for knowledge_item in knowledge:
                evidence_items.append(
                    IntelligenceEvidence(
                        run_id=row.id,
                        evidence_type="knowledge",
                        citation=knowledge_item.source,
                        content=knowledge_item.content,
                        confidence=None,
                    )
                )
            for claim_item in claims:
                evidence_items.append(
                    IntelligenceEvidence(
                        run_id=row.id,
                        evidence_type="literature_claim",
                        citation={"claim_id": str(claim_item.id), "document_id": str(claim_item.document_id)},
                        content=claim_item.claim,
                        confidence=None,
                    )
                )
            session.add_all(evidence_items)
            summary_parts = [
                f"Target: {target.name if target else row.target_id}",
                f"Evidence items: {len(evidence_items)}",
                "Human review is required before applying a design route.",
            ]
            session.add(
                IntelligenceReport(
                    run_id=row.id,
                    title="Target intelligence report",
                    summary=" ".join(summary_parts),
                    content={
                        "query": row.query,
                        "target": {
                            "id": str(target.id),
                            "name": target.name,
                            "uniprot_accession": target.uniprot_accession,
                            "organism": target.organism,
                        }
                        if target
                        else None,
                        "evidence_count": len(evidence_items),
                    },
                )
            )
            session.add(
                IntelligenceHotspot(
                    run_id=row.id,
                    label="Review-required candidate region",
                    residues=[],
                    rationale="No residues are asserted until reviewed structural evidence is available.",
                )
            )
            session.add(
                DesignRoute(
                    run_id=row.id,
                    name="Structure-conditioned design",
                    workflow_spec={
                        "name": "Structure-conditioned design",
                        "nodes": [],
                        "edges": [],
                        "source_intelligence_run_id": str(row.id),
                    },
                )
            )
            row.status = "succeeded"
            row.version += 1
    return {"run_id": run_id, "status": "succeeded"}


@celery_app.task(name="bda_v2.intelligence_export")
def intelligence_export(run_id: str) -> dict:
    from ..intelligence.models import IntelligenceReport, IntelligenceRun

    parsed = uuid.UUID(run_id)
    key = f"intelligence/{parsed}/report.json"
    with SessionFactory() as session:
        run = session.get(IntelligenceRun, parsed)
        if run is None:
            return {"run_id": run_id, "status": "ignored"}
        existing = session.scalar(select(Artifact).where(Artifact.object_key == key))
        if existing:
            return {"run_id": run_id, "status": "available", "artifact_id": str(existing.id)}
        report = session.scalar(select(IntelligenceReport).where(IntelligenceReport.run_id == parsed))
        payload = {
            "schema_version": "1",
            "run_id": run_id,
            "query": run.query,
            "report": (
                {"title": report.title, "summary": report.summary, "content": report.content} if report else None
            ),
        }
        project_id, created_by = run.project_id, run.created_by
    data = json.dumps(payload, sort_keys=True, indent=2).encode()
    checksum = hashlib.sha256(data).hexdigest()
    ObjectStorage().put_bytes(key, data, "application/json")
    with session_scope() as session:
        existing = session.scalar(select(Artifact).where(Artifact.object_key == key))
        if existing is None:
            existing = Artifact(
                project_id=project_id,
                created_by=created_by,
                artifact_type="intelligence_report",
                filename=f"intelligence-{run_id}.json",
                content_type="application/json",
                object_key=key,
                size_bytes=len(data),
                checksum_sha256=checksum,
                lineage={"intelligence_run_id": run_id},
            )
            session.add(existing)
            session.flush()
        artifact_id = existing.id
    return {"run_id": run_id, "status": "available", "artifact_id": str(artifact_id)}
