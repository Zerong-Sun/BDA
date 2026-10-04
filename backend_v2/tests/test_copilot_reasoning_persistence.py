"""Private thinking protocol state survives restarts without entering public output.

All provider replies are synthetic markers, never real inference or reasoning.
"""
from __future__ import annotations

import importlib
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from backend_v2.app.copilot import agent_loop, agent_runs, provider_selection, research_agent, tasks
from backend_v2.app.copilot.models import CopilotAgentRun, CopilotConfig, CopilotConversation, CopilotMessage
from backend_v2.app.copilot.project_context import ProjectContextService
from backend_v2.app.copilot.research_context import ResearchContextService
from backend_v2.app.copilot.schemas import AgentTurnResponse, MessageResponse
from backend_v2.tests.test_copilot_agent_tasks import _project
from backend_v2.tests.test_copilot_agent_tasks import wired as wired  # noqa: F401
from sqlalchemy import Column, Integer, MetaData, Table, Text, create_engine, inspect, select


@pytest.mark.parametrize("reasoning", [None, "", "synthetic-protocol-marker\n  retained  "])
@pytest.mark.parametrize("with_tool_call", [False, True])
def test_durable_turn_roundtrip_and_public_schema_exclusion(wired, reasoning, with_tool_call):
    factory, _ = wired
    with factory() as session:
        project_id, user_id = _project(session)
        run = agent_runs.create_run(session, project_id=project_id, user_id=user_id, goal="test", allowed_tools=[])
        calls = [{"id": "synthetic-call", "type": "function", "function": {"name": "test_read", "arguments": "{}"}}] if with_tool_call else []
        agent_runs.append_turn(session, run, role="assistant", content="public answer", reasoning_content=reasoning, tool_calls=calls)
        if with_tool_call:
            agent_runs.append_turn(session, run, role="tool", content='{"count":1}',
                                   tool_calls=[{"tool_call_id": "synthetic-call", "name": "test_read"}])
        session.commit()
        run_id = run.id
    with factory() as session:
        run = session.get(CopilotAgentRun, run_id)
        turns = agent_runs.transcript(session, run)
        turn = turns[0]
        assert turn.reasoning_content == reasoning
        assert "reasoning_content" not in AgentTurnResponse.model_validate(turn).model_dump()
        assert turn.tool_calls == calls
        history = agent_loop.messages_for(run, turns)
        assistant = [item for item in history if item["role"] == "assistant"][0]
        if reasoning is None:
            assert "reasoning_content" not in assistant
        else:
            assert assistant["reasoning_content"] == reasoning
        assert "reasoning_content" not in str(turn.tool_calls)


def _conversation(factory):
    with factory() as session:
        project_id, user_id = _project(session)
        conversation = CopilotConversation(project_id=project_id, created_by=user_id)
        session.add(conversation)
        session.add(CopilotConfig(project_id=project_id, enabled_skills=[]))
        session.flush()
        source = CopilotMessage(conversation_id=conversation.id, role="user", content="first", status="pending")
        session.add(source)
        session.commit()
        return conversation.id, source.id


