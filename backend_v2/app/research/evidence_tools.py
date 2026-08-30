from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

IDENTIFIER_PATTERNS = {
    "pmid": re.compile(r"^[0-9]{1,12}$"),
    "doi": re.compile(r"^10\.[0-9]{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE),
    "uniprot": re.compile(r"^[A-Z0-9]{6,10}$", re.IGNORECASE),
    "pdb": re.compile(r"^[0-9][A-Z0-9]{3}$", re.IGNORECASE),
    "pmcid": re.compile(r"^PMC_?[0-9]+$", re.IGNORECASE),
}


@dataclass(frozen=True)
class EvidenceToolResult:
    data: dict[str, Any]
    audit: dict[str, Any]


@dataclass(frozen=True)
class EvidenceContentResult:
    content: bytes
    audit: dict[str, Any]


class EvidenceToolService:
    """Fixed-endpoint, read-only evidence tools with bounded retries and auditing."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        max_calls: int = 60,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
    ):
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=timeout_seconds,
            headers={"User-Agent": "BDA-Research/2.0 (controlled evidence verification)"},
        )
        self.max_calls = max_calls
        self.max_retries = max_retries
        self.calls = 0
        self.audits: list[dict[str, Any]] = []

    def close(self) -> None:
        if self._owns_client:
            self.client.close()
            self._owns_client = False

    def search_europe_pmc(self, query: str, *, page_size: int = 12) -> EvidenceToolResult:
        return self._get(
            "europe_pmc.search",
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={
                "query": query,
                "format": "json",
                "resultType": "core",
                "pageSize": max(1, min(page_size, 25)),
            },
        )

    def get_europe_pmc_full_text(self, pmcid: str) -> EvidenceContentResult:
        normalized = self._identifier("pmcid", pmcid).upper().replace("PMC_", "PMC")
        return self._get_content(
            "europe_pmc.full_text_xml",
            f"https://www.ebi.ac.uk/europepmc/webservices/rest/{normalized}/fullTextXML",
            max_bytes=10 * 1024 * 1024,
        )

    def get_crossref(self, doi: str) -> EvidenceToolResult:
        normalized = self._identifier("doi", doi)
        return self._get("crossref.work", f"https://api.crossref.org/works/{quote(normalized, safe='')}")

    def get_uniprot(self, accession: str) -> EvidenceToolResult:
        normalized = self._identifier("uniprot", accession).upper()
        return self._get("uniprot.entry", f"https://rest.uniprot.org/uniprotkb/{normalized}.json")

    def get_rcsb(self, pdb_id: str) -> EvidenceToolResult:
        normalized = self._identifier("pdb", pdb_id).upper()
        return self._get("rcsb.entry", f"https://data.rcsb.org/rest/v1/core/entry/{normalized}")

    def search_reactome(self, query: str, *, species: str = "Homo sapiens") -> EvidenceToolResult:
        return self._get(
            "reactome.search",
            "https://reactome.org/ContentService/search/query",
            params={"query": query, "species": species, "cluster": "true"},
        )

    @staticmethod
    def _identifier(kind: str, value: str) -> str:
        normalized = value.strip()
        if not IDENTIFIER_PATTERNS[kind].fullmatch(normalized):
            raise ValueError(f"invalid_{kind}_identifier")
        return normalized

    def _get(self, tool: str, url: str, *, params: dict[str, Any] | None = None) -> EvidenceToolResult:
        if self.calls >= self.max_calls:
            raise RuntimeError("evidence_tool_call_limit_reached")
        self.calls += 1
        started_at = datetime.now(UTC)
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("evidence_tool_response_not_object")
                checksum = hashlib.sha256(response.content).hexdigest()
                audit = {
                    "tool": tool,
                    "query": {"url": url, "params": params or {}},
                    "queried_at": started_at.isoformat(),
                    "response_checksum_sha256": checksum,
                    "http_status": response.status_code,
                    "content_type": response.headers.get("content-type"),
                    "byte_count": len(response.content),
                    "attempts": attempt + 1,
                    "status": "completed",
                }
                self.audits.append(audit)
                return EvidenceToolResult(data=payload, audit=audit)
            except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                if status_code is not None and status_code != 429 and status_code < 500:
                    break
        audit = {
            "tool": tool,
            "query": {"url": url, "params": params or {}},
            "queried_at": started_at.isoformat(),
            "attempts": self.max_retries + 1,
            "status": "failed",
            "error": str(last_error)[:500],
        }
        self.audits.append(audit)
        raise RuntimeError(f"{tool}_failed") from last_error

    def _get_content(
        self,
        tool: str,
        url: str,
        *,
        max_bytes: int,
    ) -> EvidenceContentResult:
        if self.calls >= self.max_calls:
            raise RuntimeError("evidence_tool_call_limit_reached")
        self.calls += 1
        started_at = datetime.now(UTC)
        last_error: Exception | None = None
        attempts = 0
        for attempt in range(self.max_retries + 1):
            attempts = attempt + 1
            try:
                response = self.client.get(url)
                response.raise_for_status()
                if len(response.content) > max_bytes:
                    raise ValueError("evidence_tool_response_too_large")
                checksum = hashlib.sha256(response.content).hexdigest()
                audit = {
                    "tool": tool,
                    "query": {"url": url, "params": {}},
                    "queried_at": started_at.isoformat(),
                    "response_checksum_sha256": checksum,
                    "http_status": response.status_code,
                    "content_type": response.headers.get("content-type"),
                    "byte_count": len(response.content),
                    "attempts": attempts,
                    "status": "completed",
                }
                self.audits.append(audit)
                return EvidenceContentResult(content=response.content, audit=audit)
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                if status_code is not None and status_code != 429 and status_code < 500:
                    break
        audit = {
            "tool": tool,
            "query": {"url": url, "params": {}},
            "queried_at": started_at.isoformat(),
            "attempts": attempts,
            "status": "failed",
            "error": str(last_error)[:500],
        }
        if isinstance(last_error, httpx.HTTPStatusError):
            audit["http_status"] = last_error.response.status_code
        self.audits.append(audit)
        raise RuntimeError(f"{tool}_failed") from last_error


def normalized_title(value: Any) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    return " ".join(re.findall(r"[a-z0-9]+", str(value).lower()))


def titles_match(left: Any, right: Any) -> bool:
    left_tokens = set(normalized_title(left).split())
    right_tokens = set(normalized_title(right).split())
    if not left_tokens or not right_tokens:
        return False
    return len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens)) >= 0.6
