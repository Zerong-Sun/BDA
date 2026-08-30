"""Durable agent runs: suspend, resume, budget, and the cancel cascade.

The behaviour worth pinning is what happens across the gap. A run that submits
a GPU job stops executing but stays alive; its transcript is its whole state, so
resuming is reloading rows. And a cancelled parent must not leave GPU jobs
running and subagents thinking — that is how a budget disappears without anyone
deciding to spend it.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.copilot import agent_runs
from backend_v2.app.copilot.models import CopilotAgentRun, CopilotAgentTask
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
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


def _project(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    n = next(_counter)
    user = User(username=f"agent-{n}", display_name="A", role="editor", enabled=True)
    organization = Organization(name=f"Agent Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"agent-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project.id, user.id


def _run(session: Session, **kwargs) -> CopilotAgentRun:
    project_id, user_id = kwargs.pop("ids", None) or _project(session)
    return agent_runs.create_run(
        session,
        project_id=project_id,
        user_id=user_id,
        goal=kwargs.pop("goal", "design a binder"),
        allowed_tools=kwargs.pop("allowed_tools", ["list_proteins", "compute_concentration"]),
        **kwargs,
    )


# --- The transcript is the state ---------------------------------------------


def test_turns_are_persisted_in_order_and_charged_to_the_run(session: Session) -> None:
    run = _run(session)
    agent_runs.append_turn(session, run, role="user", content="start", tokens_in=10)
    agent_runs.append_turn(session, run, role="assistant", content="thinking", cost_usd_cents=7)
    agent_runs.append_turn(session, run, role="assistant", content="done", cost_usd_cents=5)

    turns = agent_runs.transcript(session, run)
    assert [turn.sequence for turn in turns] == [0, 1, 2]
    assert [turn.content for turn in turns] == ["start", "thinking", "done"]
    assert run.turn_count == 3
    # Charged as it goes, so the budget can be checked before the next call
    # rather than after it has been paid for.
    assert run.cost_usd_cents == 12


def test_a_dead_process_leaves_a_readable_transcript(session: Session) -> None:
    """Written per turn, not at the end: a run that dies mid-way is exactly when
    the record is worth reading."""
    run = _run(session)
    agent_runs.append_turn(session, run, role="assistant", content="submitted the job")
    session.expire_all()

    reloaded = agent_runs.require_run(session, run.id)
    assert [turn.content for turn in agent_runs.transcript(session, reloaded)] == [
        "submitted the job"
    ]


# --- Suspend and resume ------------------------------------------------------


def test_suspending_parks_the_run_against_named_work(session: Session) -> None:
    run = _run(session)
    job_id = uuid.uuid4()

    tasks = agent_runs.suspend(session, run, [("gpu_job", job_id, "call_1")])

    assert run.status == "awaiting_tasks"
    assert len(tasks) == 1
    # The tool call id travels with the task, so a resumed turn puts each result
    # back where the model expects it rather than guessing from order.
    assert tasks[0].tool_call_id == "call_1"


def test_a_run_cannot_wait_on_nothing(session: Session) -> None:
    """It would never be woken; better to refuse than to sleep forever."""
    run = _run(session)
    with pytest.raises(DomainError) as raised:
        agent_runs.suspend(session, run, [])
    assert raised.value.error_code == "agent_suspend_without_tasks"


def test_suspending_twice_on_the_same_work_does_not_duplicate_the_wait(session: Session) -> None:
    run = _run(session)
    job_id = uuid.uuid4()
    agent_runs.suspend(session, run, [("gpu_job", job_id, "call_1")])
    agent_runs.suspend(session, run, [("gpu_job", job_id, "call_1")])
    assert len(agent_runs.outstanding_tasks(session, run)) == 1


def test_a_run_resumes_only_once_everything_it_waits_on_has_settled(session: Session) -> None:
    run = _run(session)
    first, second = uuid.uuid4(), uuid.uuid4()
    tasks = agent_runs.suspend(
        session, run, [("gpu_job", first, "c1"), ("gpu_job", second, "c2")]
    )

    agent_runs.settle_task(session, tasks[0], status="succeeded", result={"ok": True})
    assert agent_runs.resume(session, run) is False
    assert run.status == "awaiting_tasks"

    agent_runs.settle_task(session, tasks[1], status="succeeded")
    assert agent_runs.resume(session, run) is True
    assert run.status == "running"


def test_a_failed_task_wakes_the_run_rather_than_failing_it(session: Session) -> None:
    """A failed fold is information. An agent that cannot see it will repeat the
    run that produced it."""
    run = _run(session)
    tasks = agent_runs.suspend(session, run, [("gpu_job", uuid.uuid4(), "c1")])
    agent_runs.settle_task(session, tasks[0], status="failed", error="node died")

    assert agent_runs.resume(session, run) is True
    assert run.status == "running"


def test_the_poller_finds_runs_with_nothing_left_outstanding(session: Session) -> None:
    """The backstop query. Events now wake a settled run directly, so this
    should normally find nothing; it exists for the wake-ups no event carries."""
    ready = _run(session)
    waiting = _run(session)
    ready_tasks = agent_runs.suspend(session, ready, [("gpu_job", uuid.uuid4(), "c1")])
    agent_runs.suspend(session, waiting, [("gpu_job", uuid.uuid4(), "c1")])
    agent_runs.settle_task(session, ready_tasks[0], status="succeeded")

    resumable = agent_runs.resumable_runs(session)
    assert [run.id for run in resumable] == [ready.id]


# --- Budget ------------------------------------------------------------------


def test_the_turn_limit_stops_a_run_before_the_next_call(session: Session) -> None:
    run = _run(session, max_turns=2)
    agent_runs.append_turn(session, run, role="assistant")
    assert agent_runs.within_budget(session, run)[0] is True
    agent_runs.append_turn(session, run, role="assistant")
    allowed, why = agent_runs.within_budget(session, run)
    assert allowed is False
    assert "turn limit" in why


def test_the_cost_limit_stops_a_run_before_the_next_call(session: Session) -> None:
    run = _run(session, max_cost_usd_cents=100)
    agent_runs.append_turn(session, run, role="assistant", cost_usd_cents=99)
    assert agent_runs.within_budget(session, run)[0] is True
    agent_runs.append_turn(session, run, role="assistant", cost_usd_cents=2)
    allowed, why = agent_runs.within_budget(session, run)
    assert allowed is False
    assert "cost limit" in why


# --- Subagents ---------------------------------------------------------------


def test_a_subagent_cannot_reach_further_than_its_parent(session: Session) -> None:
    """Intersected rather than trusted: a child that could widen its own tool
    list would make the parent's restriction decorative."""
    ids = _project(session)
    parent = _run(session, ids=ids, allowed_tools=["list_proteins"])
    child = agent_runs.create_run(
        session,
        project_id=ids[0],
        user_id=ids[1],
        goal="sub",
        allowed_tools=["list_proteins", "create_compute_draft"],
        parent_run_id=parent.id,
    )
    assert child.allowed_tools == ["list_proteins"]


