from __future__ import annotations

import uuid
from contextlib import contextmanager

import httpx
import pytest
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.literature import epo_ops_client, patent_claims
from backend_v2.app.literature.epo_ops import PublicationRef
from backend_v2.app.literature.models import LiteratureClaim, LiteratureDocument, LiteratureRetrievalTrace
from backend_v2.app.projects.models import Project
from backend_v2.tests.test_literature_epo_ops_client import _client, _token
from backend_v2.tests.test_literature_patent_service import _patent, _project
from backend_v2.tests.test_literature_patent_service import session as session
from sqlalchemy import func, select

XML = '''<ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns="http://www.epo.org/fulltext">
<fulltext-documents><fulltext-document>
<bibliographic-data><publication-reference><document-id document-id-type="docdb">
<country>EP</country><doc-number>100</doc-number><kind>A1</kind>
</document-id></publication-reference></bibliographic-data>
<claims lang="en"><claim num="1"><claim-text>An example device with a <claim-text>bounded sensor.</claim-text></claim-text></claim>
<claim num="2"><claim-text>The device of claim 1 with a 50% indicator.</claim-text></claim></claims>
<claims lang="de"><claim num="1"><claim-text>Ein Beispiel.</claim-text></claim></claims>
</fulltext-document></fulltext-documents></ops:world-patent-data>'''
REFERENCE = PublicationRef('EP', '100', 'A1')


def test_claim_numbers_languages_and_nested_text_are_preserved():
    claims = patent_claims.parse_claims(XML, REFERENCE)
    assert [(c['language'], c['number']) for c in claims] == [('en', '1'), ('en', '2'), ('de', '1')]
    assert claims[0]['text'] == 'An example device with a bounded sensor.'


@pytest.mark.parametrize('xml,reference', [
    (XML, PublicationRef('EP', '999', 'A1')),
    (XML, PublicationRef('EP', '100', 'B1')),
    ('<!DOCTYPE x [<!ENTITY y "boom">]>' + XML, REFERENCE),
    (XML.replace('num="2"', 'num="1"'), REFERENCE),
])
def test_ambiguous_or_wrong_publication_claims_are_refused(xml, reference):
    with pytest.raises(ValueError):
        patent_claims.parse_claims(xml, reference)


def test_claims_client_requests_xml_and_keeps_credentials_out_of_audit():
    def handler(request):
        if request.url.path.endswith('/auth/accesstoken'):
            return _token(request)
        assert request.headers['Accept'] == 'application/xml'
        assert request.url.path.endswith('/publication/docdb/EP.100.A1/claims')
        return httpx.Response(200, content=XML.encode(), headers={'Content-Type': 'application/xml'})
    client, _ = _client(handler)
    result = client.claims(REFERENCE)
    assert result.data['xml'] == XML
    assert 'Authorization' not in str(result.audit)
    assert result.audit['byte_count'] == len(XML.encode())


def test_collection_preserves_abstracts_and_is_idempotent_and_search_is_project_scoped(session, monkeypatch):
    project_id = _project(session)
    other_id = _project(session)
    document = _patent(session, project_id, 'EP100', country='EP', kind='A1', stage='application')
    owner = session.get(Project, project_id).owner_id
    document.abstract = 'Existing saved abstract'
    session.commit()
    blobs = {}

    @contextmanager
    def scope():
        yield session
        session.commit()

    class Storage:
        def put_bytes(self, key, content, content_type):
            blobs[key] = content

    class Client:
        def __init__(self, *args, **kwargs):
            self.audits = []
        def claims(self, reference):
            from backend_v2.app.research.evidence_tools import EvidenceToolResult
            return EvidenceToolResult(data={'xml': XML}, audit={'tool': 'epo_ops.claims', 'status': 'completed'})
        def close(self):
            pass

    monkeypatch.setattr(patent_claims, 'session_scope', scope)
    monkeypatch.setattr(patent_claims, 'ObjectStorage', Storage)
    monkeypatch.setattr(epo_ops_client, 'load_credential', lambda _: ('test', 'test'))
    monkeypatch.setattr(epo_ops_client, 'EpoOpsClient', Client)
    lookup = str(uuid.uuid4())
    payload = {'project_id': str(project_id), 'requested_by': str(owner), 'document_ids': [str(document.id)]}
    result = patent_claims.collect_claims(lookup, payload)
    assert result['results'][0]['claims_indexed'] == 3
    patent_claims.collect_claims(lookup, payload)
    assert session.scalar(select(func.count()).select_from(LiteratureClaim)) == 3
    assert session.scalar(select(func.count()).select_from(Artifact)) == 1
    assert session.get(LiteratureDocument, document.id).abstract == 'Existing saved abstract'
    assert len(patent_claims.search_claims(session, project_id, 'device')['items']) == 2
    assert len(patent_claims.search_claims(session, project_id, '50%')['items']) == 1
    assert patent_claims.search_claims(session, project_id, '%device')['items'] == []
    assert patent_claims.search_claims(session, other_id, 'device')['items'] == []
    first = patent_claims.search_claims(session, project_id, 'device', limit=1)
    second = patent_claims.search_claims(session, project_id, 'device', after=uuid.UUID(first['next_id']), limit=1)
    assert first['items'][0]['claim_id'] != second['items'][0]['claim_id']
    assert len(blobs) == 1
    trace = session.scalar(select(LiteratureRetrievalTrace))
    assert trace.response_metadata['claims'] == 3


def test_quota_refusal_stops_later_requests_and_cross_project_documents_are_ignored(session, monkeypatch):
    project = _project(session)
    other = _project(session)
    docs = [_patent(session, project, f'EP{n}', country='EP', kind='A1', stage='application') for n in (100, 200)]
    elsewhere = _patent(session, other, 'EP300', country='EP', kind='A1', stage='application')
    owner = session.get(Project, project).owner_id
    session.commit()
    calls = []
    @contextmanager
    def scope():
        yield session
        session.commit()
    class Client:
        def __init__(self, *args, **kwargs):
            self.audits = []
        def claims(self, reference):
            calls.append(reference)
            raise epo_ops_client.EpoOpsUnavailable('epo_ops_quota_refused')
        def close(self):
            pass
    monkeypatch.setattr(patent_claims, 'session_scope', scope)
    monkeypatch.setattr(epo_ops_client, 'load_credential', lambda _: ('test', 'test'))
    monkeypatch.setattr(epo_ops_client, 'EpoOpsClient', Client)
    result = patent_claims.collect_claims(str(uuid.uuid4()), {
        'project_id': str(project), 'requested_by': str(owner),
        'document_ids': [str(d.id) for d in [*docs, elsewhere]],
    })
    assert len(calls) == 1
    assert [r['status'] for r in result['results']] == ['failed', 'not_attempted']
    assert result['status'] == 'completed_with_gaps'
    assert session.scalar(select(func.count()).select_from(Artifact)) == 0
