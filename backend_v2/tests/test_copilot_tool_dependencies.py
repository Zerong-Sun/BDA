"""A scene cannot be derived from receipts the model has not observed yet."""
import json

import pytest
from backend_v2.app.copilot import agent_loop, agent_runs
from backend_v2.tests.test_copilot_agent_loop import (
    _call,
    _project,
    _provider,
    _run,
    _script,
    session,  # noqa: F401 - shared database fixture
)


@pytest.mark.parametrize("source", [
    "analyse_structure", "list_structure_contacts", "measure_structure_interface", "describe_structure_site",
])
@pytest.mark.parametrize("scene_first", [False, True])
def test_measurement_batch_defers_scene_until_receipts_are_observed(session, monkeypatch, source, scene_first):  # noqa: F811
    project, user = _project(session)
    run = _run(session, project, user, allowed_tools=[source, "render_structure_view"])
    provider = _provider(session)
    executed = []

    def execute(name, context, arguments):
        executed.append((name, arguments))
        return {"residues": [{"chain": "A", "seq": 1}]} if name == source else {"scene_id": "saved"}

    monkeypatch.setattr(agent_loop.REGISTRY, "execute", execute)
    measurement = _call("measure", source, {})
    guessed_scene = _call("guess", "render_structure_view", {"residues": [{"chain": "A", "seq": 2}]})
    seen = _script(monkeypatch, [
        {"tool_calls": [guessed_scene, measurement] if scene_first else [measurement, guessed_scene]},
        {"tool_calls": [_call("correct", "render_structure_view", {"residues": [{"chain": "A", "seq": 1}]})]},
    ])
    agent_loop.step(session, run, provider)
    assert [name for name, _ in executed] == [source]
    refused = next(turn for turn in agent_runs.transcript(session, run)
                   if turn.role == "tool" and turn.tool_calls[0]["tool_call_id"] == "guess")
    receipt = json.loads(refused.content)
    assert receipt["error"] == "tool_results_not_yet_observed"
    assert receipt["wait_for"] == [source]

    # Only a subsequent provider request has observed the true measurement.
    agent_loop.step(session, run, provider)
    assert any(message.get("role") == "tool" and "tool_results_not_yet_observed" in message.get("content", "")
               for message in seen[1])
    assert executed == [(source, {}), ("render_structure_view", {"residues": [{"chain": "A", "seq": 1}]})]


def test_independent_read_and_explicit_scene_remain_callable_together(session, monkeypatch):  # noqa: F811
    project, user = _project(session)
    run = _run(session, project, user, allowed_tools=["list_proteins", "render_structure_view"])
    executed = []
    monkeypatch.setattr(agent_loop.REGISTRY, "execute", lambda name, context, arguments: executed.append(name) or {})
    _script(monkeypatch, [{"tool_calls": [
        _call("independent", "list_proteins", {}),
        _call("explicit", "render_structure_view", {"residues": [{"chain": "B", "seq": 9}]}),
    ]}])
    agent_loop.step(session, run, _provider(session))
    assert executed == ["list_proteins", "render_structure_view"]


def test_dependency_deferral_does_not_replace_authorization_failure(session, monkeypatch):  # noqa: F811
    project, user = _project(session)
    run = _run(session, project, user, allowed_tools=["list_structure_contacts"])
    monkeypatch.setattr(agent_loop.REGISTRY, "execute", lambda name, context, arguments: {})
    _script(monkeypatch, [{"tool_calls": [
        _call("measure", "list_structure_contacts", {}),
        _call("not-allowed", "render_structure_view", {}),
    ]}])
    agent_loop.step(session, run, _provider(session))
    receipt = json.loads(agent_runs.transcript(session, run)[-1].content)
    assert receipt["error"] == "tool_not_allowed_for_this_run"
