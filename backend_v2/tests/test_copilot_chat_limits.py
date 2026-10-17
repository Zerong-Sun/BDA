"""A task cap stops model calls, not access to a conversation or its draft."""
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot import provider_selection, research_agent, tasks
from backend_v2.app.copilot.models import CopilotMessage
from backend_v2.app.copilot.project_context import ProjectContextService
from backend_v2.app.copilot.research_context import ResearchContextService
from backend_v2.app.core.problem import DomainError
from backend_v2.tests.test_copilot_agent_tasks import wired as wired
from backend_v2.tests.test_copilot_reasoning_persistence import _conversation
from sqlalchemy import select


@pytest.mark.parametrize('review_reached', [False, True])
def test_limit_retains_draft_only_when_answer_exists_and_next_message_is_allowed(wired, monkeypatch, review_reached):
    factory, _ = wired
    conversation_id, source_id = _conversation(factory)
    monkeypatch.setattr(provider_selection, 'select_provider', lambda *_, **__: SimpleNamespace(enabled=True))
    monkeypatch.setattr(ResearchContextService, 'build_context', lambda *_, **__: SimpleNamespace(
        citations=[], context='{"overview":{}}', tool_calls=[]))
    monkeypatch.setattr(ResearchContextService, 'research_overview', lambda *_: {'available_kinds': ['project']})
    monkeypatch.setattr(ProjectContextService, 'overview_packet', lambda *_: '{}')
    draft = 'A saved draft based on existing records. ' * 30

    def blocked(*_, **__):
        raise DomainError('llm_budget_exhausted', 'The task allowance cannot cover another request.', status_code=409)

    monkeypatch.setattr(research_agent, 'complete_research_turn',
        (lambda *_, **__: research_agent.ResearchAgentResult(draft, [], [])) if review_reached else blocked)
    monkeypatch.setattr(research_agent, 'review_scientific_answer_result', blocked)
    tasks.copilot_respond.run(str(source_id))
    with factory() as session:
        answer = session.scalars(select(CopilotMessage).where(
            CopilotMessage.conversation_id == conversation_id, CopilotMessage.role == 'assistant')).one()
        if review_reached:
            assert draft in answer.content
            assert 'has not passed final review' in answer.content
            assert answer.context['delivery_status'] == 'partial'
            assert answer.context['review_status'] == 'not_completed'
            assert answer.context['stop_reason'] == 'llm_budget_exhausted'
        else:
            assert answer.status == 'failed'
            assert answer.context['error_code'] == 'llm_budget_exhausted'
            assert draft not in answer.content
        next_source = CopilotMessage(conversation_id=conversation_id, role='user', content='A narrower new question', status='pending')
        session.add(next_source)
        session.commit()
        next_id = next_source.id
    monkeypatch.setattr(research_agent, 'complete_research_turn',
        lambda *_, **__: research_agent.ResearchAgentResult('New answer', [], []))
    tasks.copilot_respond.run(str(next_id))
    with factory() as session:
        assert session.get(CopilotMessage, next_id).status == 'completed'
        assert session.scalar(select(CopilotMessage).where(
            CopilotMessage.conversation_id == conversation_id, CopilotMessage.content == 'New answer')) is not None


def test_archived_messages_are_not_replayed_to_provider(wired, monkeypatch):
    factory, _ = wired
    conversation_id, source_id = _conversation(factory)
    with factory() as session:
        session.add_all([
            CopilotMessage(conversation_id=conversation_id, role='assistant', content='obsolete-marker',
                           status='completed', context={'chat_archive': {'archived': True}}),
            CopilotMessage(conversation_id=conversation_id, role='assistant', content='useful-marker', status='completed'),
        ])
        session.commit()
    monkeypatch.setattr(provider_selection, 'select_provider', lambda *_, **__: SimpleNamespace(enabled=True))
    monkeypatch.setattr(ResearchContextService, 'build_context', lambda *_, **__: SimpleNamespace(
        citations=[], context='{"overview":{}}', tool_calls=[]))
    monkeypatch.setattr(ResearchContextService, 'research_overview', lambda *_: {'available_kinds': ['project']})
    monkeypatch.setattr(ProjectContextService, 'overview_packet', lambda *_: '{}')
    captured = []

    def reply(provider, messages, *args, **kwargs):
        captured.extend(messages)
        return research_agent.ResearchAgentResult('New answer', [], [])

    monkeypatch.setattr(research_agent, 'complete_research_turn', reply)
    monkeypatch.setattr(research_agent, 'review_scientific_answer_result', lambda *_, **__: (_ for _ in ()).throw(
        DomainError('llm_budget_exhausted', 'test review stop', status_code=409)))
    tasks.copilot_respond.run(str(source_id))
    assert any(item['content'] == 'useful-marker' for item in captured)
    assert all('obsolete-marker' not in item['content'] for item in captured)
