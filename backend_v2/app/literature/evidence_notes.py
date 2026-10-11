"""Curated argument–passage records on the existing claim/evidence storage.

Sentence extraction remains a reading aid. Only explicitly authored notes enter
this view, and source matching says nothing about the truth of an argument.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..core.problem import DomainError
from ..identity.models import User
from .models import LiteratureChunk, LiteratureClaim, LiteratureDocument, LiteratureEvidence
from .schemas import EvidenceNoteResponse, EvidenceNoteWrite, ReviewUpdate

NOTE_KIND = "argument_evidence_v1"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def is_note(claim: LiteratureClaim) -> bool:
    return (claim.attributes or {}).get("curation_kind") == NOTE_KIND


def reading_context(claim: LiteratureClaim, evidence: LiteratureEvidence, chunk: LiteratureChunk | None) -> dict:
    """Never let a project interpretation travel downstream as a paper's assertion."""
    if not is_note(claim):
        return {}
    details = claim.attributes["evidence_note"]
    return {
        "curation_kind": NOTE_KIND, "claim": details["paper_claim"], "project_argument": claim.claim,
        "evidence_relation": details["relation"], "interpretation": details["interpretation"],
        "limitations": details["limitations"], "anchor_status": anchor_status(evidence, chunk),
        "locator": evidence.source_ref.get("locator"), "review_status": claim.review_status,
        "review_scope": "Interpretation review only; not experimental validation of the project argument",
    }


def note_rows(session: Session, project_id: uuid.UUID, after: uuid.UUID | None, limit: int):
    query = (
        select(LiteratureClaim, LiteratureEvidence, LiteratureDocument, LiteratureChunk)
        .join(LiteratureEvidence, LiteratureEvidence.claim_id == LiteratureClaim.id)
        .join(LiteratureDocument, LiteratureDocument.id == LiteratureClaim.document_id)
        .outerjoin(LiteratureChunk, LiteratureChunk.id == LiteratureClaim.chunk_id)
        .where(
            LiteratureDocument.project_id == project_id,
            LiteratureClaim.attributes["curation_kind"].as_string() == NOTE_KIND,
            LiteratureEvidence.evidence_type == NOTE_KIND,
        )
    )
    if after:
        query = query.where(LiteratureClaim.id > after)
    return session.execute(query.order_by(LiteratureClaim.id).limit(limit + 1)).all()


def note_evidence(session: Session, claim: LiteratureClaim) -> LiteratureEvidence:
    row = session.scalar(select(LiteratureEvidence).where(
        LiteratureEvidence.claim_id == claim.id, LiteratureEvidence.evidence_type == NOTE_KIND,
    ))
    if not is_note(claim) or row is None:
        raise DomainError("evidence_note_not_found", "Curated evidence note was not found", status_code=404)
    return row


def source_anchor(session: Session, document: LiteratureDocument, payload: EvidenceNoteWrite) -> dict:
    provenance = (document.metadata_json or {}).get("content_provenance") or {}
    ref: dict = {
        "document_id": str(document.id),
        "url": str(payload.source_url),
        "locator": payload.locator,
        "excerpt_checksum_sha256": digest(payload.quote),
        "content_kind": "user_supplied_excerpt",
        "content_checksum_sha256": None,
        "retrieval_trace_id": None,
        "selector": [{"type": "TextQuoteSelector", "exact": payload.quote}],
        "anchor_scope": "user_supplied_excerpt",
    }
    if payload.chunk_id is None:
        return ref
    chunk = session.get(LiteratureChunk, payload.chunk_id)
    if chunk is None or chunk.document_id != document.id:
        raise DomainError("evidence_chunk_mismatch", "Choose a saved passage from this document", status_code=422)
    start = payload.quote_start
    if start is None:
        start = chunk.content.find(payload.quote)
        if start >= 0 and chunk.content.find(payload.quote, start + 1) >= 0:
            raise DomainError("evidence_quote_ambiguous", "The quote occurs more than once; select its exact position", status_code=422)
    end = start + len(payload.quote)
    if start < 0 or chunk.content[start:end] != payload.quote:
        raise DomainError("evidence_quote_mismatch", "The original quote must match the saved passage exactly", status_code=422)
    ref.update({
        "content_kind": provenance.get("content_kind", "saved_text"),
        "content_checksum_sha256": provenance.get("content_checksum_sha256"),
        "retrieval_trace_id": provenance.get("retrieval_trace_id"),
        "chunk_id": str(chunk.id), "chunk_position": chunk.position, "chunk_version": chunk.version,
        "chunk_checksum_sha256": digest(chunk.content), "anchor_scope": "saved_chunk",
        "selector": [
            {"type": "TextQuoteSelector", "exact": payload.quote,
             "prefix": chunk.content[max(0, start - 32):start], "suffix": chunk.content[end:end + 32]},
            {"type": "TextPositionSelector", "start": start, "end": end},
        ],
    })
    return ref


