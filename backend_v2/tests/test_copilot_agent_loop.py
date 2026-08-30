"""The agent loop running on the durable substrate.

`test_copilot_agent_runs.py` pins the substrate — suspend, resume, budget,
cancel. This pins the loop that sits on it, and the property that matters is the
one the tables were built for: a run that stops mid-way loses nothing. Every test
here drives the loop with a scripted provider and then reloads the run from rows,
because "resuming is reloading rows" is only true if nothing else is carried.
"""

from __future__ import annotations

import itertools
import json
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.copilot import agent_loop, agent_runs
from backend_v2.app.copilot.models import CopilotAgentRun, CopilotAgentTask
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.registry.models import LLMProvider
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def session() -> Iterator[Session]:
    engine = enforce_foreign_keys(
        create_engine(
            "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    )
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as opened:
        yield opened
    drop_all(engine, Base.metadata)


_counter = itertools.count()


def _project(session: Session) -> tuple[Project, User]:
    n = next(_counter)
    user = User(username=f"loop-{n}", display_name="L", role="editor", enabled=True)
    organization = Organization(name=f"Loop Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id,
        owner_id=user.id,
        name=f"loop-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project, user


def _provider(session: Session) -> LLMProvider:
    provider = LLMProvider(
        name=f"scripted-{next(_counter)}",
        provider_type="openai_compatible",
        endpoint="https://example.invalid/v1",
        model="scripted",
        credential_ref="env:UNUSED",
        enabled=True,
    )
    session.add(provider)
    session.flush()
    return provider


def _run(session: Session, project: Project, user: User, **kwargs: Any) -> CopilotAgentRun:
    return agent_runs.create_run(
        session,
        project_id=project.id,
        user_id=user.id,
        goal=kwargs.pop("goal", "find a binder"),
        allowed_tools=kwargs.pop(
            "allowed_tools", ["list_proteins", "await_compute_job", "spawn_subagent"]
        ),
        **kwargs,
    )


def _script(monkeypatch: pytest.MonkeyPatch, messages: list[dict[str, Any]]) -> list[list[dict]]:
    """Replace the provider call with a fixed sequence, recording what it saw."""
    seen: list[list[dict]] = []
    replies = iter(messages)

    def fake(provider: LLMProvider, conversation: list[dict], *, tools: Any = None) -> dict:
        seen.append(conversation)
        return next(replies)

    monkeypatch.setattr(agent_loop, "completion_message", fake)
    return seen


def _call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def _job(session: Session, project: Project, user: User, status: str = "running"):
    from backend_v2.app.compute.models import Job, JobSubmission
    from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun

    workflow = WorkflowRun(project_id=project.id, created_by=user.id, name="wf", graph={})
    session.add(workflow)
    session.flush()
    node = WorkflowNode(
        workflow_run_id=workflow.id,
        node_key="n1",
        node_type="demo",
        model_plugin="demo",
        parameters={},
    )
    submission = JobSubmission(
        workflow_run_id=workflow.id,
        project_id=project.id,
        created_by=user.id,
        compute_backend="demo",
    )
    session.add_all([node, submission])
    session.flush()
    job = Job(
        submission_id=submission.id,
        workflow_run_id=workflow.id,
        workflow_node_id=node.id,
        project_id=project.id,
        status=status,
        compute_backend="demo",
        model_plugin="demo",
        runtime_spec={},
    )
    session.add(job)
    session.flush()
    return job


# --- Answering ---------------------------------------------------------------


def test_a_run_that_answers_finishes_and_keeps_its_answer(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, user = _project(session)
    run = _run(session, project, user)
    _script(monkeypatch, [{"content": "Three candidates look worth testing."}])

    agent_loop.drive(session, run, _provider(session))

    assert run.status == "succeeded"
    transcript = agent_runs.transcript(session, run)
    assert [turn.role for turn in transcript] == ["assistant"]
    assert transcript[0].content == "Three candidates look worth testing."


def test_the_conversation_is_rebuilt_from_rows_and_nothing_else(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The claim the tables exist for: reloading rows is the whole of resuming."""
    project, user = _project(session)
    run = _run(session, project, user, goal="quantify the eluate")
    agent_runs.append_turn(session, run, role="assistant", content="I checked the library.")
    agent_runs.append_turn(
        session,
        run,
        role="tool",
        content='{"count": 2}',
        tool_calls=[{"tool_call_id": "call_a", "name": "list_proteins"}],
    )

    conversation = agent_loop.messages_for(run, agent_runs.transcript(session, run))

    assert conversation[0]["role"] == "system"
    assert conversation[1] == {"role": "user", "content": "quantify the eluate"}
    assert conversation[2]["content"] == "I checked the library."
    assert conversation[3] == {
        "role": "tool",
        "tool_call_id": "call_a",
        "name": "list_proteins",
        "content": '{"count": 2}',
    }


def test_a_tool_result_is_persisted_before_the_next_provider_call(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, user = _project(session)
    run = _run(session, project, user, allowed_tools=["list_proteins"])
    seen = _script(
        monkeypatch,
        [
            {"content": "", "tool_calls": [_call("call_1", "list_proteins", {"limit": 5})]},
            {"content": "The library is empty."},
        ],
    )

    agent_loop.drive(session, run, _provider(session))

    roles = [turn.role for turn in agent_runs.transcript(session, run)]
    assert roles == ["assistant", "tool", "assistant"]
    # The second call saw the tool result, which means it came back out of a row.
    assert seen[1][-1]["role"] == "tool"
    assert run.status == "succeeded"


# --- Suspending --------------------------------------------------------------


def test_awaiting_a_running_job_suspends_the_run_rather_than_blocking(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, user = _project(session)
    job = _job(session, project, user, status="running")
    run = _run(session, project, user)
    _script(
        monkeypatch,
        [{"content": "", "tool_calls": [_call("call_1", "await_compute_job", {"job_id": str(job.id)})]}],
    )

    agent_loop.drive(session, run, _provider(session))

    assert run.status == "awaiting_tasks"
    task = agent_runs.outstanding_tasks(session, run)[0]
    assert (task.kind, task.resource_id, task.tool_call_id) == ("gpu_job", job.id, "call_1")
    # No tool turn yet: the result is written when the wait settles, so the
    # transcript stays in the order the model will read it.
    assert [turn.role for turn in agent_runs.transcript(session, run)] == ["assistant"]


def test_awaiting_a_job_that_already_finished_does_not_park_the_run(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A task nothing will settle is a run that never wakes."""
    project, user = _project(session)
    job = _job(session, project, user, status="succeeded")
    run = _run(session, project, user)
    _script(
        monkeypatch,
        [
            {"content": "", "tool_calls": [_call("call_1", "await_compute_job", {"job_id": str(job.id)})]},
            {"content": "The job had already succeeded."},
        ],
    )

    agent_loop.drive(session, run, _provider(session))

    assert run.status == "succeeded"
    assert agent_runs.outstanding_tasks(session, run) == []


def test_a_settled_job_comes_back_as_the_tool_result_it_answers(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, user = _project(session)
    job = _job(session, project, user, status="running")
    run = _run(session, project, user)
    _script(
        monkeypatch,
        [
            {"content": "", "tool_calls": [_call("call_1", "await_compute_job", {"job_id": str(job.id)})]},
            {"content": "The job produced two artifacts."},
        ],
    )
    agent_loop.drive(session, run, _provider(session))
    assert run.status == "awaiting_tasks"

    agent_loop.settle_job_waits(session, job.id, "succeeded", {"job_status": "succeeded"})
    assert agent_runs.resume(session, run) is True
    agent_loop.drive(session, run, _provider(session))

    tool_turns = [turn for turn in agent_runs.transcript(session, run) if turn.role == "tool"]
    assert len(tool_turns) == 1
    assert tool_turns[0].tool_calls[0] == {"tool_call_id": "call_1", "name": "await_compute_job"}
    assert json.loads(tool_turns[0].content)["status"] == "succeeded"
    assert run.status == "succeeded"


def test_a_failed_job_is_folded_in_as_information_not_as_a_failed_run(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An agent that cannot see a failure repeats the run that caused it."""
    project, user = _project(session)
    job = _job(session, project, user, status="running")
    run = _run(session, project, user)
    _script(
        monkeypatch,
        [
            {"content": "", "tool_calls": [_call("call_1", "await_compute_job", {"job_id": str(job.id)})]},
            {"content": "The job failed on the node; I did not resubmit it."},
        ],
    )
    agent_loop.drive(session, run, _provider(session))

    agent_loop.settle_job_waits(session, job.id, "failed", {"error_code": "compute_failed"})
    agent_runs.resume(session, run)
    agent_loop.drive(session, run, _provider(session))

    folded = json.loads(
        [turn for turn in agent_runs.transcript(session, run) if turn.role == "tool"][0].content
    )
    assert folded["status"] == "failed"
    assert folded["error_code"] == "compute_failed"
    assert run.status == "succeeded"


def test_folding_a_settled_task_twice_adds_nothing(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wake-ups are redelivered; the transcript must not grow each time."""
    project, user = _project(session)
    job = _job(session, project, user, status="running")
    run = _run(session, project, user)
    _script(
        monkeypatch,
        [{"content": "", "tool_calls": [_call("call_1", "await_compute_job", {"job_id": str(job.id)})]}],
    )
    agent_loop.drive(session, run, _provider(session))
    agent_loop.settle_job_waits(session, job.id, "succeeded", {})

    assert agent_loop.fold_settled_tasks(session, run) == 1
    assert agent_loop.fold_settled_tasks(session, run) == 0


# --- Subagents ---------------------------------------------------------------


def test_spawning_a_subagent_suspends_the_parent_on_the_child(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, user = _project(session)
    parent = _run(session, project, user)
    _script(
        monkeypatch,
        [{"content": "", "tool_calls": [_call("call_1", "spawn_subagent", {"goal": "screen the library"})]}],
    )

    agent_loop.drive(session, parent, _provider(session))

    assert parent.status == "awaiting_tasks"
    child = session.scalar(select(CopilotAgentRun).where(CopilotAgentRun.parent_run_id == parent.id))
    assert child is not None and child.goal == "screen the library"
    assert agent_runs.outstanding_tasks(session, parent)[0].resource_id == child.id


def test_a_finished_child_settles_the_parents_wait_with_its_answer(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, user = _project(session)
    parent = _run(session, project, user)
    _script(
        monkeypatch,
        [
            {"content": "", "tool_calls": [_call("call_1", "spawn_subagent", {"goal": "screen"})]},
            {"content": "Screened; two hits."},
        ],
    )
    agent_loop.drive(session, parent, _provider(session))
    child = session.scalar(select(CopilotAgentRun).where(CopilotAgentRun.parent_run_id == parent.id))
    assert child is not None

    agent_loop.drive(session, child, _provider(session))

    assert child.status == "succeeded"
    task = session.scalar(select(CopilotAgentTask).where(CopilotAgentTask.run_id == parent.id))
    assert task is not None
    assert task.status == "succeeded"
    assert task.result["answer"] == "Screened; two hits."


# --- Refusals and budget -----------------------------------------------------


def test_a_tool_outside_the_runs_vocabulary_is_refused_without_ending_the_run(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The run may be most of the way to its goal; a bad call is a fact to correct."""
    project, user = _project(session)
    run = _run(session, project, user, allowed_tools=["list_proteins"])
    _script(
        monkeypatch,
        [
            {"content": "", "tool_calls": [_call("call_1", "create_compute_draft", {"name": "x"})]},
            {"content": "I cannot draft compute in this run."},
        ],
    )

    agent_loop.drive(session, run, _provider(session))

    refusal = [turn for turn in agent_runs.transcript(session, run) if turn.role == "tool"][0]
    assert json.loads(refusal.content)["error"] == "tool_not_allowed_for_this_run"
    assert run.status == "succeeded"


def test_the_budget_stops_the_run_before_the_call_it_could_not_afford(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, user = _project(session)
    run = _run(session, project, user, allowed_tools=["list_proteins"], max_turns=2)
    calls: list[int] = []

    def fake(provider: LLMProvider, conversation: list[dict], *, tools: Any = None) -> dict:
        calls.append(1)
        return {"content": "", "tool_calls": [_call(f"c{len(calls)}", "list_proteins", {})]}

    monkeypatch.setattr(agent_loop, "completion_message", fake)

    agent_loop.drive(session, run, _provider(session))

    assert run.status == "failed"
    assert run.error is not None and "turn limit" in run.error
    # One provider call spent two turns (assistant + tool); the second was never made.
    assert len(calls) == 1


def test_a_run_only_offers_the_model_the_tools_it_may_use(session: Session) -> None:
    project, user = _project(session)
    run = _run(session, project, user, allowed_tools=["list_proteins"])
    names = {schema["function"]["name"] for schema in agent_loop._schemas(run)}
    assert names == {"list_proteins"}


def test_the_waiting_tools_are_unreachable_without_a_run() -> None:
    """`requires="agent_run"` is what keeps a chat turn from calling them: chat has
    no run, so there is nothing to suspend."""
    from backend_v2.app.copilot.registry import REGISTRY

    assert REGISTRY.get("await_compute_job").requires == "agent_run"
    assert REGISTRY.get("spawn_subagent").requires == "agent_run"
    assert REGISTRY.get("await_compute_job").awaits == "gpu_job"
    assert REGISTRY.get("spawn_subagent").awaits == "subagent"


def test_settling_a_job_touches_only_the_runs_waiting_on_it(session: Session) -> None:
    project, user = _project(session)
    waiting = _run(session, project, user)
    other = _run(session, project, user)
    job_id, other_job = uuid.uuid4(), uuid.uuid4()
    agent_runs.suspend(session, waiting, [("gpu_job", job_id, "call_1")])
    agent_runs.suspend(session, other, [("gpu_job", other_job, "call_1")])

    touched = agent_loop.settle_job_waits(session, job_id, "succeeded", {})

    assert touched == [waiting.id]
    assert agent_runs.outstanding_tasks(session, other) != []


def test_a_queued_tool_suspends_the_run_instead_of_reporting_it_and_stopping(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same tool is ordinary in chat and awaitable in a run.

    Chat has no run to suspend and never reads `awaits`, so one declaration
    serves both; before it, an agent could start the work it had just asked for
    and then had nothing to do but say "queued".
    """
    from backend_v2.app.copilot.registry import REGISTRY

    project, user = _project(session)
    operation_id = uuid.uuid4()
    run = _run(session, project, user, allowed_tools=["start_literature_search"])

    monkeypatch.setattr(
        agent_loop,
        "_tool_context",
        lambda session, run: _FakeActions(operation_id).context(session, run),
    )
    _script(
        monkeypatch,
        [
            {
                "content": "",
                "tool_calls": [_call("call_1", "start_literature_search", {"query": "binder"})],
            }
        ],
    )

    agent_loop.drive(session, run, _provider(session))

    assert REGISTRY.get("start_literature_search").awaits == "operation"
    assert run.status == "awaiting_tasks"
    task = agent_runs.outstanding_tasks(session, run)[0]
    assert (task.kind, task.resource_id) == ("operation", operation_id)


class _FakeActions:
    """Just enough of the action service for the queue tool's single call."""

    def __init__(self, operation_id: uuid.UUID) -> None:
        self.operation_id = operation_id

    def start_literature_search(self, query: str, *, limit: int = 5) -> dict[str, Any]:
        return {
            "search_run_id": str(uuid.uuid4()),
            "status": "pending",
            "operation_id": str(self.operation_id),
            "resource_id": str(self.operation_id),
        }

    def context(self, session: Session, run: CopilotAgentRun):
        from backend_v2.app.copilot.registry import ToolContext

        return ToolContext(
            project_id=run.project_id,
            user_id=run.created_by,
            session=session,
            actions=self,
            agent_run=run,
        )