@pytest.mark.parametrize("mode", ["plain", "null", "empty", "review", "grounded", "repair"])
def test_chat_replays_final_response_reasoning_after_new_worker_session(wired, monkeypatch, mode):
    factory, _ = wired
    conversation_id, source_id = _conversation(factory)
    citations = ([{"source_type": "scientific_literature", "chunk_id": "synthetic-chunk",
                   "content_checksum_sha256": "synthetic-checksum", "retrieval_trace_id": "synthetic-trace"}]
                 if mode in {"grounded", "repair"} else [])
    monkeypatch.setattr(provider_selection, "select_provider", lambda *_, **__: SimpleNamespace(enabled=True))
    monkeypatch.setattr(ResearchContextService, "build_context", lambda *_, **__: SimpleNamespace(
        citations=citations, context="synthetic evidence", tool_calls=[]))
    monkeypatch.setattr(ResearchContextService, "research_overview", lambda *_: {
        "available_kinds": ["project"] if mode == "review" else ["research_target"]})
    monkeypatch.setattr(ResearchContextService, "grounding_packet", lambda *_: "synthetic evidence")
    monkeypatch.setattr(ProjectContextService, "overview_packet", lambda *_: "synthetic overview")
    monkeypatch.setattr(research_agent, "grounded_answer_issues", lambda value: ["synthetic issue"] if value == "repair needed" else [])

    final_marker = None if mode == "null" else "" if mode == "empty" else "synthetic-final-marker\n  exact  "
    draft = "D" * 1600 if mode in {"grounded", "repair"} else "D" * 900 if mode == "review" else "public first answer"
    first = {"content": draft}
    if mode != "null":
        first["reasoning_content"] = "synthetic-draft-marker" if mode in {"review", "grounded", "repair"} else final_marker
    replies = [first]
    if mode in {"review", "grounded", "repair"}:
        replies.append({"content": "repair needed" if mode == "repair" else "public revised answer",
                        "reasoning_content": "synthetic-reviewed-marker" if mode == "repair" else final_marker})
    if mode == "repair":
        replies.append({"content": "public repaired answer", "reasoning_content": final_marker})
    replies.append({"content": "public second answer"})
    requests = []
    def complete(provider, messages, **kwargs):
        requests.append(deepcopy(messages))
        return replies.pop(0)
    monkeypatch.setattr(research_agent, "completion_message", complete)

    tasks.copilot_respond.run(str(source_id))
    with factory() as session:
        assistant = session.scalars(select(CopilotMessage).where(
            CopilotMessage.conversation_id == conversation_id, CopilotMessage.role == "assistant")).one()
        assert assistant.status == "completed", assistant.error
        assert assistant.reasoning_content == final_marker
        assert "reasoning_content" not in MessageResponse.model_validate(assistant).model_dump()
        assert "reasoning_content" not in assistant.context
        public_first_answer = assistant.content
        next_source = CopilotMessage(conversation_id=conversation_id, role="user", content="second", status="pending")
        session.add(next_source)
        session.commit()
        next_id = next_source.id
    tasks.copilot_respond.run(str(next_id))
    previous = [item for item in requests[-1] if item["role"] == "assistant"]
    assert len(previous) == 1
    assert previous[0]["content"] == public_first_answer
    if final_marker is None:
        assert "reasoning_content" not in previous[0]
    else:
        assert previous[0]["reasoning_content"] == final_marker
    assert not replies


def test_chat_followup_rebases_history_without_rewriting_saved_answer(wired, monkeypatch):
    factory, _ = wired
    conversation_id, source_id = _conversation(factory)
    source_a = {
        "source_type": "scientific_literature", "workspace_type": "literature_evidence",
        "entity_id": "synthetic-source-a", "label": "Source A", "chunk_id": "synthetic-chunk-a",
        "content_checksum_sha256": "synthetic-snapshot-a", "retrieval_trace_id": "synthetic-trace-a",
        "excerpt": "Synthetic historical evidence A.",
    }
    source_b = {
        **source_a, "entity_id": "synthetic-source-b", "label": "Source B", "chunk_id": "synthetic-chunk-b",
        "content_checksum_sha256": "synthetic-snapshot-b", "retrieval_trace_id": "synthetic-trace-b",
        "excerpt": "Synthetic newly retrieved evidence B.",
    }
    prior_answer = "Historical claim from source A [cite:1]."
    with factory() as session:
        session.get(CopilotMessage, source_id).status = "completed"
        previous = CopilotMessage(
            conversation_id=conversation_id, role="assistant", status="completed",
            content=prior_answer, citations=[source_a],
        )
        session.add(previous)
        session.flush()
        previous_id, previous_version = previous.id, previous.version
        followup = CopilotMessage(
            conversation_id=conversation_id, role="user", status="pending",
            content="Revise the previous answer using the newly retrieved source B.",
        )
        session.add(followup)
        session.commit()
        followup_id = followup.id

    monkeypatch.setattr(provider_selection, "select_provider", lambda *_, **__: SimpleNamespace(enabled=True))
    monkeypatch.setattr(ResearchContextService, "build_context", lambda *_, **__: SimpleNamespace(
        citations=[source_b], context="Synthetic newly retrieved evidence B.", tool_calls=[]))
    monkeypatch.setattr(ResearchContextService, "research_overview", lambda *_: {"available_kinds": ["research_target"]})
    monkeypatch.setattr(ProjectContextService, "overview_packet", lambda *_: "Synthetic project context")
    requests = []

    def complete(provider, messages, **kwargs):
        requests.append(deepcopy(messages))
        return {"content": "New claim from B [cite:1]. Historical claim from A [cite:2]."}

    monkeypatch.setattr(research_agent, "completion_message", complete)
    assert tasks.copilot_respond.run(str(followup_id))["status"] == "completed"
    assert len(requests) == 1
    previous_sent = [message for message in requests[0] if message["role"] == "assistant"]
    assert [message["content"] for message in previous_sent] == [
        "Historical claim from source A [cite:2]."
    ]
    catalogue_prompt = next(message["content"] for message in requests[0]
                            if message["role"] == "system" and message["content"].startswith("CITATION_PLACEMENT_V1."))
    catalogue = json.loads(catalogue_prompt.split("Catalogue: ", 1)[1])
    assert [(entry["marker"], entry["entity_id"]) for entry in catalogue] == [
        ("[cite:1]", source_b["entity_id"]), ("[cite:2]", source_a["entity_id"]),
    ]
    with factory() as session:
        previous = session.get(CopilotMessage, previous_id)
        assert (previous.content, previous.citations, previous.version) == (prior_answer, [source_a], previous_version)
        response = session.scalars(select(CopilotMessage).where(
            CopilotMessage.conversation_id == conversation_id, CopilotMessage.role == "assistant",
            CopilotMessage.id != previous_id,
        )).one()
        assert response.status == "completed", response.error
        assert response.citations == [source_b, source_a]
        assert response.content == "New claim from B [cite:1]. Historical claim from A [cite:2]."
        assert session.get(CopilotMessage, followup_id).status == "completed"


