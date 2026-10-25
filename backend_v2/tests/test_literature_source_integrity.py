from __future__ import annotations

import uuid

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.models import Base
from backend_v2.app.literature.indexing import extract_europe_pmc_full_text, index_document_content, is_source_sentence
from backend_v2.app.literature.models import LiteratureChunk, LiteratureClaim, LiteratureDocument, LiteratureEvidence
from backend_v2.app.literature.retrieval import europe_pmc_results
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def test_abstract_only_xml_is_not_claimed_as_full_text() -> None:
    paragraphs, metadata = extract_europe_pmc_full_text(
        b'<article><front><article-meta><abstract><p>Only an abstract.</p></abstract></article-meta></front></article>'
    )
    assert paragraphs == ['Only an abstract.']
    assert metadata['content_kind'] == 'open_access_abstract'


def test_body_excerpt_and_empty_metadata_have_distinct_scopes() -> None:
    paragraphs, metadata = extract_europe_pmc_full_text(b'<article><body><p>Body evidence.</p></body></article>')
    assert paragraphs == ['Body evidence.']
    assert metadata['content_kind'] == 'open_access_full_text'
    paragraphs, metadata = extract_europe_pmc_full_text(b'<article><front><article-title>Title only</article-title></front></article>')
    assert paragraphs == []
    assert metadata['content_kind'] == 'metadata_only'


def test_core_search_preserves_nested_journal_without_inventing_missing_metadata() -> None:
    rows = [
        {'id': '18287011', 'title': 'PD-1 complex', 'journalInfo': {'journal': {'title': 'PNAS'}}},
        {'id': '2', 'title': 'Flat response', 'journalTitle': 'Nature', 'journalInfo': {'journal': {'title': 'Ignored'}}},
        {'id': '3', 'title': 'Missing journal', 'journalInfo': None},
    ]
    results = europe_pmc_results({'resultList': {'result': rows}}, limit=3)
    assert [row['journal'] for row in results] == ['PNAS', 'Nature', '']


@pytest.mark.parametrize('value', ['2023 ).', '69 .', '3 A – C ).', 'Fig.', 'et al.'])
def test_reference_debris_is_not_a_scientific_statement(value: str) -> None:
    assert not is_source_sentence(value)


@pytest.mark.parametrize('value', ['PD-1 binds PD-L1.', 'Only an abstract.', '浓度变化会影响读数。', 'The measured Kd was 12 nM.'])
def test_short_scientific_sentences_and_non_latin_text_remain_indexable(value: str) -> None:
    assert is_source_sentence(value)


def test_duplicate_excerpts_keep_all_source_chunks_and_the_first_exact_anchor() -> None:
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        document = LiteratureDocument(project_id=uuid.uuid4(), title='Synthetic source', source='test')
        session.add(document)
        session.flush()
        paragraphs = ['2023 ). PD-1 binds PD-L1.', 'PD-1 binds PD-L1. 69 .']
        counts = index_document_content(session, document, paragraphs, content_kind='provided_abstract',
                                        content_checksum_sha256='a' * 64, retrieval_trace_id=None)
        assert counts == {'chunks': 2, 'claims': 1, 'evidence': 1}
        chunks = list(session.scalars(select(LiteratureChunk).order_by(LiteratureChunk.position)))
        assert [c.content for c in chunks] == paragraphs
        claim = session.scalar(select(LiteratureClaim))
        evidence = session.scalar(select(LiteratureEvidence))
        assert claim and evidence
        assert claim.claim == evidence.content == 'PD-1 binds PD-L1.'
        assert claim.chunk_id == chunks[0].id
        assert evidence.source_ref['sentence_index'] == 1
        assert claim.review_status == 'pending'
        assert claim.attributes['extraction_method'] == 'source_sentence_candidate'


def test_quality_exclusions_are_applied_before_claim_pagination_and_preserve_direct_access() -> None:
    from backend_v2.app.literature.repository import LiteratureRepository

    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        project_id = uuid.uuid4()
        doc = LiteratureDocument(project_id=project_id, title='Synthetic source', source='test')
        session.add(doc)
        session.flush()
        bad = LiteratureClaim(id=uuid.UUID(int=1), document_id=doc.id, claim='2023 ).',
                              attributes={'source_quality': {'status': 'excluded'}})
        good = LiteratureClaim(id=uuid.UUID(int=2), document_id=doc.id, claim='PD-1 binds PD-L1.')
        session.add_all([bad, good])
        session.flush()
        repository = LiteratureRepository(session)
        assert [c.id for c in repository.list_claims(project_id, None, 1, None)] == [good.id]
        assert repository.claim(bad.id).claim == '2023 ).'
        assert len(repository.document_detail(doc.id)[1]) == 2
