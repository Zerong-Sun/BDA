"""Extract real AF3 protein alignments from its collected, checksummed data JSON.

Only embedded paired/unpaired A3M is read. Path fields are never followed. The
query must match the protein sequence; no alignment is inferred from a sequence.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from ..sequences.conservation import AlignmentError, parse_alignment
from .models import Artifact, ArtifactLineageEdge
from .storage import ObjectStorage

MAX_BYTES = 64 * 1024 * 1024
PORT = {
    'name': 'protein_msa', 'kind': 'msa', 'artifact_type': 'sequence_alignment',
    'filename_glob': '*_msa.a3m',
    'description': 'Protein paired/unpaired A3M extracted from collected AF3 data JSON, with source and chain provenance.',
}


def extract(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get('sequences'), list):
        raise ValueError('af3_data_sequences_missing')
    results: list[dict[str, Any]] = []
    names: set[tuple[str, str]] = set()
    for entry in payload['sequences']:
        protein = entry.get('protein') if isinstance(entry, dict) else None
        if not isinstance(protein, dict):
            continue
        chains = protein.get('id')
        chains = chains if isinstance(chains, list) else [chains]
        if not chains or any(not isinstance(chain, str) or not re.fullmatch(r'[A-Za-z0-9]{1,16}', chain) for chain in chains):
            raise ValueError('af3_chain_id_invalid')
        sequence = protein.get('sequence')
        if not isinstance(sequence, str) or not re.fullmatch(r'[A-Z]+', sequence):
            raise ValueError('af3_protein_sequence_invalid')
        for field in ('unpairedMsa', 'pairedMsa'):
            text = protein.get(field)
            if not text:
                continue
            if not isinstance(text, str):
                raise ValueError('af3_msa_text_invalid')
            try:
                rows = parse_alignment(text)
            except AlignmentError as error:
                raise ValueError('af3_msa_invalid') from error
            if rows[0] != sequence:
                raise ValueError('af3_msa_query_mismatch')
            for chain in chains:
                key = (chain, field)
                if key in names:
                    raise ValueError('af3_msa_chain_duplicate')
                names.add(key)
                results.append({'chain_id': chain, 'msa_kind': field, 'text': text,
                                'query_sha256': hashlib.sha256(sequence.encode()).hexdigest()})
                if len(results) > 512:
                    raise ValueError('af3_msa_count_exceeded')
    return results


def collect(session: Session, sources: list[Artifact], *, declared: bool) -> list[Artifact]:
    derived: list[Artifact] = []
    storage = ObjectStorage()
    for source in sources:
        if not source.filename.endswith('_data.json'):
            continue
        try:
            raw = storage.read_bytes(source.object_key, max_bytes=MAX_BYTES)
            if hashlib.sha256(raw).hexdigest() != source.checksum_sha256:
                raise ValueError('af3_data_checksum_mismatch')
            records = extract(json.loads(raw))
        except (ValueError, UnicodeDecodeError) as error:
            # Preserve the raw output and the rest of the prediction. A missing
            # alignment is reported, never replaced with a query-only fake MSA.
            source.lineage = {**source.lineage, 'msa_extraction': {'status': 'unavailable', 'reason': type(error).__name__}}
            continue
        source.lineage = {**source.lineage, 'msa_extraction': {'status': 'completed' if records else 'unavailable', 'alignments': len(records)}}
        for record in records:
            body = record.pop('text').encode()
            checksum = hashlib.sha256(body).hexdigest()
            filename = f"{source.id}_{record['chain_id']}_{record['msa_kind']}_msa.a3m"
            key = f'projects/{source.project_id}/derived/af3/{source.id}/{filename}/{checksum}'
            storage.put_bytes(key, body, 'text/plain')
            artifact = Artifact(
                project_id=source.project_id, created_by=source.created_by,
                artifact_type='sequence_alignment', filename=filename, content_type='text/plain',
                object_key=key, size_bytes=len(body), checksum_sha256=checksum,
                lineage={
                    'job_id': source.lineage.get('job_id'), 'attempt': source.lineage.get('attempt'),
                    'output_port': PORT['name'] if declared else None,
                    'source_artifact_id': str(source.id), 'source_checksum_sha256': source.checksum_sha256,
                    'method': 'alphafold3_embedded_msa', **record,
                },
            )
            session.add(artifact)
            session.flush()
            session.add(ArtifactLineageEdge(
                project_id=source.project_id, parent_artifact_id=source.id, child_artifact_id=artifact.id,
                relation='extracted_alignment', details=record,
            ))
            derived.append(artifact)
    return derived
