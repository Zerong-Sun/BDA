"""Saved patent documents -> a landscape whose every count can be traced.

`patents.landscape` counts; this decides what it counts. Only patent documents
this project has actually saved - each one a hit from a recorded search, with a
retrieval trace - and never a search run on demand here, because a landscape
computed from an unsaved search would be the untraceable answer the policy
exists to refuse.

Every record returned names its document and its retrieval trace, so a figure
in the landscape can be walked back to the exact search response it came from.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.problem import DomainError
from .models import LiteratureDocument
from .patents import JURISDICTIONS, landscape

#: The document source a patent run saves under (see `literature_search`).
PATENT_SOURCE = "europe_pmc_patent"

#: A landscape is read by a person and by a model whose result is written into
#: a transcript. The counts cover every matching record; the list does not.
MAX_RECORDS_LISTED = 50
MAX_DOCUMENTS_READ = 2000


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

    documents = session.scalars(
        select(LiteratureDocument)
        .where(
            LiteratureDocument.project_id == project_id,
            LiteratureDocument.source == PATENT_SOURCE,
        )
        .order_by(LiteratureDocument.created_at.desc())
        .limit(MAX_DOCUMENTS_READ)
    )

    selected: list[tuple[LiteratureDocument, dict[str, Any], dict[str, Any]]] = []
    for document in documents:
        metadata = document.metadata_json or {}
        patent = metadata.get("patent") or {}
        if not patent:
            continue
        if search_run_id is not None and metadata.get("search_run_id") != str(search_run_id):
            continue
        if codes and str(patent.get("country_code") or "").upper() not in codes:
            continue
        selected.append((document, patent, metadata))

    today = datetime.now(UTC).date()
    summary = landscape([patent for _, patent, _ in selected], today=today)
    records = [
        {
            "document_id": str(document.id),
            "publication_number": patent.get("publication_number"),
            "title": document.title,
            "country_code": patent.get("country_code"),
            "kind_code": patent.get("kind_code"),
            "stage": patent.get("stage"),
            "applicant": patent.get("applicant"),
            "application_date": patent.get("application_date"),
            "earliest_priority_date": patent.get("earliest_priority_date"),
            "ipc": patent.get("ipc") or [],
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
        "records": records,
        "records_listed": len(records),
        "records_matched": len(selected),
        "searches": searches,
        "filters": {
            "search_run_id": str(search_run_id) if search_run_id else None,
            "jurisdictions": sorted(codes),
        },
        "database": "Europe PMC patent index (SRC:PAT)",
        "as_of": today.isoformat(),
    }
