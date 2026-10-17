import json
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot.chat_context import compact_research_context, history_citations, select_chat_history
from backend_v2.app.copilot.citations import rebase_history_markers


def test_history_keeps_recent_complete_messages_without_reasoning_or_mutation():
    history = [SimpleNamespace(role='user', content='older' * 4000, citations=[], reasoning_content='private'),
               SimpleNamespace(role='assistant', content='Recent answer.', citations=[], reasoning_content='never resend'),
               SimpleNamespace(role='user', content='What changed?', citations=[])]
    selected = select_chat_history(history)
    assert [row.content for row in selected] == ['Recent answer.', 'What changed?']
    assert not hasattr(selected[0], 'reasoning_content')
    assert history[1].reasoning_content == 'never resend'


def test_oversized_unicode_history_is_explicitly_previewed_within_serialized_budget():
    selected = select_chat_history([{'role': 'assistant', 'content': '研究结果' * 10000 + '[cite:1]', 'citations': []}])
    assert 'History preview truncated' in selected[0].content
    serialized = json.dumps([{'role': row.role, 'content': row.content} for row in selected], ensure_ascii=False,
                            separators=(',', ':'))
    assert len(serialized.encode('utf-8')) <= 16000
    assert '\ufffd' not in selected[0].content


def test_only_referenced_history_sources_enter_catalogue_and_original_indices_stay_valid():
    original = [{'source_type': 'research_workspace', 'entity_id': str(i)} for i in range(80)]
    selected = select_chat_history([{'role': 'assistant', 'content': 'Supported.[cite:76] Missing.[cite:900]',
                                    'citations': original}])
    citations = history_citations(selected)
    assert citations == [original[75]]
    assert len(selected[0].citations) == 80
    assert rebase_history_markers(selected[0].content, selected[0].citations, citations) == (
        'Supported.[cite:1] Missing.[unverified prior citation 900]')
    assert history_citations(select_chat_history([{'role': 'assistant', 'content': 'No markers.',
                                                  'citations': original}])) == []


def test_history_source_selection_uses_deduped_original_indices_like_rebasing():
    first, second = {'entity_id': 'a'}, {'entity_id': 'b'}
    selected = select_chat_history([{'role': 'assistant', 'content': 'Second.[cite:2]',
                                    'citations': [first, first, second]}])
    assert history_citations(selected) == [second]


def test_compaction_preserves_order_identities_and_explicit_preview_without_changing_source():
    items = [{'id': str(i), 'kind': 'research_brief', 'label': f'Source {i}',
              'data': {'content': '研究结果含完整证据' * 10000, 'status': 'pending_review'}} for i in range(12)]
    source = json.dumps({'overview': {'counts': {'briefs': 12}}, 'retrieved_items': items,
                         'coverage': {'retrieved': 12}}, ensure_ascii=False)
    compact = compact_research_context(source)
    result = json.loads(compact)
    assert len(compact.encode('utf-8')) <= 24000
    assert result['overview'] == {'counts': {'briefs': 12}}
    assert [(item['id'], item['kind'], item['label']) for item in result['retrieved_items']] == [
        (item['id'], item['kind'], item['label']) for item in items]
    assert all(item['data']['truncated'] for item in result['retrieved_items'])
    assert 'get_research_items' in result['context_compaction']['instruction']
    assert 'pending_review' in source


def test_small_context_is_unchanged_and_large_overview_is_bounded():
    source = '{"overview":{"counts":{}},"retrieved_items":[]}'
    assert compact_research_context(source) == source
    compact = compact_research_context(json.dumps({'overview': {'content': 'x' * 100000}, 'retrieved_items': []}))
    assert len(compact.encode('utf-8')) <= 24000
    assert json.loads(compact)['overview']['truncated']


def test_identity_overflow_fails_closed_without_dropping_or_renumbering_sources():
    source = json.dumps({'retrieved_items': [{'id': 'x' * 25000, 'kind': 'document', 'label': 'Original'}]})
    with pytest.raises(ValueError, match='identity_budget_exceeded'):
        compact_research_context(source)