def test_subagents_do_not_nest_beyond_one_level(session: Session) -> None:
    """One level is enough to split work and shallow enough that cancel and
    budget checks terminate."""
    ids = _project(session)
    parent = _run(session, ids=ids)
    child = agent_runs.create_run(
        session, project_id=ids[0], user_id=ids[1], goal="sub",
        allowed_tools=["list_proteins"], parent_run_id=parent.id,
    )
    with pytest.raises(DomainError) as raised:
        agent_runs.create_run(
            session, project_id=ids[0], user_id=ids[1], goal="sub-sub",
            allowed_tools=["list_proteins"], parent_run_id=child.id,
        )
    assert raised.value.error_code == "agent_subagent_too_deep"


# --- Cancel cascades ---------------------------------------------------------


def test_cancelling_a_parent_cancels_its_children_and_their_waits(session: Session) -> None:
    """A cancelled parent leaving subagents thinking is how a budget disappears
    without anyone deciding to spend it."""
    ids = _project(session)
    parent = _run(session, ids=ids)
    child = agent_runs.create_run(
        session, project_id=ids[0], user_id=ids[1], goal="sub",
        allowed_tools=["list_proteins"], parent_run_id=parent.id,
    )
    agent_runs.suspend(session, child, [("gpu_job", uuid.uuid4(), "c1")])
    agent_runs.suspend(session, parent, [("subagent", child.id, "c0")])

    cancelled = agent_runs.cancel(session, parent, reason="user asked")

    assert cancelled == 2
    assert parent.status == "cancelled"
    assert child.status == "cancelled"
    assert agent_runs.outstanding_tasks(session, child) == []
    assert agent_runs.outstanding_tasks(session, parent) == []


