"""Literal EPO claims, indexed as source excerpts rather than legal conclusions."""
from __future__ import annotations

import hashlib
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..artifacts.storage import ObjectStorage
from ..core.database import session_scope
from .epo_ops import PublicationRef
from .models import LiteratureChunk, LiteratureClaim, LiteratureDocument, LiteratureEvidence, LiteratureRetrievalTrace

MAX_CLAIMS = 2000


def _name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _text(node: ET.Element) -> str:
    return ' '.join(' '.join(node.itertext()).split())


def parse_claims(xml: str, reference: PublicationRef) -> list[dict[str, str]]:
    if '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
        raise ValueError('epo_claims_xml_declarations_forbidden')
    root = ET.fromstring(xml)
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for document in root.iter():
        if _name(document.tag) != 'fulltext-document':
            continue
        matched = False
        identifiers = (identifier for reference_node in document.iter()
                       if _name(reference_node.tag) == 'publication-reference'
                       for identifier in reference_node.iter() if _name(identifier.tag) == 'document-id')
        for identifier in identifiers:
            parts = {_name(child.tag): _text(child) for child in identifier}
            country = parts.get('country', '').upper()
            number = parts.get('doc-number', '').upper()
            kind = parts.get('kind', '').upper()
            if country == reference.country and number == reference.number and (not reference.kind or kind == reference.kind):
                matched = True
                break
        # Never attribute another publication's claims, even if the response contains one.
        if not matched:
            continue
        for group in document.iter():
            if _name(group.tag) != 'claims':
                continue
            language = group.attrib.get('lang', 'unknown')
            for claim in group:
                if _name(claim.tag) != 'claim':
                    continue
                number = claim.attrib.get('num') or claim.attrib.get('id') or str(len(records) + 1)
                text = _text(claim)
                if not text:
                    continue
                key = (language, number)
                if key in seen:
                    raise ValueError('epo_claims_duplicate_number')
                seen.add(key)
                records.append({'number': number, 'language': language, 'text': text})
                if len(records) > MAX_CLAIMS:
                    raise ValueError('epo_claims_count_exceeded')
    if not records:
        raise ValueError('epo_claims_unavailable_for_requested_publication')
    return records


def save_claims(
    session: Session, document: LiteratureDocument, records: list[dict[str, str]], *,
    lookup_id: str, trace_id: uuid.UUID, artifact_id: uuid.UUID, checksum: str,
) -> int:
    if (document.metadata_json or {}).get('patent_claims', {}).get('lookup_id') == lookup_id:
        return 0
    last_position = session.scalar(select(func.max(LiteratureChunk.position)).where(LiteratureChunk.document_id == document.id))
    position = last_position + 1 if last_position is not None else 0
    for offset, record in enumerate(records):
        chunk = LiteratureChunk(document_id=document.id, position=position + offset, content=record['text'])
        session.add(chunk)
        session.flush()
        provenance = {
            'content_kind': 'patent_claim', 'lookup_id': lookup_id,
            'claim_number': record['number'], 'language': record['language'],
            'retrieval_trace_id': str(trace_id), 'raw_response_artifact_id': str(artifact_id),
            'content_checksum_sha256': checksum,
        }
        claim = LiteratureClaim(
            document_id=document.id, chunk_id=chunk.id, claim=record['text'],
            confidence='verbatim_unreviewed', attributes=provenance,
        )
        session.add(claim)
        session.flush()
        session.add(LiteratureEvidence(
            claim_id=claim.id, evidence_type='verbatim_patent_claim', content=record['text'],
            source_ref={**provenance, 'document_id': str(document.id), 'chunk_id': str(chunk.id)},
        ))
    document.metadata_json = {
        **(document.metadata_json or {}),
        'patent_claims': {
            'status': 'completed', 'lookup_id': lookup_id, 'claims': len(records),
            'languages': sorted({r['language'] for r in records}),
            'retrieval_trace_id': str(trace_id), 'raw_response_artifact_id': str(artifact_id),
            'content_checksum_sha256': checksum, 'retrieved_at': datetime.now(UTC).isoformat(),
        },
    }
    document.version += 1
    return len(records)


