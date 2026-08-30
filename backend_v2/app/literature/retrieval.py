from __future__ import annotations

import hashlib
from typing import Any


def europe_pmc_results(payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    rows = (payload.get("resultList") or {}).get("result") or []
    results: list[dict[str, Any]] = []
    for rank, row in enumerate(rows[:limit], start=1):
        if not isinstance(row, dict):
            continue
        external_id = str(row.get("id") or row.get("pmid") or row.get("doi") or "").strip()
        title = str(row.get("title") or "").strip()
        if not external_id or not title:
            continue
        pmcid = str(row.get("pmcid") or "").strip().upper().replace("PMC_", "PMC")
        abstract = str(row.get("abstractText") or "").strip()
        results.append(
            {
                "rank": rank,
                "source": str(row.get("source") or "europe_pmc").lower(),
                "external_id": external_id,
                "title": title,
                "abstract": abstract,
                "doi": str(row.get("doi") or "").strip(),
                "pmid": str(row.get("pmid") or "").strip(),
                "pmcid": pmcid,
                "authors": str(row.get("authorString") or "").strip(),
                "journal": str(row.get("journalTitle") or "").strip(),
                "year": str(row.get("pubYear") or "").strip(),
                "is_open_access": str(row.get("isOpenAccess") or "").upper() == "Y",
                "in_epmc": str(row.get("inEPMC") or "").upper() == "Y",
                "cited_by_count": row.get("citedByCount"),
                "publication_types": row.get("pubTypeList") or {},
            }
        )
    return results


def text_checksum(paragraphs: list[str]) -> str:
    return hashlib.sha256("\n\n".join(paragraphs).encode("utf-8")).hexdigest()
