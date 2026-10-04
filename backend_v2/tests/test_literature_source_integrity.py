from __future__ import annotations

from backend_v2.app.literature.indexing import extract_europe_pmc_full_text
from backend_v2.app.literature.retrieval import europe_pmc_results


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
