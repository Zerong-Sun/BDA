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
        "status": "failed" if error else (audit.get("status") or "completed"),
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

    from ..core.config import get_settings
    from ..literature.epo_ops import cql_query
    from ..literature.epo_ops import search_results as ops_search_results
    from ..literature.epo_ops import search_total as ops_search_total
    from ..literature.epo_ops_client import EpoOpsClient, load_credential
    from ..literature.indexing import extract_europe_pmc_full_text, index_document_content
    from ..literature.models import LiteratureDocument, LiteratureRetrievalTrace, LiteratureSearchRun
    from ..literature.patents import patent_query
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
        from ..research.search_query import search_topic

        # A patent run is the same pipeline over a patent index - Europe PMC's or
        # EPO OPS. The office
        # restriction is applied after translation, not stored in the query: a
        # Chinese topic is rewritten into English terms first, and a filter
        # embedded in the text could be dropped by that rewrite, recording a
        # search nobody asked for.
        sources = set(run.sources or [])
        ops_run = "epo_ops_patents" in sources
        patents_run = ops_run or "europe_pmc_patents" in sources
        database = "epo_ops_patents" if ops_run else ("europe_pmc_patents" if patents_run else "europe_pmc")
        document_source = "epo_ops_patent" if ops_run else ("europe_pmc_patent" if patents_run else "europe_pmc")
        # The index a trace names. An OPS record is not Europe PMC's because the
        # same pipeline saved it, and a trace that said so would send a reader to
        # the wrong database to check it.
        trace_source = "epo_ops" if ops_run else "europe_pmc"
        metadata_verification = "verified_epo_ops_metadata" if ops_run else "verified_europe_pmc_metadata"
        jurisdictions = [str(code) for code in (run.jurisdictions or [])]
        try:
            query = search_topic(session, run.project_id, run.query)
            if ops_run:
                query = cql_query(query, jurisdictions)
            elif patents_run:
                query = patent_query(query, jurisdictions)
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)[:1000]
            return {"search_run_id": search_run_id, "status": "failed", "error": str(exc)[:1000]}
        requested_limit = run.requested_limit
        fetch_full_text = run.fetch_full_text
        extract_claims = run.extract_claims
        created_by = run.created_by

    tools = EvidenceToolService(max_calls=1 + requested_limit * 2, timeout_seconds=20.0)
    ops_client: EpoOpsClient | None = None
    try:
        if ops_run:
            # Read at the moment of use and never stored: the run records that OPS
            # was searched, not how this server authenticated to it.
            ops_client = EpoOpsClient(load_credential(get_settings().epo_ops_credential_ref), max_calls=1)
            search_result = ops_client.search(query, limit=requested_limit)
            results = ops_search_results(search_result.data, limit=requested_limit)
        else:
            search_result = tools.search_europe_pmc(query, page_size=requested_limit)
            results = europe_pmc_results(search_result.data, limit=requested_limit)
    except RuntimeError as exc:
        audits = ops_client.audits if ops_client is not None else tools.audits
        audit = (
            audits[-1]
            if audits
            else {
                "tool": f"{trace_source}.search",
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
        if ops_client is not None:
            ops_client.close()
        return {"search_run_id": search_run_id, "status": "failed", "error": str(exc)}

    search_payload = json.dumps(search_result.data, ensure_ascii=False, sort_keys=True).encode()
    search_object_key = f"projects/{project_id}/literature/searches/{parsed}/{database.replace('_', '-')}.json"
    ObjectStorage().put_bytes(search_object_key, search_payload, "application/json")
    with session_scope() as session:
        raw_search_artifact = Artifact(
            project_id=project_id,
            created_by=created_by,
            artifact_type="literature_search_response",
            filename=f"{database.replace('_', '-')}-{parsed}.json",
            content_type="application/json",
            object_key=search_object_key,
            size_bytes=len(search_payload),
            checksum_sha256=hashlib.sha256(search_payload).hexdigest(),
            lineage={
                "search_run_id": search_run_id,
                "database": database,
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
                        "result_type": "biblio" if ops_run else "core",
                        # OPS states "no results found" in its own answer; recorded
                        # so an empty search reads as what the source said.
                        **({"no_results": True} if search_result.audit.get("no_results") else {}),
                        # OPS says how many records matched in all, not only how
                        # many were returned - the difference a reader must see.
                        **({"total_result_count": ops_search_total(search_result.data)} if ops_run else {}),
                        **({"jurisdictions": jurisdictions} if jurisdictions else {}),
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
                    LiteratureDocument.source == document_source,
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
            patent = result.get("patent")
            url = (
                patent["url"]
                if patent
                else (
                    f"https://europepmc.org/article/MED/{result['pmid']}"
                    if result["pmid"]
                    else (f"https://doi.org/{result['doi']}" if result["doi"] else None)
                )
            )
            if document is None:
                document = LiteratureDocument(
                    project_id=project_id,
                    title=result["title"],
                    source=document_source,
                    external_id=result["external_id"],
                    abstract=result["abstract"] or None,
                    status="retrieving",
                    metadata_json={
                        **result,
                        "url": url,
                        "ref_id": (
                            f"PATENT:{result['external_id']}"
                            if patent
                            else (
                                f"PMID:{result['pmid']}"
                                if result["pmid"]
                                else (
                                    f"DOI:{result['doi'].lower()}"
                                    if result["doi"]
                                    else f"EPMC:{result['external_id']}"
                                )
                            )
                        ),
                        "search_run_id": search_run_id,
                        "search_query": query,
                        "verification_status": metadata_verification,
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
                    source=trace_source,
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

        verification_status = metadata_verification
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
                            "database": database,
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
                    source=trace_source,
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
                    "database": database,
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
    if ops_client is not None:
        ops_client.close()
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


def _store_legal_status(document_id: uuid.UUID, record: dict) -> None:
    from ..literature.models import LiteratureDocument

    with session_scope() as session:
        document = session.get(LiteratureDocument, document_id)
        if document is None:
            return
        document.metadata_json = {**(document.metadata_json or {}), "patent_legal_status": record}
        document.version += 1


@celery_app.task(name="bda_v2.patent_legal_status")
def patent_legal_status(lookup_id: str, payload: dict) -> dict:
    """Look up saved patents' families and INPADOC events through EPO OPS.

    One family request per document, each one audited, its raw response kept
    as an artifact and its trace attached to the document it describes. What is
    saved on the document is a summary the landscape can read without another
    call - and the trace and artifact that let a reader check the summary.

    A document is looked up only if it is a saved patent of the project the
    operation belongs to; ids from anywhere else are skipped, not trusted.
    """
    from ..core.config import get_settings
    from ..literature.epo_ops import family_legal_summary, publication_reference
    from ..literature.epo_ops_client import EpoOpsClient, EpoOpsUnavailable, load_credential
    from ..literature.models import LiteratureDocument, LiteratureRetrievalTrace
    from ..literature.patent_service import MAX_LEGAL_STATUS_DOCUMENTS, PATENT_SOURCES
    from ..literature.patents import PatentQueryError

    project_id = uuid.UUID(str(payload["project_id"]))
    requested_by = uuid.UUID(str(payload["requested_by"]))
    requested = [uuid.UUID(str(item)) for item in (payload.get("document_ids") or [])][:MAX_LEGAL_STATUS_DOCUMENTS]
    targets: list[tuple[uuid.UUID, str, str | None]] = []
    with session_scope() as session:
        for document_id in requested:
            document = session.get(LiteratureDocument, document_id)
            if document is None or document.project_id != project_id or document.source not in PATENT_SOURCES:
                continue
            patent = (document.metadata_json or {}).get("patent") or {}
            targets.append((document.id, str(patent.get("publication_number") or ""), patent.get("kind_code")))

    # Raises before any call when the credential is missing or unreadable, so the
    # operation fails with that reason instead of recording every document as a gap.
    client = EpoOpsClient(
        load_credential(get_settings().epo_ops_credential_ref),
        # A kind code one index records differently can cost a second request.
        max_calls=2 * len(targets) + 1,
    )
    looked_up = gaps = 0
    refused: str | None = None
    try:
        for document_id, number, kind in targets:
            retrieved_at = datetime.now(UTC).isoformat()
            if refused is not None:
                gaps += 1
                _store_legal_status(document_id, {"status": "not_attempted", "error": refused, "retrieved_at": retrieved_at})
                continue
            try:
                reference = publication_reference(number, kind)
            except PatentQueryError as exc:
                gaps += 1
                _store_legal_status(document_id, {"status": "unresolvable", "error": str(exc), "retrieved_at": retrieved_at})
                continue
            try:
                try:
                    result = client.family_legal(reference)
                except RuntimeError as exc:
                    # The message may carry the fault OPS gave after the code.
                    if reference.kind is None or not str(exc).split(":")[0].endswith("_not_found"):
                        raise
                    # Europe PMC's kind code for a publication is not always
                    # DOCDB's (B for B2); the number alone still names it.
                    reference = type(reference)(reference.country, reference.number, None)
                    result = client.family_legal(reference)
            except RuntimeError as exc:
                gaps += 1
                if isinstance(exc, EpoOpsUnavailable) or "_refused" in str(exc):
                    # A refused credential or an exhausted quota refuses every
                    # remaining request too; spending them would only add noise.
                    refused = str(exc)
                audit = client.audits[-1] if client.audits else {"tool": "epo_ops.family_legal", "status": "failed"}
                with session_scope() as session:
                    trace = LiteratureRetrievalTrace(
                        project_id=project_id,
                        search_run_id=None,
                        document_id=document_id,
                        **_retrieval_trace_values(
                            audit,
                            stage="legal_status",
                            response_metadata={"publication": reference.docdb, "lookup_id": lookup_id},
                            error=str(exc),
                        ),
                    )
                    session.add(trace)
                    session.flush()
                    trace_id = str(trace.id)
                _store_legal_status(
                    document_id,
                    {
                        "status": "failed",
                        "error": str(exc)[:300],
                        "retrieval_trace_id": trace_id,
                        "retrieved_at": retrieved_at,
                    },
                )
                continue

            summary = family_legal_summary(result.data, reference)
            raw = json.dumps(result.data, ensure_ascii=False, sort_keys=True).encode()
            object_key = f"projects/{project_id}/literature/documents/{document_id}/epo-ops-family-legal/{hashlib.sha256(raw).hexdigest()}.json"
            ObjectStorage().put_bytes(object_key, raw, "application/json")
            with session_scope() as session:
                artifact = Artifact(
                    project_id=project_id,
                    created_by=requested_by,
                    artifact_type="patent_legal_status_response",
                    filename=f"epo-ops-{reference.docdb}-family-legal.json",
                    content_type="application/json",
                    object_key=object_key,
                    size_bytes=len(raw),
                    checksum_sha256=hashlib.sha256(raw).hexdigest(),
                    lineage={
                        "lookup_id": lookup_id,
                        "document_id": str(document_id),
                        "database": "epo_ops",
                        "publication": reference.docdb,
                    },
                )
                session.add(artifact)
                session.flush()
                trace = LiteratureRetrievalTrace(
                    project_id=project_id,
                    search_run_id=None,
                    document_id=document_id,
                    **_retrieval_trace_values(
                        result.audit,
                        stage="legal_status",
                        response_metadata={
                            "publication": reference.docdb,
                            "lookup_id": lookup_id,
                            "family_id": summary["family_id"],
                            "matched_publication": summary["matched_publication"],
                            "event_count": summary["event_count"],
                            "raw_response_artifact_id": str(artifact.id),
                        },
                    ),
                )
                session.add(trace)
                session.flush()
                trace_id, artifact_id = str(trace.id), str(artifact.id)
            matched = bool(summary["matched_publication"])
            looked_up += int(matched)
            gaps += int(not matched)
            _store_legal_status(
                document_id,
                {
                    **summary,
                    # A family that does not contain the publication asked about
                    # has no events that can be attributed to it.
                    "status": "completed" if matched else "not_matched",
                    "database": "EPO OPS (DOCDB family, INPADOC legal events)",
                    "publication": reference.docdb,
                    "retrieved_at": retrieved_at,
                    "retrieval_trace_id": trace_id,
                    "raw_response_artifact_id": artifact_id,
                    "lookup_id": lookup_id,
                },
            )
    finally:
        client.close()
    return {
        "lookup_id": lookup_id,
        "status": "completed_with_gaps" if gaps else "completed",
        "looked_up": looked_up,
        "gaps": gaps,
        "skipped": len(requested) - len(targets),
        "refused": refused,
    }


@celery_app.task(name="bda_v2.patent_claims")
def patent_claims(lookup_id: str, payload: dict) -> dict:
    from .patent_claims import collect_claims

    return collect_claims(lookup_id, payload)
