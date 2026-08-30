from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..literature.models import (
    LiteratureChunk,
    LiteratureClaim,
    LiteratureDocument,
    LiteratureEvidence,
    LiteratureSearchRun,
)
from ..projects.models import Project
from ..research.workspace import build_research_workspace

SENSITIVE_KEYS = {"download_url", "object_key", "credential_ref", "api_key", "token"}
WORD_PATTERN = re.compile(r"[A-Za-z0-9_.:/-]+|[\u3400-\u9fff]")


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items() if key not in SENSITIVE_KEYS}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("default") or value.get("zh") or value.get("en") or "")
    if value is None:
        return ""
    return str(value)


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in WORD_PATTERN.findall(value) if token.strip()}


@dataclass(frozen=True)
class ResearchContextResult:
    context: str
    citations: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]


class ResearchContextService:
    """Token-bounded, read-only access to the canonical Research workspace."""

    def __init__(self, session: Session, project: Project):
        self.session = session
        self.project_id = project.id
        self.workspace = _sanitize(build_research_workspace(session, project).model_dump(mode="json"))
        self._documents = {
            row.id: row
            for row in session.scalars(
                select(LiteratureDocument)
                .where(LiteratureDocument.project_id == project.id)
                .order_by(LiteratureDocument.created_at)
            )
        }
        self._items = self._flatten()
        self._items.extend(self._literature_evidence_items())

    def research_overview(self) -> dict[str, Any]:
        project = self.workspace["project"]
        review = self.workspace.get("review_document")
        return {
            "project": project,
            "review_document": {
                "id": review.get("id"),
                "title": review.get("title"),
                "status": review.get("status"),
                "updated_at": review.get("updated_at"),
            }
            if review
            else None,
            "counts": self.workspace.get("counts", {}),
            "available_kinds": sorted({item["kind"] for item in self._items}),
        }

    def search_research(
        self,
        query: str,
        *,
        limit: int = 12,
        allowed_kinds: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        terms = _tokens(query)
        ranked: list[tuple[int, dict[str, Any]]] = []
        for item in self._items:
            if allowed_kinds is not None and item["kind"] not in allowed_kinds:
                continue
            haystack = json.dumps(item["data"], ensure_ascii=False, default=str).lower()
            score = sum(3 if term in item["label"].lower() else 1 for term in terms if term in haystack)
            if not terms or score:
                ranked.append((score, item))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]["kind"], pair[1]["id"]))
        return [item for _, item in ranked[: max(1, min(limit, 50))]]

    def get_research_items(
        self,
        kind: str,
        *,
        ids: list[str] | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        selected = [item for item in self._items if item["kind"] == kind]
        if ids:
            wanted = set(ids)
            selected = [item for item in selected if item["id"] in wanted]
        return selected[max(0, offset) : max(0, offset) + max(1, min(limit, 100))]

    def get_dataset_slice(self, dataset_id: str, *, offset: int = 0, limit: int = 25) -> dict[str, Any] | None:
        for dataset in self.workspace.get("datasets", []):
            if str(dataset.get("id")) != dataset_id and str(dataset.get("key")) != dataset_id:
                continue
            data = dataset.get("data")
            if isinstance(data, list):
                data = data[max(0, offset) : max(0, offset) + max(1, min(limit, 100))]
            return {**dataset, "data": data}
        return None

    def get_reference(self, reference_id: str) -> dict[str, Any] | None:
        for reference in self.workspace.get("references", []):
            if reference_id in {str(reference.get("document_id")), str(reference.get("ref_id"))}:
                return reference
        return None

    def get_reference_content(
        self,
        reference_id: str,
        *,
        offset: int = 0,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        document_id: str | None = None
        reference: dict[str, Any] | None = None
        for candidate in self.workspace.get("references", []):
            if reference_id in {str(candidate.get("document_id")), str(candidate.get("ref_id"))}:
                document_id = str(candidate.get("document_id"))
                reference = candidate
                break
        if document_id is None:
            return []
        chunks = list(
            self.session.scalars(
                select(LiteratureChunk)
                .where(LiteratureChunk.document_id == uuid.UUID(document_id))
                .order_by(LiteratureChunk.position)
                .offset(max(0, offset))
                .limit(max(1, min(limit, 50)))
            )
        )
        provenance = ((reference or {}).get("metadata") or {}).get("content_provenance") or {}
        return [
            {
                "kind": "literature_excerpt",
                "id": str(chunk.id),
                "label": _text((reference or {}).get("title")) or f"Literature chunk {chunk.position}",
                "data": {
                    "document_id": document_id,
                    "ref_id": (reference or {}).get("ref_id"),
                    "title": (reference or {}).get("title"),
                    "url": (reference or {}).get("url"),
                    "chunk_id": str(chunk.id),
                    "position": chunk.position,
                    "content": chunk.content,
                    "review_status": ((reference or {}).get("metadata") or {}).get("review_status", "pending_review"),
                    "content_provenance": provenance,
                },
            }
            for chunk in chunks
        ]

    def grounding_packet(
        self,
        citations: list[dict[str, Any]],
        *,
        max_chunks: int = 24,
        max_chars: int = 28_000,
    ) -> str:
        """Return a bounded packet of the exact saved excerpts behind citations."""
        ordered = sorted(
            citations,
            key=lambda item: 0 if item.get("workspace_type") == "literature_excerpt" else 1,
        )
        seen: set[str] = set()
        search_run_ids: set[str] = set()
        packet: list[dict[str, Any]] = []
        used_chars = 0
        for citation in ordered:
            if citation.get("source_type") != "scientific_literature":
                continue
            chunk_id = str(citation.get("chunk_id") or "")
            if not chunk_id or chunk_id in seen:
                continue
            try:
                chunk = self.session.get(LiteratureChunk, uuid.UUID(chunk_id))
            except ValueError:
                continue
            if chunk is None:
                continue
            document = self.session.get(LiteratureDocument, chunk.document_id)
            if document is None or document.project_id != self.project_id:
                continue
            remaining = max_chars - used_chars
            if remaining <= 0 or len(packet) >= max_chunks:
                break
            excerpt = chunk.content[: min(1600, remaining)]
            provenance = (document.metadata_json or {}).get("content_provenance") or {}
            search_run_id = str((document.metadata_json or {}).get("search_run_id") or "")
            if search_run_id:
                search_run_ids.add(search_run_id)
            packet.append(
                {
                    "document_id": str(document.id),
                    "chunk_id": str(chunk.id),
                    "title": document.title,
                    "content_kind": provenance.get("content_kind"),
                    "content_checksum_sha256": provenance.get("content_checksum_sha256"),
                    "retrieval_trace_id": provenance.get("retrieval_trace_id"),
                    "search_run_id": search_run_id or None,
                    "retrieval_database": provenance.get("database"),
                    "retrieval_query": provenance.get("query"),
                    "retrieved_at": provenance.get("retrieved_at"),
                    "review_status": (document.metadata_json or {}).get("review_status", "pending_review"),
                    "excerpt": excerpt,
                }
            )
            seen.add(chunk_id)
            used_chars += len(excerpt)
        searches: list[dict[str, Any]] = []
        for search_run_id in sorted(search_run_ids):
            try:
                run = self.session.get(LiteratureSearchRun, uuid.UUID(search_run_id))
            except ValueError:
                continue
            if run is None or run.project_id != self.project_id:
                continue
            searches.append(
                {
                    "search_run_id": str(run.id),
                    "database_sources": run.sources,
                    "query": run.query,
                    "result_count": run.result_count,
                    "requested_limit": run.requested_limit,
                    "status": run.status,
                    "created_at": run.created_at,
                    "completed_at": run.completed_at,
                }
            )
        return json.dumps(
            {
                "scope": (
                    "Exact saved literature excerpts used by the draft. These remain pending human review. "
                    "Anything not supported here must be removed, parameterized, or labeled as a hypothesis."
                ),
                "searches": searches,
                "items": packet,
            },
            ensure_ascii=False,
            default=str,
        )

    def build_context(
        self,
        query: str,
        *,
        selected_entity_ids: list[str] | None = None,
        max_items: int = 12,
        allowed_kinds: set[str] | None = None,
    ) -> ResearchContextResult:
        selected: list[dict[str, Any]] = []
        selected_ids = set(selected_entity_ids or [])
        if selected_ids:
            selected.extend(
                item
                for item in self._items
                if item["id"] in selected_ids and (allowed_kinds is None or item["kind"] in allowed_kinds)
            )
        seen = {(item["kind"], item["id"]) for item in selected}
        for item in self.search_research(query, limit=max_items, allowed_kinds=allowed_kinds):
            key = (item["kind"], item["id"])
            if key not in seen:
                selected.append(item)
                seen.add(key)
            if len(selected) >= max_items:
                break

        citations = [self._citation(item) for item in selected]
        context_payload = {
            "overview": self.research_overview(),
            "retrieved_items": selected,
            "coverage": {
                "retrieved": len(selected),
                "available": len(self._items),
                "note": "Only retrieved items may be used as factual evidence. Request another page if needed.",
            },
        }
        return ResearchContextResult(
            context=json.dumps(context_payload, ensure_ascii=False, default=str),
            citations=citations,
            tool_calls=[
                {
                    "name": "research_overview",
                    "status": "completed",
                },
                {
                    "name": "search_research",
                    "arguments": {"query": query, "limit": max_items},
                    "status": "completed",
                    "result_count": len(selected),
                },
            ],
        )

    def _flatten(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []

        def add(kind: str, identifier: Any, label: Any, data: Any) -> None:
            items.append({"kind": kind, "id": str(identifier), "label": _text(label), "data": data})

        project = self.workspace["project"]
        add("project", project["id"], project.get("name"), project)
        if project.get("primary_target"):
            target = project["primary_target"]
            add("primary_target", target.get("id", "primary_target"), target.get("name"), target)
        if self.workspace.get("review_document"):
            review = self.workspace["review_document"]
            add("review_document", review["id"], review.get("title"), review)
        for section in self.workspace.get("review_sections", []):
            for finding in section.get("items", []):
                add("review_finding", finding["id"], finding.get("title"), {**finding, "track": section.get("track")})
        mappings = {
            "graph_nodes": ("graph_node", "id", "label"),
            "graph_edges": ("graph_edge", "id", "summary"),
            "references": ("reference", "document_id", "title"),
            "structures": ("structure", "artifact_id", "name"),
            "research_targets": ("research_target", "id", "name"),
            "methods": ("method", "id", "title"),
            "datasets": ("dataset", "id", "title"),
        }
        for collection, (kind, id_key, label_key) in mappings.items():
            for row in self.workspace.get(collection, []):
                add(kind, row[id_key], row.get(label_key), row)
        return items

    def _literature_evidence_items(self) -> list[dict[str, Any]]:
        rows = self.session.execute(
            select(LiteratureEvidence, LiteratureClaim, LiteratureDocument)
            .join(LiteratureClaim, LiteratureClaim.id == LiteratureEvidence.claim_id)
            .join(LiteratureDocument, LiteratureDocument.id == LiteratureClaim.document_id)
            .where(LiteratureDocument.project_id == self.project_id)
            .order_by(LiteratureDocument.created_at, LiteratureClaim.created_at)
            .limit(2000)
        ).all()
        items: list[dict[str, Any]] = []
        for evidence, claim, document in rows:
            metadata = document.metadata_json or {}
            source_ref = evidence.source_ref or {}
            ref_id = str(metadata.get("ref_id") or document.external_id or document.id)
            items.append(
                {
                    "kind": "literature_evidence",
                    "id": str(evidence.id),
                    "label": document.title,
                    "data": {
                        "document_id": str(document.id),
                        "claim_id": str(claim.id),
                        "chunk_id": str(claim.chunk_id) if claim.chunk_id else None,
                        "ref_id": ref_id,
                        "title": document.title,
                        "url": metadata.get("url"),
                        "claim": claim.claim,
                        "excerpt": evidence.content,
                        "evidence_type": evidence.evidence_type,
                        "confidence": claim.confidence,
                        "review_status": claim.review_status,
                        "source_ref": source_ref,
                        "content_provenance": metadata.get("content_provenance") or {},
                        "verification_status": metadata.get("verification_status"),
                    },
                }
            )
        return items

    @staticmethod
    def _citation(item: dict[str, Any]) -> dict[str, Any]:
        data = item["data"]
        reference_ids = data.get("reference_ids") if isinstance(data, dict) else None
        url = ""
        if isinstance(data, dict):
            url = str(data.get("url") or data.get("rcsb_url") or "")
        citation = {
            "source_type": "research_workspace",
            "workspace_type": item["kind"],
            "entity_id": item["id"],
            "label": item["label"],
            "reference_ids": reference_ids if isinstance(reference_ids, list) else [],
            "url": url or None,
            "evidence_grade": data.get("evidence_grade") if isinstance(data, dict) else None,
            "review_status": data.get("review_status") if isinstance(data, dict) else None,
        }
        if item["kind"] in {"literature_evidence", "literature_excerpt"} and isinstance(data, dict):
            provenance = data.get("content_provenance") or {}
            source_ref = data.get("source_ref") or {}
            citation.update(
                {
                    "source_type": "scientific_literature",
                    "document_id": data.get("document_id"),
                    "claim_id": data.get("claim_id"),
                    "chunk_id": data.get("chunk_id"),
                    "reference_ids": [data.get("ref_id")] if data.get("ref_id") else [],
                    "content_kind": provenance.get("content_kind") or source_ref.get("content_kind"),
                    "content_checksum_sha256": (
                        provenance.get("content_checksum_sha256") or source_ref.get("content_checksum_sha256")
                    ),
                    "retrieval_trace_id": (
                        provenance.get("retrieval_trace_id") or source_ref.get("retrieval_trace_id")
                    ),
                    "verification_status": data.get("verification_status"),
                }
            )
        return citation

    def citation_for_item(self, item: dict[str, Any]) -> dict[str, Any]:
        return self._citation(item)