@pytest.mark.parametrize("reasoning", [None, "", "synthetic-tool-marker\n  exact  "])
def test_tool_protocol_replays_only_provider_supplied_reasoning(monkeypatch, reasoning):
    call = {"id": "synthetic-call", "type": "function", "function": {"name": "test_read", "arguments": "{}"}}
    first = {"content": None, "tool_calls": [call]}
    if reasoning is not None:
        first["reasoning_content"] = reasoning
    replies = [first, {"content": "public final", "reasoning_content": "synthetic-final"}]
    requests = []
    def complete(provider, messages, **kwargs):
        requests.append(deepcopy(messages))
        return replies.pop(0)
    monkeypatch.setattr(research_agent, "completion_message", complete)
    monkeypatch.setattr(research_agent, "chat_schemas", lambda **_: [{"type": "function", "function": {"name": "test_read"}}])
    monkeypatch.setattr(research_agent, "_execute", lambda *_, **__: ({"count": 1}, []))
    result = research_agent.complete_research_turn(SimpleNamespace(), [{"role": "user", "content": "read"}],
        SimpleNamespace(), initial_citations=[], initial_tool_calls=[])
    assistant = [item for item in requests[-1] if item["role"] == "assistant"][0]
    assert assistant["tool_calls"] == [call]
    if reasoning is None:
        assert "reasoning_content" not in assistant
    else:
        assert assistant["reasoning_content"] == reasoning
    assert result.reasoning_content == "synthetic-final"
    assert "synthetic-final" not in repr(result)
    assert "reasoning_content" not in str(result.tool_calls)


def test_reasoning_migration_preserves_legacy_rows_and_reverses():
    migration = importlib.import_module("backend_v2.alembic.versions.0071_copilot_reasoning_content")
    engine = create_engine("sqlite+pysqlite://")
    metadata = MetaData()
    tables = [Table(name, metadata, Column("id", Integer, primary_key=True), Column("content", Text))
              for name in ("copilot_agent_turns", "copilot_messages")]
    with engine.begin() as connection:
        metadata.create_all(connection)
        for table in tables:
            connection.execute(table.insert().values(id=1, content="legacy public content"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            for table in tables:
                columns = {column["name"]: column for column in inspect(connection).get_columns(table.name)}
                assert columns["reasoning_content"]["nullable"] is True
                assert isinstance(columns["reasoning_content"]["type"], Text)
                reflected = Table(table.name, MetaData(), autoload_with=connection)
                row = connection.execute(select(reflected)).one()
                assert row.reasoning_content is None
                assert row.content == "legacy public content"
            migration.downgrade()
            for table in tables:
                assert {column["name"] for column in inspect(connection).get_columns(table.name)} == {"id", "content"}
                assert connection.execute(select(table.c.content)).scalar_one() == "legacy public content"
    engine.dispose()


@pytest.mark.parametrize("content", ["public forced final", ""])
def test_tool_limit_retains_only_reasoning_belonging_to_actual_final(monkeypatch, content):
    replies = iter([
        {"content": None, "tool_calls": [{"id": "unused-call"}], "reasoning_content": "synthetic-unused"},
        {"content": content, "reasoning_content": "synthetic-forced-final"},
    ])
    monkeypatch.setattr(research_agent, "completion_message", lambda *_, **__: next(replies))
    result = research_agent.complete_research_turn(SimpleNamespace(), [{"role": "user", "content": "read"}],
        SimpleNamespace(), initial_citations=[], initial_tool_calls=[], max_tool_calls=0)
    assert result.limit_reached is True
    assert result.reasoning_content == ("synthetic-forced-final" if content else None)