def test_cancelling_reaches_a_child_the_parent_was_no_longer_waiting_on(
    session: Session,
) -> None:
    """The parent may have moved on while the child kept working; it is still
    the parent's to stop."""
    ids = _project(session)
    parent = _run(session, ids=ids)
    child = agent_runs.create_run(
        session, project_id=ids[0], user_id=ids[1], goal="sub",
        allowed_tools=["list_proteins"], parent_run_id=parent.id,
    )
    assert agent_runs.outstanding_tasks(session, parent) == []

    agent_runs.cancel(session, parent)
    assert child.status == "cancelled"


def test_cancelling_a_finished_run_changes_nothing(session: Session) -> None:
    run = _run(session)
    agent_runs.finish(session, run, status="succeeded")
    assert agent_runs.cancel(session, run) == 0
    assert run.status == "succeeded"


def test_a_run_finishes_as_succeeded_or_failed_only(session: Session) -> None:
    run = _run(session)
    with pytest.raises(DomainError) as raised:
        agent_runs.finish(session, run, status="cancelled")
    assert raised.value.error_code == "agent_bad_terminal_status"


def test_deleting_a_run_takes_its_transcript_and_waits(session: Session) -> None:
    run = _run(session)
    agent_runs.append_turn(session, run, role="assistant", content="x")
    agent_runs.suspend(session, run, [("gpu_job", uuid.uuid4(), "c1")])

    session.delete(run)
    session.flush()
    session.expire_all()

    assert session.scalar(select(CopilotAgentRun).where(CopilotAgentRun.id == run.id)) is None
    assert session.scalar(select(CopilotAgentTask).where(CopilotAgentTask.run_id == run.id)) is None


def test_the_cost_ceiling_covers_the_whole_run_tree(session: Session) -> None:
    """A per-run ceiling is no ceiling once a run can spawn children: five
    subagents each at the parent's limit spend six times the limit."""
    ids = _project(session)
    parent = _run(session, ids=ids, max_cost_usd_cents=100)
    child = agent_runs.create_run(
        session, project_id=ids[0], user_id=ids[1], goal="sub",
        allowed_tools=["list_proteins"], parent_run_id=parent.id,
    )
    agent_runs.append_turn(session, parent, role="assistant", cost_usd_cents=60)
    agent_runs.append_turn(session, child, role="assistant", cost_usd_cents=30)
    assert agent_runs.within_budget(session, parent)[0] is True
    assert agent_runs.within_budget(session, child)[0] is True

    agent_runs.append_turn(session, child, role="assistant", cost_usd_cents=20)

    # The child is what spent past the line, and both stop.
    for run in (parent, child):
        allowed, why = agent_runs.within_budget(session, run)
        assert allowed is False
        assert "cost limit" in why and "tree" in why


def test_a_child_is_charged_to_itself_and_counted_on_the_parent(session: Session) -> None:
    """Summed on read rather than reported upward: a child that mutated the
    parent's total would make its own row untrue, and that row is what a person
    reads when asking where the money went."""
    ids = _project(session)
    parent = _run(session, ids=ids)
    child = agent_runs.create_run(
        session, project_id=ids[0], user_id=ids[1], goal="sub",
        allowed_tools=["list_proteins"], parent_run_id=parent.id,
    )
    agent_runs.append_turn(session, parent, role="assistant", cost_usd_cents=7)
    agent_runs.append_turn(session, child, role="assistant", cost_usd_cents=5)

    assert parent.cost_usd_cents == 7
    assert child.cost_usd_cents == 5
    assert agent_runs.tree_cost_usd_cents(session, parent) == 12
    assert agent_runs.tree_cost_usd_cents(session, child) == 5


def test_the_turn_limit_stays_per_run(session: Session) -> None:
    """Turns measure one agent's reasoning. A parent that spent its allowance
    thinking should not thereby silence a subagent that has barely started."""
    ids = _project(session)
    parent = _run(session, ids=ids, max_turns=1)
    child = agent_runs.create_run(
        session, project_id=ids[0], user_id=ids[1], goal="sub",
        allowed_tools=["list_proteins"], parent_run_id=parent.id, max_turns=4,
    )
    agent_runs.append_turn(session, parent, role="assistant")

    assert agent_runs.within_budget(session, parent)[0] is False
    assert agent_runs.within_budget(session, child)[0] is True


def test_an_operation_is_something_a_run_can_wait_on(session: Session) -> None:
    """Queued work was the awkward case: an agent could start a literature
    search and then had nothing to do but report "queued" and stop."""
    run = _run(session)
    operation_id = uuid.uuid4()

    tasks = agent_runs.suspend(session, run, [("operation", operation_id, "call_1")])

    assert run.status == "awaiting_tasks"
    assert tasks[0].kind == "operation"
    assert tasks[0].resource_id == operation_id
