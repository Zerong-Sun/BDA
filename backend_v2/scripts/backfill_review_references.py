from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from backend_v2.app.core.database import session_scope
from backend_v2.app.literature.retrieval import europe_pmc_results
from backend_v2.app.projects.models import Project
from backend_v2.app.research.models import ResearchFinding
from backend_v2.app.research.workspace import _reference_source, _strings
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified


class CitationMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        values = {key.lower(): value or "" for key, value in attrs}
        name = (values.get("name") or values.get("property") or "").lower()
        content = values.get("content", "").strip()
        if name.startswith("citation_") and content:
            self.values.setdefault(name, []).append(content)


def _first(values: dict[str, list[str]], key: str) -> str:
    return (values.get(key) or [""])[0]


def _article_page_metadata(client: httpx.Client, url: str) -> dict[str, str]:
    response = client.get(url, follow_redirects=True)
    response.raise_for_status()
    parser = CitationMetaParser()
    parser.feed(response.text[:2_000_000])
    values = parser.values
    title = _first(values, "citation_title")
    if not title:
        return {}
    date = _first(values, "citation_publication_date") or _first(values, "citation_date")
    doi = _first(values, "citation_doi")
    return {
        "title": title,
        "authors": "; ".join(values.get("citation_author") or []),
        "journal": _first(values, "citation_journal_title"),
        "year": date[:4] if date[:4].isdigit() else "",
        "doi": doi,
        "url": f"https://doi.org/{doi}" if doi else str(response.url),
    }


