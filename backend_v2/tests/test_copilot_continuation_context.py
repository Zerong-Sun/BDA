"""Continuation prompts omit old reasoning without changing durable evidence."""
import json

import pytest
from backend_v2.app.copilot import agent_loop, agent_runs
from backend_v2.tests.test_copilot_agent_loop import _call, _project, _run
from backend_v2.tests.test_copilot_agent_loop import session as session_fixture


@pytest.fixture(name="session")
def db_session():
    yield from session_fixture.__wrapped__()


@pytest.mark.parametrize("continuations", [0, 1, 2])
def test_only_pre_continuation_reasoning_is_omitted_and_storage_is_unchanged(session, continuations):
    project, user = _project(session)
    run = _run(session, project, user)
    for index in range(continuations + 1):
        if index:
            agent_runs.append_turn(session, run, role="user", content=f"Continue {index}, preserve original evidence.")
        agent_runs.append_turn(session, run, role="assistant", content=f"Recorded answer {index}",
                               reasoning_content=f"synthetic-private-{index}" * 2000)
        agent_runs.append_turn(session, run, role="assistant", tool_calls=[_call(f"read-{index}", "list_proteins", {})],
                               reasoning_content=f"synthetic-tool-protocol-{index}")
        agent_runs.append_turn(session, run, role="tool", content=json.dumps({"record": index, "value": "1 nM"}),
                               tool_calls=[{"name": "list_proteins", "tool_call_id": f"read-{index}"}])
    session.commit()
    turns = agent_runs.transcript(session, run)

    def snapshot(rows):
        return [(t.id, t.role, t.content, t.reasoning_content, json.dumps(t.tool_calls)) for t in rows]

    before = snapshot(turns)
    prompt = agent_loop.messages_for(run, turns)
    assistants = [message for message in prompt if message["role"] == "assistant"]
    for index in range(continuations + 1):
        answer, tool = assistants[index * 2:index * 2 + 2]
        assert answer["content"] == f"Recorded answer {index}"
        assert tool["tool_calls"] == [_call(f"read-{index}", "list_proteins", {})]
        if index < continuations:
            assert "reasoning_content" not in answer
            assert "reasoning_content" not in tool
        else:
            assert answer["reasoning_content"] == f"synthetic-private-{index}" * 2000
            assert tool["reasoning_content"] == f"synthetic-tool-protocol-{index}"
    assert [message["content"] for message in prompt if message["role"] == "tool"] == [
        json.dumps({"record": index, "value": "1 nM"}) for index in range(continuations + 1)]
    assert snapshot(turns) == before
    session.expire_all()
    assert snapshot(agent_runs.transcript(session, run)) == before