def anchor_status(evidence: LiteratureEvidence, chunk: LiteratureChunk | None) -> Literal["matched", "changed", "unverified"]:
    ref = evidence.source_ref
    if ref.get("anchor_scope") != "saved_chunk":
        return "unverified"
    if chunk is None or ref.get("chunk_version") != chunk.version or ref.get("chunk_checksum_sha256") != digest(chunk.content):
        return "changed"
    position: dict = next((value for value in ref.get("selector", []) if value.get("type") == "TextPositionSelector"), {})
    start, end = position.get("start"), position.get("end")
    if not isinstance(start, int) or not isinstance(end, int) or chunk.content[start:end] != evidence.content:
        return "changed"
    return "matched"


def response(claim: LiteratureClaim, evidence: LiteratureEvidence, document: LiteratureDocument,
             chunk: LiteratureChunk | None) -> EvidenceNoteResponse:
    details = claim.attributes["evidence_note"]
    return EvidenceNoteResponse(
        id=claim.id, document_id=document.id, document_title=document.title,
        argument=claim.claim, paper_claim=details["paper_claim"], interpretation=details["interpretation"],
        limitations=details["limitations"], relation=details["relation"], quote=evidence.content,
        locator=evidence.source_ref.get("locator", ""), source_url=evidence.source_ref["url"],
        source_ref=evidence.source_ref, anchor_status=anchor_status(evidence, chunk),
        review_status=claim.review_status, reviewed_by=claim.reviewed_by, reviewed_at=claim.reviewed_at,
        version=claim.version, created_at=claim.created_at, updated_at=claim.updated_at,
    )


def audit(session: Session, claim: LiteratureClaim, document: LiteratureDocument, user: User,
          action: str, snapshot: dict, before: dict | None = None) -> None:
    record_audit(session, action=action, entity_type="literature_evidence_note", entity_id=claim.id,
                 actor_id=user.id, project_id=document.project_id,
                 payload={"version": claim.version, "before": before, "after": snapshot})


def save_note(session: Session, document: LiteratureDocument, payload: EvidenceNoteWrite, user: User,
              claim: LiteratureClaim | None = None, expected_version: int | None = None) -> EvidenceNoteResponse:
    before = None
    if claim is not None:
        evidence = note_evidence(session, claim)
        if claim.version != expected_version:
            raise DomainError("version_conflict", "Evidence note changed; reload before editing", status_code=412)
        before = response(claim, evidence, document, session.get(LiteratureChunk, claim.chunk_id) if claim.chunk_id else None).model_dump(mode="json")
    # Validate before adding or mutating either resource.
    ref = source_anchor(session, document, payload)
    creating = claim is None
    if claim is None:
        claim = LiteratureClaim(document_id=document.id, confidence="unassessed", version=1)
        session.add(claim)
    claim.claim = payload.argument
    claim.chunk_id = payload.chunk_id
    claim.attributes = {"curation_kind": NOTE_KIND, "evidence_note": payload.model_dump(
        mode="json", include={"paper_claim", "interpretation", "limitations", "relation"},
    )}
    claim.review_status, claim.reviewed_by, claim.reviewed_at = "pending", None, None
    if not creating:
        claim.version += 1
    session.flush()
    if creating:
        evidence = LiteratureEvidence(claim_id=claim.id, evidence_type=NOTE_KIND, version=1)
        session.add(evidence)
    else:
        evidence.version += 1
    evidence.content, evidence.source_ref = payload.quote, ref
    session.flush()
    result = response(claim, evidence, document, session.get(LiteratureChunk, claim.chunk_id) if claim.chunk_id else None)
    audit(session, claim, document, user, "literature.evidence_note.created" if creating else "literature.evidence_note.updated",
          result.model_dump(mode="json"), before)
    return result


def review_note(session: Session, claim: LiteratureClaim, document: LiteratureDocument,
                payload: ReviewUpdate, expected_version: int, user: User) -> EvidenceNoteResponse:
    evidence = note_evidence(session, claim)
    chunk = session.get(LiteratureChunk, claim.chunk_id) if claim.chunk_id else None
    if claim.version != expected_version:
        raise DomainError("version_conflict", "Evidence note changed; reload before reviewing", status_code=412)
    if payload.review_status == "accepted" and anchor_status(evidence, chunk) == "changed":
        raise DomainError("evidence_source_changed", "The saved source changed; re-anchor the quote before accepting", status_code=409)
    before = response(claim, evidence, document, chunk).model_dump(mode="json")
    claim.review_status, claim.reviewed_by, claim.reviewed_at = payload.review_status, user.id, datetime.now(UTC)
    claim.version += 1
    session.flush()
    result = response(claim, evidence, document, chunk)
    audit(session, claim, document, user, "literature.evidence_note.reviewed", result.model_dump(mode="json"), before)
    return result