def collect_claims(lookup_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from ..core.config import get_settings
    from .epo_ops import publication_reference
    from .epo_ops_client import EpoOpsClient, EpoOpsUnavailable, load_credential
    from .patent_service import MAX_LEGAL_STATUS_DOCUMENTS, PATENT_SOURCES
    from .tasks import _retrieval_trace_values

    project_id = uuid.UUID(str(payload['project_id']))
    requested_by = uuid.UUID(str(payload['requested_by']))
    targets: list[tuple[uuid.UUID, str | None, str | None]] = []
    for value in dict.fromkeys(payload.get('document_ids') or []):
        if len(targets) >= MAX_LEGAL_STATUS_DOCUMENTS:
            break
        with session_scope() as session:
            document = session.get(LiteratureDocument, uuid.UUID(str(value)))
            if document is None or document.project_id != project_id or document.source not in PATENT_SOURCES:
                continue
            if (document.metadata_json or {}).get('patent_claims', {}).get('lookup_id') == lookup_id:
                continue
            patent = (document.metadata_json or {}).get('patent') or {}
            targets.append((document.id, patent.get('publication_number'), patent.get('kind_code')))
    client = EpoOpsClient(load_credential(get_settings().epo_ops_credential_ref), max_calls=MAX_LEGAL_STATUS_DOCUMENTS)
    results: list[dict[str, Any]] = []
    refused: str | None = None
    try:
        for document_id, number, kind in targets:
            if refused:
                results.append({'document_id': str(document_id), 'status': 'not_attempted', 'error': refused})
                continue
            audit_start = len(client.audits)
            try:
                reference = publication_reference(str(number or ''), kind)
                result = client.claims(reference)
                xml = str(result.data['xml'])
                records = parse_claims(xml, reference)
            except (RuntimeError, ValueError, ET.ParseError) as error:
                message = str(error)[:300]
                if isinstance(error, EpoOpsUnavailable) or '_refused' in message:
                    refused = message
                with session_scope() as session:
                    trace = LiteratureRetrievalTrace(
                        project_id=project_id, document_id=document_id,
                        **_retrieval_trace_values(
                            client.audits[-1] if len(client.audits) > audit_start else {'tool': 'epo_ops.claims', 'status': 'failed'},
                            stage='patent_claims', response_metadata={'lookup_id': lookup_id}, error=message,
                        ),
                    )
                    session.add(trace)
                results.append({'document_id': str(document_id), 'status': 'failed', 'error': message})
                continue
            raw = xml.encode('utf-8')
            checksum = hashlib.sha256(raw).hexdigest()
            object_key = f'projects/{project_id}/literature/documents/{document_id}/epo-claims/{checksum}.xml'
            ObjectStorage().put_bytes(object_key, raw, 'application/xml')
            with session_scope() as session:
                document = session.scalar(select(LiteratureDocument).where(
                    LiteratureDocument.id == document_id, LiteratureDocument.project_id == project_id,
                ).with_for_update())
                if document is None or (document.metadata_json or {}).get('patent_claims', {}).get('lookup_id') == lookup_id:
                    continue
                artifact = Artifact(
                    project_id=project_id, created_by=requested_by, artifact_type='patent_claims_response',
                    filename=f'epo-claims-{reference.docdb}.xml', content_type='application/xml',
                    object_key=object_key, size_bytes=len(raw), checksum_sha256=checksum,
                    lineage={'lookup_id': lookup_id, 'document_id': str(document_id), 'database': 'epo_ops'},
                )
                session.add(artifact)
                session.flush()
                trace = LiteratureRetrievalTrace(
                    project_id=project_id, document_id=document_id,
                    **_retrieval_trace_values(result.audit, stage='patent_claims', response_metadata={
                        'lookup_id': lookup_id, 'raw_response_artifact_id': str(artifact.id), 'claims': len(records),
                    }),
                )
                session.add(trace)
                session.flush()
                count = save_claims(session, document, records, lookup_id=lookup_id, trace_id=trace.id, artifact_id=artifact.id, checksum=checksum)
            results.append({'document_id': str(document_id), 'status': 'completed', 'claims_indexed': count})
    finally:
        client.close()
    return {'lookup_id': lookup_id, 'status': 'completed_with_gaps' if any(r['status'] != 'completed' for r in results) else 'completed', 'results': results}


def search_claims(session: Session, project_id: uuid.UUID, query: str, *, after: uuid.UUID | None = None, limit: int = 50) -> dict[str, Any]:
    statement = select(LiteratureClaim, LiteratureDocument).join(LiteratureDocument, LiteratureClaim.document_id == LiteratureDocument.id).where(
        LiteratureDocument.project_id == project_id,
        LiteratureClaim.attributes['content_kind'].as_string() == 'patent_claim',
        LiteratureClaim.attributes['lookup_id'].as_string() == LiteratureDocument.metadata_json['patent_claims']['lookup_id'].as_string(),
        LiteratureClaim.claim.icontains(query, autoescape=True),
    )
    if after is not None:
        statement = statement.where(LiteratureClaim.id > after)
    rows = session.execute(statement.order_by(LiteratureClaim.id).limit(limit + 1)).all()
    items = []
    for claim, document in rows[:limit]:
        start = max(0, claim.claim.casefold().find(query.casefold()) - 100)
        items.append({
            'claim_id': str(claim.id), 'document_id': str(document.id), 'title': document.title,
            'excerpt': claim.claim[start:start + 600], **claim.attributes,
        })
    return {'items': items, 'next_id': str(rows[limit - 1][0].id) if len(rows) > limit else None}
