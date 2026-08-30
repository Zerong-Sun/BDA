from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import LiteratureChunk, LiteratureClaim, LiteratureDocument, LiteratureEvidence

SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+")
WHITESPACE = re.compile(r"\s+")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _element_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return WHITESPACE.sub(" ", " ".join(element.itertext())).strip()


def extract_europe_pmc_full_text(xml_bytes: bytes) -> tuple[list[str], dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    article_title = ""
    license_text = ""
    for element in root.iter():
        name = _local_name(element.tag)
        if name == "article-title" and not article_title:
            article_title = _element_text(element)
        elif name == "license-p" and not license_text:
            license_text = _element_text(element)

    paragraphs: list[str] = []
    body = next((element for element in root.iter() if _local_name(element.tag) == "body"), None)
    if body is not None:
        for section in (element for element in body.iter() if _local_name(element.tag) == "sec"):
            title = next(
                (_element_text(child) for child in section if _local_name(child.tag) == "title"),
                "",
            )
            for child in section:
                if _local_name(child.tag) != "p":
                    continue
                text = _element_text(child)
                if text:
                    paragraphs.append(f"{title}: {text}" if title else text)
        for child in body:
            if _local_name(child.tag) == "p":
                text = _element_text(child)
                if text:
                    paragraphs.append(text)

    if not paragraphs:
        abstract = next((element for element in root.iter() if _local_name(element.tag) == "abstract"), None)
        abstract_text = _element_text(abstract)
        if abstract_text:
            paragraphs.append(abstract_text)
    return paragraphs[:500], {
        "article_title": article_title,
        "license_text": license_text[:2000],
        "content_checksum_sha256": hashlib.sha256(xml_bytes).hexdigest(),
    }


def index_document_content(
    session: Session,
    document: LiteratureDocument,
    paragraphs: list[str],
    *,
    content_kind: str,
    content_checksum_sha256: str,
    retrieval_trace_id: str | None,
    extract_claims: bool = True,
) -> dict[str, int]:
    existing = session.scalar(select(LiteratureChunk.id).where(LiteratureChunk.document_id == document.id).limit(1))
    if existing is not None:
        return {"chunks": 0, "claims": 0, "evidence": 0}

    identifiers = {
        key: value
        for key, value in {
            "doi": (document.metadata_json or {}).get("doi"),
            "pmid": (document.metadata_json or {}).get("pmid"),
            "pmcid": (document.metadata_json or {}).get("pmcid"),
        }.items()
        if value
    }
    counts = {"chunks": 0, "claims": 0, "evidence": 0}
    for position, paragraph in enumerate(paragraphs[:500]):
        normalized = WHITESPACE.sub(" ", paragraph).strip()
        if not normalized:
            continue
        chunk = LiteratureChunk(document_id=document.id, position=position, content=normalized)
        session.add(chunk)
        session.flush()
        counts["chunks"] += 1
        if not extract_claims:
            continue
        sentences = [item.strip() for item in SENTENCE_SPLIT.split(normalized) if item.strip()]
        for sentence_index, sentence in enumerate(sentences[:20]):
            claim = LiteratureClaim(
                document_id=document.id,
                chunk_id=chunk.id,
                claim=sentence,
                confidence=f"{content_kind}_unreviewed",
                attributes={
                    "source": document.source,
                    "content_kind": content_kind,
                    "content_checksum_sha256": content_checksum_sha256,
                    "identifiers": identifiers,
                    "analysis_status": "pending_human_review",
                },
            )
            session.add(claim)
            session.flush()
            counts["claims"] += 1
            session.add(
                LiteratureEvidence(
                    claim_id=claim.id,
                    evidence_type="verbatim_source_excerpt",
                    content=sentence,
                    source_ref={
                        "document_id": str(document.id),
                        "chunk_id": str(chunk.id),
                        "chunk_position": position,
                        "sentence_index": sentence_index,
                        "retrieval_trace_id": retrieval_trace_id,
                        "content_kind": content_kind,
                        "content_checksum_sha256": content_checksum_sha256,
                        **identifiers,
                    },
                )
            )
            counts["evidence"] += 1
    return counts
