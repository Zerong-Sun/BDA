"""Literature ingestion, search and relation detection.

Moved out of ``compute.tasks``, which had grown to hold this domain's tasks alongside a
dozen others. Task names and queue routing are unchanged.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from ..artifacts.models import Artifact
from ..artifacts.storage import ObjectStorage
from ..core.celery_app import celery_app
from ..core.database import session_scope


@celery_app.task(name="bda_v2.literature_ingest")
def literature_ingest(document_id: str) -> dict:
    import re

    from ..literature.indexing import index_document_content
    from ..literature.models import LiteratureDocument

    with session_scope() as session:
        row = session.get(LiteratureDocument, uuid.UUID(document_id))
        if row and row.status == "pending":
            content = row.abstract or ""
            if row.artifact_id:
                artifact = session.get(Artifact, row.artifact_id)
                if artifact and artifact.project_id == row.project_id and artifact.status == "available":
                    if artifact.content_type in {"text/plain", "text/markdown", "application/json"}:
                        raw = ObjectStorage().read_bytes(artifact.object_key, max_bytes=10 * 1024 * 1024)
                        content = raw.decode("utf-8", errors="strict")
            paragraphs = [item.strip() for item in re.split(r"\n\s*\n", content) if item.strip()]
            if not paragraphs and row.title:
                paragraphs = [row.title]
            checksum = hashlib.sha256("\n\n".join(paragraphs).encode()).hexdigest()
            index_document_content(
                session,
                row,
                paragraphs,
                content_kind="uploaded_text" if row.artifact_id else "provided_abstract",
                content_checksum_sha256=checksum,
                retrieval_trace_id=None,
            )
            row.metadata_json = {
                **(row.metadata_json or {}),
                "content_provenance": {
                    "content_kind": "uploaded_text" if row.artifact_id else "provided_abstract",
                    "content_checksum_sha256": checksum,
                    "analysis_status": "pending_human_review",
                },
            }
            row.status = "available"
            row.version += 1
    return {"document_id": document_id, "status": "available"}


def _retrieval_trace_values(
    audit: dict,
    *,
    stage: str,
    response_metadata: dict | None = None,
    content_checksum_sha256: str | None = None,
    error: str | None = None,
) -> dict:
    return {
        "stage": stage,
        "source": str(audit.get("tool") or "").split(".", 1)[0] or "unknown",
        "request_json": audit.get("query") or {},
        "response_metadata": response_metadata or {},
        "status": audit.get("status") or ("failed" if error else "completed"),
        "http_status": audit.get("http_status"),
        "response_checksum_sha256": audit.get("response_checksum_sha256"),
        "content_checksum_sha256": content_checksum_sha256,
        "content_type": audit.get("content_type"),
        "byte_count": audit.get("byte_count"),
        "error": error or audit.get("error"),
    }


def _same_literature_identity(document, result: dict) -> bool:
    metadata = document.metadata_json or {}
    pairs = (
        ("pmid", str(result.get("pmid") or "").strip()),
        ("pmcid", str(result.get("pmcid") or "").strip().upper()),
        ("doi", str(result.get("doi") or "").strip().lower()),
    )
    for key, expected in pairs:
        actual = str(metadata.get(key) or "").strip()
        if key == "pmcid":
            actual = actual.upper().replace("PMC_", "PMC")
        elif key == "doi":
            actual = actual.lower()
        if expected and actual == expected:
            return True
    return False


@celery_app.task(name="bda_v2.literature_search")
def literature_search(search_run_id: str) -> dict:
    import xml.etree.ElementTree as ET

    from ..literature.indexing import extract_europe_pmc_full_text, index_document_content
    from ..literature.models import LiteratureDocument, LiteratureRetrievalTrace, LiteratureSearchRun
    from ..literature.retrieval import europe_pmc_results, text_checksum
    from ..research.evidence_tools import EvidenceToolService, titles_match

    parsed = uuid.UUID(search_run_id)
    with session_scope() as session:
        run = session.get(LiteratureSearchRun, parsed)
        if run is None:
            return {"search_run_id": search_run_id, "status": "missing"}
        if run.status in {"completed", "completed_with_gaps"}:
            return {
                "search_run_id": search_run_id,
                "status": run.status,
                "result_count": run.result_count,
            }
        run.status = "running"
        run.version += 1
        project_id = run.project_id
        query = run.query
        requested_limit = run.requested_limit
        fetch_full_text = run.fetch_full_text
        extract_claims = run.extract_claims
        created_by = run.created_by

    tools = EvidenceToolService(max_calls=1 + requested_limit * 2, timeout_seconds=20.0)
    try:
        search_result = tools.search_europe_pmc(query, page_size=requested_limit)
        results = europe_pmc_results(search_result.data, limit=requested_limit)
    except RuntimeError as exc:
        audit = (
            tools.audits[-1]
            if tools.audits
            else {
                "tool": "europe_pmc.search",
                "query": {"query": query},
                "status": "failed",
                "error": str(exc),
            }
        )
        with session_scope() as session:
            run = session.get(LiteratureSearchRun, parsed)
            if run is not None:
                session.add(
                    LiteratureRetrievalTrace(
                        project_id=project_id,
                        search_run_id=parsed,
                        document_id=None,
                        **_retrieval_trace_values(audit, stage="search", error=str(exc)),
                    )
                )
                run.status = "failed"
                run.error = str(exc)[:2000]
                run.completed_at = datetime.now(UTC)
                run.version += 1
        tools.close()
        return {"search_run_id": search_run_id, "status": "failed", "error": str(exc)}

    search_payload = json.dumps(search_result.data, ensure_ascii=False, sort_keys=True).encode()
    search_object_key = f"projects/{project_id}/literature/searches/{parsed}/europe-pmc.json"
    ObjectStorage().put_bytes(search_object_key, search_payload, "application/json")
    with session_scope() as session:
        raw_search_artifact = Artifact(
            project_id=project_id,
            created_by=created_by,
            artifact_type="literature_search_response",
            filename=f"europe-pmc-{parsed}.json",
            content_type="application/json",
            object_key=search_object_key,
            size_bytes=len(search_payload),
            checksum_sha256=hashlib.sha256(search_payload).hexdigest(),
            lineage={
                "search_run_id": search_run_id,
                "database": "europe_pmc",
                "query": query,
            },
        )
        session.add(raw_search_artifact)
        session.flush()
        session.add(
            LiteratureRetrievalTrace(
                project_id=project_id,
                search_run_id=parsed,
                document_id=None,
                **_retrieval_trace_values(
                    search_result.audit,
                    stage="search",
                    response_metadata={
                        "result_count": len(results),
                        "raw_response_artifact_id": str(raw_search_artifact.id),
                        "result_type": "core",
                    },
                ),
            )
        )

    created_documents = 0
    gaps = 0
    for result in results:
        with session_scope() as session:
            document = session.scalar(
                select(LiteratureDocument).where(
                    LiteratureDocument.project_id == project_id,
                    LiteratureDocument.source == "europe_pmc",
                    LiteratureDocument.external_id == result["external_id"],
                )
            )
            if document is None:
                document = next(
                    (
                        item
                        for item in session.scalars(
                            select(LiteratureDocument).where(LiteratureDocument.project_id == project_id)
                        )
                        if _same_literature_identity(item, result)
                    ),
                    None,
                )
            url = (
                f"https://europepmc.org/article/MED/{result['pmid']}"
                if result["pmid"]
                else (f"https://doi.org/{result['doi']}" if result["doi"] else None)
            )
            if document is None:
                document = LiteratureDocument(
                    project_id=project_id,
                    title=result["title"],
                    source="europe_pmc",
                    external_id=result["external_id"],
                    abstract=result["abstract"] or None,
                    status="retrieving",
                    metadata_json={
                        **result,
                        "url": url,
                        "ref_id": (
                            f"PMID:{result['pmid']}"
                            if result["pmid"]
                            else (f"DOI:{result['doi'].lower()}" if result["doi"] else f"EPMC:{result['external_id']}")
                        ),
                        "search_run_id": search_run_id,
                        "search_query": query,
                        "verification_status": "verified_europe_pmc_metadata",
                        "review_status": "pending_review",
                    },
                )
                session.add(document)
                session.flush()
                created_documents += 1
            else:
                metadata = dict(document.metadata_json or {})
                document.abstract = document.abstract or result["abstract"] or None
                document.metadata_json = {
                    **result,
                    **metadata,
                    "url": metadata.get("url") or url,
                    "search_run_id": search_run_id,
                    "search_query": query,
                }
                if document.status not in {"available"}:
                    document.status = "retrieving"
                document.version += 1
            document_id = document.id
            session.add(
                LiteratureRetrievalTrace(
                    project_id=project_id,
                    search_run_id=parsed,
                    document_id=document.id,
                    stage="search_hit",
                    source="europe_pmc",
                    request_json={"query": query, "rank": result["rank"]},
                    response_metadata={
                        key: result[key]
                        for key in (
                            "external_id",
                            "doi",
                            "pmid",
                            "pmcid",
                            "is_open_access",
                            "in_epmc",
                        )
                    },
                    status="completed",
                    http_status=search_result.audit.get("http_status"),
                    response_checksum_sha256=search_result.audit.get("response_checksum_sha256"),
                    content_type=search_result.audit.get("content_type"),
                    byte_count=search_result.audit.get("byte_count"),
                )
            )

        verification_status = "verified_europe_pmc_metadata"
        if result["doi"]:
            try:
                crossref = tools.get_crossref(result["doi"])
                crossref_message = crossref.data.get("message") or {}
                matched = isinstance(crossref_message, dict) and titles_match(
                    result["title"], crossref_message.get("title")
                )
                verification_status = "verified_crossref" if matched else "metadata_mismatch"
                with session_scope() as session:
                    session.add(
                        LiteratureRetrievalTrace(
                            project_id=project_id,
                            search_run_id=parsed,
                            document_id=document_id,
                            **_retrieval_trace_values(
                                crossref.audit,
                                stage="metadata_verification",
                                response_metadata={"title_match": matched, "doi": result["doi"]},
                            ),
                        )
                    )
            except (RuntimeError, ValueError) as exc:
                gaps += 1
                audit = tools.audits[-1]
                with session_scope() as session:
                    session.add(
                        LiteratureRetrievalTrace(
                            project_id=project_id,
                            search_run_id=parsed,
                            document_id=document_id,
                            **_retrieval_trace_values(
                                audit,
                                stage="metadata_verification",
                                error=str(exc),
                            ),
                        )
                    )

        paragraphs: list[str] = []
        content_kind = "metadata_only"
        content_checksum = ""
        retrieval_trace_id: str | None = None
        raw_artifact_id: uuid.UUID | None = None
        license_text = ""
        if fetch_full_text and result["pmcid"] and result["is_open_access"]:
            try:
                full_text = tools.get_europe_pmc_full_text(result["pmcid"])
                paragraphs, xml_metadata = extract_europe_pmc_full_text(full_text.content)
                content_checksum = str(xml_metadata["content_checksum_sha256"])
                license_text = str(xml_metadata.get("license_text") or "")
                object_key = f"projects/{project_id}/literature/documents/{document_id}/{result['pmcid']}.xml"
                ObjectStorage().put_bytes(object_key, full_text.content, "application/xml")
                with session_scope() as session:
                    artifact = Artifact(
                        project_id=project_id,
                        created_by=created_by,
                        artifact_type="literature_full_text_xml",
                        filename=f"{result['pmcid']}.xml",
                        content_type="application/xml",
                        object_key=object_key,
                        size_bytes=len(full_text.content),
                        checksum_sha256=content_checksum,
                        lineage={
                            "search_run_id": search_run_id,
                            "document_id": str(document_id),
                            "database": "europe_pmc",
                            "pmcid": result["pmcid"],
                            "license_text": license_text,
                        },
                    )
                    session.add(artifact)
                    session.flush()
                    raw_artifact_id = artifact.id
                    trace = LiteratureRetrievalTrace(
                        project_id=project_id,
                        search_run_id=parsed,
                        document_id=document_id,
                        **_retrieval_trace_values(
                            full_text.audit,
                            stage="full_text",
                            response_metadata={
                                "pmcid": result["pmcid"],
                                "raw_content_artifact_id": str(artifact.id),
                                "license_text": license_text,
                            },
                            content_checksum_sha256=content_checksum,
                        ),
                    )
                    session.add(trace)
                    session.flush()
                    retrieval_trace_id = str(trace.id)
                content_kind = "open_access_full_text"
            except (RuntimeError, ValueError, ET.ParseError) as exc:
                gaps += 1
                audit = tools.audits[-1]
                with session_scope() as session:
                    trace = LiteratureRetrievalTrace(
                        project_id=project_id,
                        search_run_id=parsed,
                        document_id=document_id,
                        **_retrieval_trace_values(
                            audit,
                            stage="full_text",
                            response_metadata={"pmcid": result["pmcid"]},
                            error=str(exc),
                        ),
                    )
                    session.add(trace)

        if not paragraphs and result["abstract"]:
            paragraphs = [result["abstract"]]
            content_kind = "database_abstract"
            content_checksum = text_checksum(paragraphs)
            with session_scope() as session:
                trace = LiteratureRetrievalTrace(
                    project_id=project_id,
                    search_run_id=parsed,
                    document_id=document_id,
                    stage="abstract",
                    source="europe_pmc",
                    request_json=search_result.audit.get("query") or {},
                    response_metadata={
                        "rank": result["rank"],
                        "abstract_from_core_search": True,
                    },
                    status="completed",
                    http_status=search_result.audit.get("http_status"),
                    response_checksum_sha256=search_result.audit.get("response_checksum_sha256"),
                    content_checksum_sha256=content_checksum,
                    content_type="text/plain",
                    byte_count=len(result["abstract"].encode()),
                )
                session.add(trace)
                session.flush()
                retrieval_trace_id = str(trace.id)

        with session_scope() as session:
            document = session.get(LiteratureDocument, document_id)
            if document is None:
                continue
            document.metadata_json = {
                **(document.metadata_json or {}),
                "verification_status": verification_status,
                "content_provenance": {
                    "content_kind": content_kind,
                    "content_checksum_sha256": content_checksum or None,
                    "retrieval_trace_id": retrieval_trace_id,
                    "raw_content_artifact_id": str(raw_artifact_id) if raw_artifact_id else None,
                    "retrieved_at": datetime.now(UTC).isoformat(),
                    "database": "europe_pmc",
                    "query": query,
                    "rank": result["rank"],
                    "license_text": license_text,
                    "analysis_status": "pending_human_review",
                },
            }
            if raw_artifact_id:
                document.artifact_id = raw_artifact_id
            if paragraphs:
                index_document_content(
                    session,
                    document,
                    paragraphs,
                    content_kind=content_kind,
                    content_checksum_sha256=content_checksum,
                    retrieval_trace_id=retrieval_trace_id,
                    extract_claims=extract_claims,
                )
                document.status = "available"
            else:
                document.status = "metadata_only"
                gaps += 1
            document.version += 1

    with session_scope() as session:
        run = session.get(LiteratureSearchRun, parsed)
        if run is not None:
            run.result_count = len(results)
            run.status = "completed_with_gaps" if gaps else "completed"
            run.completed_at = datetime.now(UTC)
            run.error = None
            run.version += 1
    tools.close()
    return {
        "search_run_id": search_run_id,
        "status": "completed_with_gaps" if gaps else "completed",
        "result_count": len(results),
        "created_documents": created_documents,
        "gaps": gaps,
    }


@celery_app.task(name="bda_v2.subscription_run")
def subscription_run(subscription_id: str) -> dict:
    from ..literature.models import LiteratureSearchRun, LiteratureSubscription

    parsed = uuid.UUID(subscription_id)
    with session_scope() as session:
        subscription = session.get(LiteratureSubscription, parsed)
        if subscription is None:
            return {"subscription_id": subscription_id, "status": "missing"}
        run = LiteratureSearchRun(
            project_id=subscription.project_id,
            query=subscription.query,
            sources=["europe_pmc"],
            requested_limit=10,
            fetch_full_text=True,
            extract_claims=True,
            created_by=subscription.created_by,
        )
        session.add(run)
        session.flush()
        run_id = str(run.id)
    result = literature_search.run(run_id)
    return {"subscription_id": subscription_id, **result}


@celery_app.task(name="bda_v2.literature_relations_detect")
def literature_relations_detect(project_id: str) -> dict:
    from ..literature.models import LiteratureClaim, LiteratureDocument, LiteratureRelation

    parsed = uuid.UUID(project_id)
    with session_scope() as session:
        claims = list(
            session.scalars(
                select(LiteratureClaim)
                .join(LiteratureDocument, LiteratureDocument.id == LiteratureClaim.document_id)
                .where(LiteratureDocument.project_id == parsed)
                .order_by(LiteratureClaim.id)
                .limit(500)
            )
        )
        existing = set(
            session.execute(
                select(LiteratureRelation.source_claim_id, LiteratureRelation.target_claim_id).where(
                    LiteratureRelation.project_id == parsed
                )
            ).tuples()
        )
        created = 0
        for left, right in zip(claims, claims[1:], strict=False):
            if (left.id, right.id) in existing:
                continue
            left_terms = {item.lower() for item in left.claim.split() if len(item) > 4}
            right_terms = {item.lower() for item in right.claim.split() if len(item) > 4}
            overlap = sorted(left_terms & right_terms)
            if overlap:
                session.add(
                    LiteratureRelation(
                        project_id=parsed,
                        source_claim_id=left.id,
                        target_claim_id=right.id,
                        relation_type="related",
                        rationale=f"Shared terms: {', '.join(overlap[:8])}",
                    )
                )
                created += 1
    return {"project_id": project_id, "status": "completed", "created": created}