def _pubmed_metadata(client: httpx.Client, pmid: str) -> dict[str, str]:
    response = client.get(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        params={
            "query": f"EXT_ID:{pmid} AND SRC:MED",
            "format": "json",
            "resultType": "core",
            "pageSize": 1,
        },
    )
    response.raise_for_status()
    rows = europe_pmc_results(response.json(), limit=1)
    if not rows:
        return {}
    row = rows[0]
    return {
        "title": row["title"],
        "authors": row["authors"],
        "journal": row["journal"],
        "year": row["year"],
        "doi": row["doi"],
        "pmid": row["pmid"] or pmid,
        "pmcid": row["pmcid"],
        "abstract": row["abstract"],
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def _pdb_metadata(client: httpx.Client, pdb_id: str) -> dict[str, str]:
    response = client.get(f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}")
    response.raise_for_status()
    payload = response.json()
    citations = payload.get("citation") or []
    citation = next(
        (item for item in citations if isinstance(item, dict) and item.get("rcsb_is_primary") == "Y"),
        citations[0] if citations else {},
    )
    if not isinstance(citation, dict):
        citation = {}
    authors = citation.get("rcsb_authors") or []
    doi = str(citation.get("pdbx_database_id_DOI") or "").strip()
    pmid = str(citation.get("pdbx_database_id_PubMed") or "").strip()
    return {
        "title": str(citation.get("title") or (payload.get("struct") or {}).get("title") or f"PDB {pdb_id}"),
        "authors": "; ".join(str(author) for author in authors),
        "journal": str(citation.get("rcsb_journal_abbrev") or citation.get("journal_abbrev") or "RCSB PDB"),
        "year": str(citation.get("year") or ""),
        "doi": doi,
        "pmid": pmid,
        "url": f"https://www.rcsb.org/structure/{pdb_id}",
    }


def _crossref_metadata(message: object, *, fallback_doi: str = "") -> dict[str, str]:
    if not isinstance(message, dict):
        return {}
    titles = message.get("title") or []
    title = str(titles[0] if isinstance(titles, list) and titles else titles).strip()
    if not title:
        return {}
    authors: list[str] = []
    for raw_author in message.get("author") or []:
        if not isinstance(raw_author, dict):
            continue
        name = " ".join(
            part for part in (str(raw_author.get("given") or "").strip(), str(raw_author.get("family") or "").strip())
            if part
        )
        if name:
            authors.append(name)
    containers = message.get("container-title") or []
    journal = str(containers[0] if isinstance(containers, list) and containers else containers).strip()
    date_parts = (
        (message.get("published-print") or {}).get("date-parts")
        or (message.get("published-online") or {}).get("date-parts")
        or (message.get("issued") or {}).get("date-parts")
        or []
    )
    year = str(date_parts[0][0]) if date_parts and date_parts[0] else ""
    normalized_doi = str(message.get("DOI") or fallback_doi).strip()
    return {
        "title": title,
        "authors": "; ".join(authors),
        "journal": journal,
        "year": year,
        "doi": normalized_doi,
        "url": f"https://doi.org/{normalized_doi}",
    }


def _doi_metadata(client: httpx.Client, doi: str) -> dict[str, str]:
    response = client.get(f"https://api.crossref.org/works/{quote(doi, safe='')}")
    response.raise_for_status()
    return _crossref_metadata(response.json().get("message"), fallback_doi=doi)


def _mdpi_crossref_metadata(client: httpx.Client, url: str) -> dict[str, str]:
    """Resolve an MDPI route through Crossref when the article page blocks crawlers."""
    parsed_url = urlparse(url)
    if parsed_url.netloc.lower().removeprefix("www.") != "mdpi.com":
        return {}
    parts = [part for part in parsed_url.path.split("/") if part]
    if len(parts) < 4:
        return {}
    issn, volume, issue, article_number = parts[:4]
    if not re.fullmatch(r"\d{4}-\d{3}[\dX]", issn, re.IGNORECASE):
        return {}
    if not all(part.isdigit() for part in (volume, issue, article_number)):
        return {}
    response = client.get(
        "https://api.crossref.org/works",
        params={
            "query.bibliographic": f"{issn} {volume} {issue} {article_number}",
            "rows": 10,
        },
    )
    response.raise_for_status()
    items = (response.json().get("message") or {}).get("items") or []
    normalized_issn = issn.upper()
    for item in items:
        if not isinstance(item, dict):
            continue
        item_issns = {str(value).upper() for value in item.get("ISSN") or []}
        item_number = str(item.get("article-number") or item.get("page") or "")
        if (
            normalized_issn in item_issns
            and str(item.get("volume") or "") == volume
            and str(item.get("issue") or "") == issue
            and item_number == article_number
        ):
            return _crossref_metadata(item)
    return {}


def _metadata(client: httpx.Client, parsed: dict[str, str]) -> dict[str, str]:
    key = parsed["key"]
    if key.startswith("pmid:"):
        return _pubmed_metadata(client, parsed["pmid"])
    if key.startswith("doi:"):
        return _doi_metadata(client, parsed["doi"])
    if key.startswith("pdb:"):
        return _pdb_metadata(client, key.removeprefix("pdb:"))
    if key.startswith("url:"):
        mdpi_metadata = _mdpi_crossref_metadata(client, parsed["url"])
        if mdpi_metadata:
            return mdpi_metadata
        return _article_page_metadata(client, parsed["url"])
    return {}


def backfill(*, apply: bool) -> tuple[int, int]:
    updated_findings = 0
    enriched_sources = 0
    cache: dict[str, dict[str, Any]] = {}
    with httpx.Client(
        timeout=httpx.Timeout(20, connect=10),
        headers={"User-Agent": "BDA-Workbench/2.0 scientific-reference-backfill"},
    ) as client, session_scope() as session:
        findings = list(
            session.scalars(
                select(ResearchFinding)
                .join(Project, Project.id == ResearchFinding.project_id)
                .where(Project.deleted_at.is_(None))
                .order_by(ResearchFinding.created_at)
            )
        )
        for finding in findings:
            evidence = dict(finding.evidence or {})
            sources = list(
                dict.fromkeys([*_strings(evidence.get("sources")), *_strings(evidence.get("source_refs"))])
            )
            raw_source_metadata = evidence.get("source_metadata")
            source_metadata = dict(raw_source_metadata) if isinstance(raw_source_metadata, dict) else {}
            changed = False
            for source in sources:
                parsed = _reference_source(source)
                if not parsed or parsed["key"].startswith("uniprot:"):
                    continue
                existing_metadata = source_metadata.get(source)
                if isinstance(existing_metadata, dict) and existing_metadata.get("title"):
                    continue
                key = parsed["key"]
                if key not in cache:
                    try:
                        cache[key] = _metadata(client, parsed)
                    except (httpx.HTTPError, ValueError, KeyError):
                        cache[key] = {}
                if cache[key]:
                    source_metadata[source] = cache[key]
                    changed = True
                    enriched_sources += 1
            if changed:
                updated_findings += 1
                if apply:
                    evidence["source_metadata"] = source_metadata
                    finding.evidence = evidence
                    finding.version += 1
                    flag_modified(finding, "evidence")
        if not apply:
            session.rollback()
    return updated_findings, enriched_sources


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich migrated Research review citations.")
    parser.add_argument("--apply", action="store_true", help="Persist enriched citation metadata.")
    args = parser.parse_args()
    findings, sources = backfill(apply=args.apply)
    mode = "updated" if args.apply else "would update"
    print(f"{mode} {findings} findings with {sources} source links")


if __name__ == "__main__":
    main()
