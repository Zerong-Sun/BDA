"""Target intelligence runs and exports.

Moved out of ``compute.tasks``, which had grown to hold this domain's tasks alongside a
dozen others. Task names and queue routing are unchanged.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

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


def gather_druggability(tools: Any, target: dict[str, Any], trial_term: str) -> dict[str, Any]:
    """Retrieve the public evidence for one target, recording every call.

    Takes the evidence service as an argument so it can be exercised without a
    network. Each failure is named for what failed: "UniProt could not be
    reached" and "UniProt has no Open Targets cross-reference" lead a reader to
    opposite conclusions, and collapsing them would send someone to fix a
    mapping that is not missing.
    """
    from . import druggability

    retrieval: dict[str, Any] = {}
    failures: list[str] = []
    ensembl_id: str | None = None
    open_targets: dict[str, Any] | None = None
    trials: dict[str, Any] | None = None

    accession = str(target.get("uniprot_accession") or "").strip()
    mapping_retrieved = False
    if accession:
        try:
            uniprot = tools.get_uniprot(accession)
            retrieval["uniprot_mapping"] = uniprot.audit
            mapping_retrieved = True
            ensembl_id = druggability.ensembl_from_uniprot(uniprot.data)
        except (RuntimeError, ValueError) as exc:
            failures.append(f"UniProt entry {accession} could not be retrieved ({exc}); nothing downstream was queried.")

    if ensembl_id:
        try:
            result = tools.get_open_targets_druggability(ensembl_id)
            retrieval["open_targets"] = result.audit
            open_targets = result.data.get("data")
        except (RuntimeError, ValueError) as exc:
            failures.append(f"Open Targets could not be queried for {ensembl_id} ({exc}).")

    if trial_term:
        counts: dict[str, int | None] = {}
        audits: list[dict[str, Any]] = []
        for phase in (None, *druggability.TRIAL_PHASES):
            key = phase or "ALL"
            try:
                result = tools.count_clinical_trials(trial_term, phase=phase)
                total = result.data.get("totalCount")
                counts[key] = total if isinstance(total, int) else None
                audits.append(result.audit)
            except (RuntimeError, ValueError) as exc:
                counts[key] = None
                failures.append(f"ClinicalTrials.gov count for {key} could not be retrieved ({exc}).")
        retrieval["clinical_trials"] = audits
        trials = druggability.trial_activity(counts, query=trial_term)

    report = druggability.assessment(
        target=target, ensembl_id=ensembl_id, open_targets=open_targets, trials=trials
    )
    if not mapping_retrieved:
        # The kernel's "no cross-reference" gap would be false here: the entry
        # was never read, so whether it has one is unknown.
        report["gaps"] = [gap for gap in report["gaps"] if "no Open Targets cross-reference" not in gap]
    report["gaps"].extend(failures)
    report["retrieval"] = retrieval
    return report


def _druggability_summary(report: dict[str, Any]) -> str:
    """One line a reader can check against the report, and nothing it does not contain."""
    parts: list[str] = []
    supported = [row["name"] for row in (report.get("tractability") or []) if row.get("supported")]
    if report.get("tractability") is not None:
        parts.append("Tractable modalities: " + (", ".join(supported) if supported else "none supported"))
    candidates = report.get("clinical_candidates")
    if candidates is not None:
        parts.append(f"{candidates['approved']} approved of {candidates['reported_count']} drugs and candidates")
    trials = report.get("trial_activity")
    if trials is not None and trials.get("total_matching") is not None:
        parts.append(f"{trials['total_matching']} registered trials matching '{trials['query']}'")
    if report.get("gaps"):
        parts.append(f"{len(report['gaps'])} gap(s) recorded")
    parts.append("Evidence only; no druggability probability is given.")
    return ". ".join(parts)


@celery_app.task(name="bda_v2.druggability_assessment")
def druggability_assessment(run_id: str) -> dict:
    from ..research.evidence_tools import EvidenceToolService
    from ..targets.models import Target
    from .druggability_service import DRUGGABILITY_KIND
    from .models import IntelligenceEvidence, IntelligenceReport, IntelligenceRun

    parsed = uuid.UUID(run_id)
    with session_scope() as session:
        run = session.get(IntelligenceRun, parsed)
        if run is None or (run.query or {}).get("kind") != DRUGGABILITY_KIND:
            return {"run_id": run_id, "status": "missing"}
        if run.status != "pending":
            return {"run_id": run_id, "status": run.status}
        target = session.get(Target, run.target_id)
        target_view: dict[str, Any] = (
            {
                "id": str(target.id),
                "name": target.name,
                "uniprot_accession": target.uniprot_accession,
                "organism": target.organism,
            }
            if target
            else {"id": str(run.target_id)}
        )
        trial_term = str((run.query or {}).get("trial_term") or target_view.get("name") or "").strip()
        run.status = "running"
        run.version += 1

    tools = EvidenceToolService(max_calls=12, timeout_seconds=30.0)
    try:
        report = gather_druggability(tools, target_view, trial_term)
    finally:
        tools.close()

    retrieval = report.get("retrieval") or {}
    sections = {
        "tractability": retrieval.get("open_targets"),
        "clinical_candidates": retrieval.get("open_targets"),
        "safety_liabilities": retrieval.get("open_targets"),
        "trial_activity": retrieval.get("clinical_trials"),
    }
    with session_scope() as session:
        run = session.get(IntelligenceRun, parsed)
        if run is None:
            return {"run_id": run_id, "status": "missing"}
        for section, audit in sections.items():
            if report.get(section) is None:
                continue
            session.add(
                IntelligenceEvidence(
                    run_id=run.id,
                    evidence_type=f"druggability_{section}",
                    # The audit is the citation: tool, request, time and response
                    # checksum, so a row can be traced to the exact response.
                    citation={"retrieval": audit},
                    content=json.dumps(report[section], ensure_ascii=False, sort_keys=True),
                    confidence=None,
                )
            )
        session.add(
            IntelligenceReport(
                run_id=run.id,
                title=f"Druggability evidence: {target_view.get('name') or target_view['id']}",
                summary=_druggability_summary(report),
                content=report,
            )
        )
        run.status = "succeeded"
        run.version += 1
    return {"run_id": run_id, "status": "succeeded", "gaps": len(report.get("gaps") or [])}
