"""Saved patent documents -> a landscape whose every count can be traced.

`patents.landscape` counts; this decides what it counts. Only patent documents
this project has actually saved - each one a hit from a recorded search, with a
retrieval trace - and never a search run on demand here, because a landscape
computed from an unsaved search would be the untraceable answer the policy
exists to refuse.

Two indexes can save a patent: Europe PMC's and EPO OPS. The same publication
found by both is one publication, so records are keyed by office, number and
kind, and counted once. Families come from the DOCDB family id OPS carries;
legal events only from a recorded OPS lookup of that document. Neither is
inferred for a record that has not got one.

Every record returned names its document and its retrieval trace, so a figure
in the landscape can be walked back to the exact search response it came from.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.problem import DomainError
from ..identity.models import User
from ..platform.operations import enqueue_operation
from ..projects.models import Project
from .epo_ops import LEGAL_LIMITS
from .epo_ops_client import credential_available
from .models import LiteratureDocument
from .patents import JURISDICTIONS, landscape

#: The document source a Europe PMC patent run saves under (see `literature_search`).
PATENT_SOURCE = "europe_pmc_patent"
#: The document source an EPO OPS patent run saves under.
OPS_PATENT_SOURCE = "epo_ops_patent"
#: Every source a saved patent document can carry.
PATENT_SOURCES: tuple[str, ...] = (PATENT_SOURCE, OPS_PATENT_SOURCE)

DATABASES = {
    PATENT_SOURCE: "Europe PMC patent index (SRC:PAT)",
    OPS_PATENT_SOURCE: "EPO Open Patent Services (DOCDB)",
}

#: A landscape is read by a person and by a model whose result is written into
#: a transcript. The counts cover every matching record; the list does not.
MAX_RECORDS_LISTED = 50
MAX_DOCUMENTS_READ = 2000
MAX_COUNTRIES_LISTED = 12
#: One OPS family request per document, and INPADOC allows about 45 a minute.
MAX_LEGAL_STATUS_DOCUMENTS = 25
LEGAL_STATUS_TOPIC = "literature.patent_legal_status"
CLAIMS_TOPIC = "literature.patent_claims"


def publication_key(patent: dict[str, Any]) -> str:
    """Office, number and kind: one publication, whichever index saved it."""
    number = "".join(str(patent.get("publication_number") or "").split()).upper()
    kind = str(patent.get("kind_code") or "").strip().upper()
    if kind and number.endswith(kind) and len(number) > len(kind) + 2 and number[-len(kind) - 1].isdigit():
        number = number[: -len(kind)]
    return f"{number}{kind}"


def family_id(metadata: dict[str, Any]) -> str | None:
    """The DOCDB family id a record carries from its search or from a lookup."""
    patent = metadata.get("patent") or {}
    looked_up = metadata.get("patent_legal_status") or {}
    value = patent.get("family_id") or looked_up.get("family_id")
    return str(value) if value else None


def _detail(metadata: dict[str, Any]) -> int:
    """How much a saved copy knows beyond its search record, to pick one of two copies."""
    looked_up = metadata.get("patent_legal_status") or {}
    return (2 if looked_up.get("status") == "completed" else 0) + (1 if family_id(metadata) else 0)


def _legal_view(metadata: dict[str, Any]) -> dict[str, Any] | None:
    looked_up = metadata.get("patent_legal_status")
    if not looked_up:
        return None
    if looked_up.get("status") != "completed":
        return {
            "status": looked_up.get("status"),
            "error": looked_up.get("error"),
            "retrieval_trace_id": looked_up.get("retrieval_trace_id"),
        }
    return {
        "status": "completed",
        "retrieved_at": looked_up.get("retrieved_at"),
        "application": looked_up.get("application"),
        "matched_publication": looked_up.get("matched_publication"),
        "event_count": looked_up.get("event_count"),
        # The most recent event per country, never a verdict per patent: an EP
        # patent lapses in one designated state and is maintained in another.
        "countries": [
            {
                "country": row.get("country"),
                "events": row.get("events"),
                # Both: a country whose every event is neutral - a publication,
                # a request for examination - has no flagged event, and showing
                # only that would report a count with nothing in it.
                "latest_event": row.get("latest_event"),
                "latest_flagged_event": row.get("latest_flagged_event"),
            }
            for row in (looked_up.get("by_country") or [])[:MAX_COUNTRIES_LISTED]
        ],
        "family_publications": looked_up.get("family_publications"),
        "retrieval_trace_id": looked_up.get("retrieval_trace_id"),
    }


def project_landscape(
    session: Session,
    project_id: uuid.UUID,
    *,
    search_run_id: uuid.UUID | None = None,
    jurisdictions: tuple[str, ...] = (),
) -> dict[str, Any]:
    codes = {str(code).strip().upper() for code in jurisdictions if str(code).strip()}
    unknown = sorted(codes - set(JURISDICTIONS))
    if unknown:
        raise DomainError(
            "patent_jurisdiction_unknown",
            f"Unknown jurisdiction(s) {unknown}. Known: {sorted(JURISDICTIONS)}.",
            status_code=422,
        )

    documents = list(session.scalars(
        select(LiteratureDocument)
        .where(
            LiteratureDocument.project_id == project_id,
            LiteratureDocument.source.in_(PATENT_SOURCES),
        )
        .order_by(LiteratureDocument.created_at.desc())
        .limit(MAX_DOCUMENTS_READ + 1)
    ))
    truncated = len(documents) > MAX_DOCUMENTS_READ

    by_key: dict[str, tuple[LiteratureDocument, dict[str, Any], dict[str, Any]]] = {}
    merged = 0
    for document in documents[:MAX_DOCUMENTS_READ]:
        metadata = document.metadata_json or {}
        patent = metadata.get("patent") or {}
        if not patent:
            continue
        if search_run_id is not None and metadata.get("search_run_id") != str(search_run_id):
            continue
        if codes and str(patent.get("country_code") or "").upper() not in codes:
            continue
        key = publication_key(patent) or str(document.id)
        held = by_key.get(key)
        if held is not None:
            merged += 1
            if _detail(metadata) <= _detail(held[2]):
                continue
        by_key[key] = (document, patent, metadata)
    selected = list(by_key.values())
    grouped: dict[str, list[tuple[LiteratureDocument, dict[str, Any], dict[str, Any]]]] = {}
    for item in selected:
        if family := family_id(item[2]):
            grouped.setdefault(family, []).append(item)
    groups = [
        {
            "family_id": family,
            "publications": len(members),
            "jurisdictions": sorted({str(p.get("country_code")) for _, p, _ in members if p.get("country_code")}),
            "applicants": sorted({str(p.get("applicant")) for _, p, _ in members if p.get("applicant")}),
            "members": [
                {
                    "document_id": str(d.id), "publication_number": p.get("publication_number"),
                    "kind_code": p.get("kind_code"), "title": d.title,
                    "retrieval_trace_id": (m.get("content_provenance") or {}).get("retrieval_trace_id"),
                }
                for d, p, m in members[:10]
            ],
            "members_truncated": len(members) > 10,
        }
        for family, members in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))[:MAX_RECORDS_LISTED]
    ]

    today = datetime.now(UTC).date()
    summary = landscape([patent for _, patent, _ in selected], today=today)
    families = {family for _, _, metadata in selected if (family := family_id(metadata))}
    lookups = [metadata.get("patent_legal_status") or {} for _, _, metadata in selected]
    looked_up = sum(1 for row in lookups if row.get("status") == "completed")
    lookup_gaps = sum(1 for row in lookups if row and row.get("status") != "completed")

    records = [
        {
            "document_id": str(document.id),
            "database": DATABASES.get(document.source, document.source),
            "publication_number": patent.get("publication_number"),
            "title": document.title,
            "country_code": patent.get("country_code"),
            "kind_code": patent.get("kind_code"),
            "stage": patent.get("stage"),
            "applicant": patent.get("applicant"),
            "application_date": patent.get("application_date"),
            "earliest_priority_date": patent.get("earliest_priority_date"),
            "ipc": patent.get("ipc") or [],
            "family_id": family_id(metadata),
            "legal_events": _legal_view(metadata),
            "url": patent.get("url"),
            # The link from a number in the landscape back to the response that
            # produced it. A record without one was not retrieved by this pipeline.
            "retrieval_trace_id": (metadata.get("content_provenance") or {}).get("retrieval_trace_id"),
            "search_run_id": metadata.get("search_run_id"),
        }
        for document, patent, metadata in selected[:MAX_RECORDS_LISTED]
    ]
    searches = sorted(
        {str(metadata.get("search_query")) for _, _, metadata in selected if metadata.get("search_query")}
    )
    return {
        "landscape": summary,
        "families": {
            "distinct": len(families),
            "groups": groups,
            "groups_truncated": len(families) > len(groups),
            "publications_without_family_id": sum(1 for _, _, metadata in selected if not family_id(metadata)),
            "basis": (
                "DOCDB simple family ids, carried by EPO OPS records and by Europe PMC records "
                "after a legal-status lookup. A publication without one is not counted as its "
                "own family, because it may belong to a family already counted."
            ),
        },
        "legal_events": {
            "looked_up": looked_up,
            "lookup_gaps": lookup_gaps,
            "not_looked_up": len(selected) - looked_up - lookup_gaps,
            "basis": "INPADOC events from a recorded EPO OPS lookup, per record, most recent per country.",
            "limits": list(LEGAL_LIMITS),
        },
        "records": records,
        "records_listed": len(records),
        "records_matched": len(selected),
        "documents_read": min(len(documents), MAX_DOCUMENTS_READ),
        "documents_truncated": truncated,
        "complete": not truncated,
        "duplicate_copies_merged": merged,
        "searches": searches,
        "filters": {
            "search_run_id": str(search_run_id) if search_run_id else None,
            "jurisdictions": sorted(codes),
        },
        "databases": sorted({DATABASES.get(document.source, document.source) for document, _, _ in selected}),
        "as_of": today.isoformat(),
    }


def _create_lookup(
    session: Session,
    project: Project,
    document_ids: list[uuid.UUID],
    user: User,
    *,
    topic: str,
) -> dict[str, Any]:
    """Queue an EPO lookup for saved patents of this project.

    Every refusal happens here, before anything is queued: a document of another
    project, a paper passed as a patent, too many at once, or no credential. A
    lookup that could only fail in the worker would leave a pending operation to
    explain what one sentence here says.
    """
    requested = list(dict.fromkeys(document_ids))
    if not requested:
        raise DomainError("patent_documents_required", "Name at least one saved patent document.", status_code=422)
    if len(requested) > MAX_LEGAL_STATUS_DOCUMENTS:
        raise DomainError(
            "patent_documents_too_many",
            f"At most {MAX_LEGAL_STATUS_DOCUMENTS} patents per lookup; split the request.",
            status_code=422,
        )
    if not credential_available(get_settings().epo_ops_credential_ref):
        raise DomainError(
            "epo_ops_not_configured",
            "Patent evidence comes from EPO Open Patent Services, which is not "
            "configured on this server. Set BDA_V2_EPO_OPS_CREDENTIAL_REF.",
            status_code=503,
        )
    rows = {
        row.id: row
        for row in session.scalars(
            select(LiteratureDocument).where(
                LiteratureDocument.id.in_(requested),
                LiteratureDocument.project_id == project.id,
            )
        )
    }
    missing = [str(item) for item in requested if item not in rows]
    if missing:
        raise DomainError(
            "patent_document_not_found",
            f"No saved document of this project has id(s) {missing}.",
            status_code=404,
        )
    not_patents = [str(item) for item in requested if rows[item].source not in PATENT_SOURCES]
    if not_patents:
        raise DomainError(
            "patent_document_not_a_patent",
            f"Document(s) {not_patents} are not saved patents; only patents have legal events.",
            status_code=422,
        )
    lookup_id = uuid.uuid4()
    operation = enqueue_operation(
        session,
        topic=topic,
        resource_type="patent_claims_lookup" if topic == CLAIMS_TOPIC else "patent_legal_status_lookup",
        resource_id=lookup_id,
        user=user,
        project_id=project.id,
        organization_id=project.organization_id,
        payload={"document_ids": [str(item) for item in requested], "requested_by": str(user.id)},
    )
    return {
        "lookup_id": str(lookup_id),
        "operation_id": str(operation.id),
        "status": "pending",
        "documents": len(requested),
        "database": "epo_ops_claims" if topic == CLAIMS_TOPIC else "epo_ops_inpadoc",
    }


def create_legal_status_lookup(session: Session, project: Project, document_ids: list[uuid.UUID], user: User) -> dict[str, Any]:
    return _create_lookup(session, project, document_ids, user, topic=LEGAL_STATUS_TOPIC)


def create_claims_lookup(session: Session, project: Project, document_ids: list[uuid.UUID], user: User) -> dict[str, Any]:
    return _create_lookup(session, project, document_ids, user, topic=CLAIMS_TOPIC)
