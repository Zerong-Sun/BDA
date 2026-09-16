"""Target intelligence runs and exports.

Moved out of ``compute.tasks``, which had grown to hold this domain's tasks alongside a
dozen others. Task names and queue routing are unchanged.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import func, select

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


def gather_druggability(
    tools: Any,
    target: dict[str, Any],
    trial_term: str,
    *,
    patent_priority_years: dict[str, int] | None = None,
    current_year: int | None = None,
    literature: dict[str, Any] | None = None,
) -> dict[str, Any]:
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

    trend: dict[str, Any] | None = None
    sponsors: dict[str, Any] | None = None
    if trial_term and current_year is not None:
        by_year: dict[int, int | None] = {}
        trend_audits: list[dict[str, Any]] = []
        for year in range(current_year - druggability.TREND_YEARS + 1, current_year + 1):
            try:
                result = tools.count_clinical_trials(trial_term, start_year=year)
                total = result.data.get("totalCount")
                by_year[year] = total if isinstance(total, int) else None
                trend_audits.append(result.audit)
            except (RuntimeError, ValueError) as exc:
                by_year[year] = None
                failures.append(f"ClinicalTrials.gov count for start year {year} could not be retrieved ({exc}).")
        retrieval["clinical_trials_trend"] = trend_audits
        trend = druggability.registration_trend(by_year, current_year=current_year)

        sponsor_counts = druggability.SponsorAccumulator()
        seen_tokens: set[str] = set()
        pagination_exhausted = False
        sponsor_audits: list[dict[str, Any]] = []
        page_token: str | None = None
        for _page in range(druggability.MAX_SPONSOR_PAGES):
            try:
                result = tools.list_clinical_trial_sponsors(trial_term, page_token=page_token)
            except (RuntimeError, ValueError) as exc:
                failures.append(f"ClinicalTrials.gov sponsor page could not be retrieved ({exc}); the mix is partial.")
                break
            sponsor_audits.append(result.audit)
            sponsor_counts.add(result.data.get("studies") or [])
            page_token = result.data.get("nextPageToken")
            if not page_token:
                pagination_exhausted = True
                break
            if page_token in seen_tokens:
                failures.append("ClinicalTrials.gov repeated a page token; sponsor pagination stopped as partial.")
                break
            seen_tokens.add(page_token)
        retrieval["clinical_trials_sponsors"] = sponsor_audits
        total_matching = (trials or {}).get("total_matching")
        sponsors = sponsor_counts.result(total_matching)
        sponsors["complete"] = bool(sponsors["complete"] and pagination_exhausted)
        sponsors["pagination_exhausted"] = pagination_exhausted
        sponsors["pages_read"] = len(sponsor_audits)
        sponsors["page_limit"] = druggability.MAX_SPONSOR_PAGES
        if not pagination_exhausted and len(sponsor_audits) == druggability.MAX_SPONSOR_PAGES:
            failures.append("ClinicalTrials.gov sponsor page limit reached; the mix is partial, not extrapolated.")

    report = druggability.assessment(
        target=target,
        ensembl_id=ensembl_id,
        open_targets=open_targets,
        trials=trials,
        literature=literature,
    )
    report["market_landscape"] = druggability.market_landscape(
        candidates=report.get("clinical_candidates"),
        trend=trend,
        sponsors=sponsors,
        patent_priority_years=patent_priority_years,
    )
    if not patent_priority_years:
        # Actionable rather than silent: the trend exists once a search is saved.
        report["gaps"].append(
            "No patents are saved for this project, so filing trends are absent. Run a patent search to include them."
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
    sponsors = (report.get("market_landscape") or {}).get("sponsor_mix")
    if sponsors and sponsors.get("industry_share") is not None:
        scope = "all" if sponsors.get("complete") else f"{sponsors['studies_aggregated']} retrieved"
        parts.append(f"Industry leads {round(sponsors['industry_share'] * 100)}% of {scope} registrations")
    saved = report.get("literature_signal")
    if saved is not None:
        parts.append(f"{saved['saved_papers']} papers and {saved['saved_patents']} patents saved in this project")
    if report.get("gaps"):
        parts.append(f"{len(report['gaps'])} gap(s) recorded")
    parts.append("Evidence only; no druggability probability is given.")
    return ". ".join(parts)


@celery_app.task(name="bda_v2.druggability_assessment")
def druggability_assessment(run_id: str) -> dict:
    from ..research.evidence_tools import EvidenceToolService
    from ..targets.models import Target
    from . import druggability
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
        candidate_sequence = (run.query or {}).get("candidate_sequence")
        trial_term = str((run.query or {}).get("trial_term") or target_view.get("name") or "").strip()
        # Filing years from patents this project already saved through a
        # recorded search - read here, not searched for: an assessment must not
        # quietly start a patent search the person did not ask for.
        from ..literature.patent_service import project_landscape

        patent_years = project_landscape(session, run.project_id)["landscape"]["priority_years"] or None
        # What this project has saved and can cite. Read here for the same
        # reason the patent years are: an assessment reports the evidence that
        # exists, and must not start a search nobody asked for to create some.
        from ..literature.models import LiteratureDocument
        from ..literature.patent_service import PATENT_SOURCES

        by_source: dict[str, int] = {
            str(source): int(count)
            for source, count in session.execute(
                select(LiteratureDocument.source, func.count())
                .where(LiteratureDocument.project_id == run.project_id)
                .group_by(LiteratureDocument.source)
            ).all()
        }
        recent_saved = [
            {"document_id": str(row.id), "title": row.title, "source": row.source}
            for row in session.scalars(
                select(LiteratureDocument)
                .where(
                    LiteratureDocument.project_id == run.project_id,
                    LiteratureDocument.source.not_in(PATENT_SOURCES),
                )
                .order_by(LiteratureDocument.created_at.desc())
                .limit(5)
            )
        ]
        literature_counts = {
            "papers": sum(count for source, count in by_source.items() if source not in PATENT_SOURCES),
            "patents": sum(by_source.get(source, 0) for source in PATENT_SOURCES),
        }
        run.status = "running"
        run.version += 1

    from datetime import UTC, datetime

    # Bound source requests while allowing targets with more than 5,000 registrations.
    tools = EvidenceToolService(max_calls=druggability.MAX_SPONSOR_PAGES + 20, timeout_seconds=30.0)
    try:
        report = gather_druggability(
            tools,
            target_view,
            trial_term,
            patent_priority_years=patent_years,
            current_year=datetime.now(UTC).year,
            literature=druggability.literature_signal(literature_counts, recent=recent_saved),
        )
    except Exception as exc:  # noqa: BLE001 - the run must not be left running
        # Per-source failures are already gaps inside `gather_druggability`.
        # Reaching here means the gathering itself broke, and without this the
        # run would sit at "running" for ever: no report, no error, and nothing
        # to tell a reader whether to wait or to start again. The reason goes
        # into a report row because `IntelligenceRun` has no error column.
        with session_scope() as session:
            run = session.get(IntelligenceRun, parsed)
            if run is not None:
                session.add(
                    IntelligenceReport(
                        run_id=run.id,
                        title=f"Druggability assessment failed: {target_view.get('name') or target_view['id']}",
                        summary=f"The assessment could not be completed: {str(exc)[:500]}",
                        content={"error": str(exc)[:2000], "target": target_view, "trial_term": trial_term},
                    )
                )
                run.status = "failed"
                run.version += 1
        return {"run_id": run_id, "status": "failed", "error": str(exc)[:500]}
    finally:
        tools.close()

    if candidate_sequence is not None:
        report["candidate_sequence"] = candidate_sequence
        report.setdefault("retrieval", {})["candidate_sequence"] = {
            "source": "BDA sequence measurements at queue time",
            **candidate_sequence.get("source", {}),
        }
    retrieval = report.get("retrieval") or {}
    sections = {
        "candidate_sequence": retrieval.get("candidate_sequence"),
        "tractability": retrieval.get("open_targets"),
        "clinical_candidates": retrieval.get("open_targets"),
        "safety_liabilities": retrieval.get("open_targets"),
        "trial_activity": retrieval.get("clinical_trials"),
        "market_landscape": {
            "trend": retrieval.get("clinical_trials_trend"),
            "sponsors": retrieval.get("clinical_trials_sponsors"),
        },
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
