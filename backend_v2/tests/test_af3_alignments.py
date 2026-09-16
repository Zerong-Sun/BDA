from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from backend_v2.app.artifacts import af3_alignments
from backend_v2.app.artifacts.models import Artifact, ArtifactLineageEdge
from backend_v2.app.core.problem import DomainError
from backend_v2.app.sequences.service import conservation_from_artifact
from backend_v2.app.targets.models import Target
from backend_v2.tests.test_sequences_conservation_service import ALIGNMENT, _project
from backend_v2.tests.test_sequences_conservation_service import session as session
from backend_v2.tests.test_sequences_conservation_service import stored as stored
from sqlalchemy import select

PAYLOAD = {'sequences': [{'protein': {'id': ['A', 'B'], 'sequence': 'MKVLAA', 'unpairedMsa': ALIGNMENT, 'pairedMsa': ''}}]}


def test_extracts_real_embedded_msa_with_chain_identity_and_query_digest():
    rows = af3_alignments.extract(PAYLOAD)
    assert [r['chain_id'] for r in rows] == ['A', 'B']
    assert all(r['text'] == ALIGNMENT for r in rows)
    assert rows[0]['query_sha256'] == hashlib.sha256(b'MKVLAA').hexdigest()
    paths_only = {'sequences': [{'protein': {'id': 'A', 'sequence': 'MKVLAA', 'unpairedMsaPath': '/never/read'}}]}
    assert af3_alignments.extract(paths_only) == []


@pytest.mark.parametrize('change', [
    {'id': '../escape'}, {'sequence': 'AAAAAA'}, {'unpairedMsa': '>only\nMKVLAA'}, {'unpairedMsa': ['invalid']},
])
def test_refuses_ambiguous_invalid_or_fake_alignments(change):
    payload = copy.deepcopy(PAYLOAD)
    payload['sequences'][0]['protein'].update(change)
    with pytest.raises(ValueError):
        af3_alignments.extract(payload)


def test_collection_records_parent_hash_chain_port_and_target_lookup(session, stored, monkeypatch):
    project, user = _project(session)
    payload = copy.deepcopy(PAYLOAD)
    payload['sequences'][0]['protein']['id'] = 'A'
    raw = json.dumps(payload).encode()
    source = Artifact(project_id=project, created_by=user, artifact_type='manifest', filename='example_data.json',
                      content_type='application/json', object_key='example_data', size_bytes=len(raw),
                      checksum_sha256=hashlib.sha256(raw).hexdigest(), lineage={'job_id': 'job', 'attempt': 1})
    session.add(source)
    target = Target(project_id=project, name='Example target', sequence='MKVLAA')
    session.add(target)
    session.flush()
    stored[source.object_key] = raw
    class Storage:
        def read_bytes(self, key, **kwargs):
            return stored[key]
        def put_bytes(self, key, body, content_type):
            stored[key] = body
    monkeypatch.setattr(af3_alignments, 'ObjectStorage', Storage)
    derived = af3_alignments.collect(session, [source], declared=True)
    session.flush()
    assert len(derived) == 1
    msa = derived[0]
    assert msa.lineage['source_checksum_sha256'] == source.checksum_sha256
    assert msa.lineage['output_port'] == 'protein_msa'
    assert stored[msa.object_key] == ALIGNMENT.encode()
    assert session.scalar(select(ArtifactLineageEdge)).parent_artifact_id == source.id
    result = conservation_from_artifact(session, project, target_id=target.id)
    assert result['artifact_id'] == str(msa.id)
    assert result['alignment']['sequences'] == 4
    assert 'MKVLAA' not in json.dumps(result)
    elsewhere, _ = _project(session)
    with pytest.raises(DomainError) as denied:
        conservation_from_artifact(session, elsewhere, target_id=target.id)
    assert denied.value.status_code == 404
    duplicate = Artifact(project_id=project, created_by=user, artifact_type=msa.artifact_type, filename='other.a3m',
                         object_key='other', content_type='text/plain', size_bytes=msa.size_bytes,
                         checksum_sha256=msa.checksum_sha256, lineage=msa.lineage)
    session.add(duplicate)
    session.flush()
    with pytest.raises(DomainError) as ambiguous:
        conservation_from_artifact(session, project, target_id=target.id)
    assert ambiguous.value.error_code == 'target_alignment_ambiguous'
    source.checksum_sha256 = '0' * 64
    assert af3_alignments.collect(session, [source], declared=True) == []
    assert source.lineage['msa_extraction']['status'] == 'unavailable'


def test_port_declaration_matches_the_frozen_migration():
    path = Path(__file__).parents[1] / 'alembic/versions/0070_af3_msa_port.py'
    spec = importlib.util.spec_from_file_location('msa_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.PORT == af3_alignments.PORT
