"""What wakes a suspended agent run.

The loop can suspend and resume (`test_copilot_agent_loop.py`); these are the
things that decide *when*. There are two, and the distinction is the point:

* the event — compute settles a job, and every run waiting on it is woken. This
  is now possible for failures too, which is why the poller stopped being the
  only correct mechanism.
* the sweep — the backstop, for a wake-up no event can carry.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.copilot import agent_runs
from backend_v2.app.copilot import tasks as copilot_tasks
from backend_v2.app.copilot.models import CopilotAgentRun, CopilotAgentTask
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_counter = itertools.count()


@pytest.fixture
def wired(monkeypatch) -> Iterator[tuple[sessionmaker, list[tuple[str, list]]]]:
    engine = enforce_foreign_keys(
        create_engine(
            "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    @contextmanager
    def scope():
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    sent: list[tuple[str, list]] = []
    monkeypatch.setattr(copilot_tasks, "session_scope", scope)
    monkeypatch.setattr(
        copilot_tasks.celery_app, "send_task", lambda name, **kwargs: sent.append((name, kwargs.get("args")))
    )
    yield factory, sent
    drop_all(engine, Base.metadata)


def _project(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    n = next(_counter)
    user = User(username=f"wake-{n}", display_name="W", role="editor", enabled=True)
    organization = Organization(name=f"Wake Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"wake-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project.id, user.id


def _job(session: Session, project_id: uuid.UUID, user_id: uuid.UUID, status: str):
    from backend_v2.app.compute.models import Job, JobSubmission
    from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun

    workflow = WorkflowRun(project_id=project_id, created_by=user_id, name="wf", graph={})
    session.add(workflow)
    session.flush()
    node = WorkflowNode(
        workflow_run_id=workflow.id, node_key="n", node_type="demo", model_plugin="demo", parameters={}
    )
    submission = JobSubmission(
        workflow_run_id=workflow.id, project_id=project_id, created_by=user_id, compute_backend="demo"
    )
    session.add_all([node, submission])
    session.flush()
    job = Job(
        submission_id=submission.id,
        workflow_run_id=workflow.id,
        workflow_node_id=node.id,
        project_id=project_id,
        status=status,
        compute_backend="demo",
        model_plugin="demo",
        runtime_spec={},
    )
    session.add(job)
    session.flush()
    return job


def _suspended_on(session: Session, job_id: uuid.UUID) -> CopilotAgentRun:
    project_id, user_id = _project(session)
    run = agent_runs.create_run(
        session,
        project_id=project_id,
        user_id=user_id,
        goal="wait for the fold",
        allowed_tools=["await_compute_job"],
    )
    agent_runs.suspend(session, run, [("gpu_job", job_id, "call_1")])
    return run


def test_a_failed_job_wakes_the_run_waiting_on_it(wired) -> None:
    """The whole reason compute now emits on every terminal state.

    While only success was published, this run would have slept until the sweep
    happened to look, which is polling wearing an event's clothes.
    """
    factory, sent = wired
    with factory() as session:
        project_id, user_id = _project(session)
        job = _job(session, project_id, user_id, "failed")
        job.error_code = "compute_failed"
        run = _suspended_on(session, job.id)
        session.commit()
        job_id, run_id = job.id, run.id

    result = copilot_tasks.copilot_agent_task_settled.run(str(job_id))

    assert result["woken"] == [str(run_id)]
    assert sent == [("bda_v2.copilot_agent_step", [str(run_id)])]
    with factory() as session:
        reloaded = session.get(CopilotAgentRun, run_id)
        assert reloaded is not None and reloaded.status == "running"
        task = agent_runs.transcript(session, reloaded)
        assert task == [], "the fold happens in the step, not in the wake-up"


def test_a_run_still_waiting_on_something_else_is_not_woken(wired) -> None:
    factory, sent = wired
    with factory() as session:
        project_id, user_id = _project(session)
        job = _job(session, project_id, user_id, "succeeded")
        run = _suspended_on(session, job.id)
        agent_runs.suspend(session, run, [("gpu_job", uuid.uuid4(), "call_2")])
        session.commit()
        job_id, run_id = job.id, run.id

    assert copilot_tasks.copilot_agent_task_settled.run(str(job_id))["woken"] == []
    assert sent == []
    with factory() as session:
        assert session.get(CopilotAgentRun, run_id).status == "awaiting_tasks"


def test_the_sweep_dispatches_only_runs_with_nothing_outstanding(wired) -> None:
    """The backstop. It should normally find nothing, and must not wake a run
    that is still legitimately waiting."""
    factory, sent = wired
    with factory() as session:
        project_id, user_id = _project(session)
        ready = agent_runs.create_run(
            session, project_id=project_id, user_id=user_id, goal="ready",
            allowed_tools=["list_proteins"],
        )
        blocked = agent_runs.create_run(
            session, project_id=project_id, user_id=user_id, goal="blocked",
            allowed_tools=["list_proteins"],
        )
        ready_tasks = agent_runs.suspend(session, ready, [("gpu_job", uuid.uuid4(), "c1")])
        agent_runs.suspend(session, blocked, [("gpu_job", uuid.uuid4(), "c1")])
        agent_runs.settle_task(session, ready_tasks[0], status="succeeded")
        session.commit()
        ready_id = ready.id

    assert copilot_tasks.copilot_agent_sweep.run()["dispatched"] == 1
    assert sent == [("bda_v2.copilot_agent_step", [str(ready_id)])]


def test_settling_a_job_no_run_waits_on_changes_nothing(wired) -> None:
    factory, sent = wired
    with factory() as session:
        project_id, user_id = _project(session)
        job = _job(session, project_id, user_id, "succeeded")
        session.commit()
        job_id = job.id

    assert copilot_tasks.copilot_agent_task_settled.run(str(job_id)) == {
        "job_id": str(job_id),
        "status": "succeeded",
        "woken": [],
    }
    assert sent == []


def test_a_step_on_a_run_without_a_provider_fails_the_run_rather_than_the_task(wired) -> None:
    """A worker that raises here would retry forever against a project that has
    no provider configured. The run carries the reason instead."""
    factory, sent = wired
    with factory() as session:
        project_id, user_id = _project(session)
        run = agent_runs.create_run(
            session, project_id=project_id, user_id=user_id, goal="go",
            allowed_tools=["list_proteins"],
        )
        session.commit()
        run_id = run.id

    assert copilot_tasks.copilot_agent_step.run(str(run_id))["status"] == "failed"
    with factory() as session:
        reloaded = session.get(CopilotAgentRun, run_id)
        assert reloaded is not None
        assert reloaded.error is not None and "provider" in reloaded.error


def test_stepping_a_cancelled_run_does_nothing(wired) -> None:
    factory, sent = wired
    with factory() as session:
        project_id, user_id = _project(session)
        run = agent_runs.create_run(
            session, project_id=project_id, user_id=user_id, goal="go",
            allowed_tools=["list_proteins"],
        )
        agent_runs.cancel(session, run)
        session.commit()
        run_id = run.id

    assert copilot_tasks.copilot_agent_step.run(str(run_id)) == {
        "run_id": str(run_id),
        "status": "cancelled",
    }


def test_a_run_still_thinking_when_the_worker_stops_is_handed_on(wired, monkeypatch) -> None:
    """`drive` bounds one worker's stay, not the run.

    A run left in `running` is invisible to the sweep, which reads
    `awaiting_tasks`; without the hand-off it would simply stop.
    """
    from backend_v2.app.copilot import agent_loop

    factory, sent = wired
    with factory() as session:
        project_id, user_id = _project(session)
        run = agent_runs.create_run(
            session, project_id=project_id, user_id=user_id, goal="long",
            allowed_tools=["list_proteins"],
        )
        session.commit()
        run_id = run.id

    monkeypatch.setattr(agent_loop, "provider_for", lambda session, run: object())
    monkeypatch.setattr(agent_loop, "drive", lambda session, run, provider, **_: run.status)

    assert copilot_tasks.copilot_agent_step.run(str(run_id))["status"] == "running"
    assert sent == [("bda_v2.copilot_agent_step", [str(run_id)])]


def _operation(session: Session, project_id: uuid.UUID, user_id: uuid.UUID, status: str):
    from backend_v2.app.platform.models import Operation

    operation = Operation(
        project_id=project_id,
        created_by=user_id,
        kind="literature.search",
        resource_type="literature_search_run",
        resource_id=uuid.uuid4(),
        status=status,
    )
    session.add(operation)
    session.flush()
    return operation


def test_a_settled_operation_wakes_the_run_that_queued_it(wired) -> None:
    """The awkward case before `operation` existed: an agent could start a
    literature search and then only report "queued"."""
    factory, sent = wired
    with factory() as session:
        project_id, user_id = _project(session)
        operation = _operation(session, project_id, user_id, "succeeded")
        run = agent_runs.create_run(
            session, project_id=project_id, user_id=user_id, goal="search",
            allowed_tools=["start_literature_search"],
        )
        agent_runs.suspend(session, run, [("operation", operation.id, "call_1")])
        session.commit()
        operation_id, run_id = operation.id, run.id

    result = copilot_tasks.copilot_agent_operation_settled.run(str(operation_id))

    assert result["woken"] == [str(run_id)]
    assert sent == [("bda_v2.copilot_agent_step", [str(run_id)])]
    with factory() as session:
        assert session.get(CopilotAgentRun, run_id).status == "running"


def test_a_failed_operation_wakes_the_run_too(wired) -> None:
    factory, sent = wired
    with factory() as session:
        project_id, user_id = _project(session)
        operation = _operation(session, project_id, user_id, "failed")
        operation.error_code = "runtimeerror"
        run = agent_runs.create_run(
            session, project_id=project_id, user_id=user_id, goal="search",
            allowed_tools=["start_literature_search"],
        )
        agent_runs.suspend(session, run, [("operation", operation.id, "call_1")])
        session.commit()
        operation_id, run_id = operation.id, run.id

    assert copilot_tasks.copilot_agent_operation_settled.run(str(operation_id))["woken"] == [
        str(run_id)
    ]
    with factory() as session:
        task = session.scalars(
            select(CopilotAgentTask).where(CopilotAgentTask.run_id == run_id)
        ).one()
        assert task.status == "failed"
        assert task.result["error_code"] == "runtimeerror"


def test_settling_an_operation_no_run_waits_on_changes_nothing(wired) -> None:
    factory, sent = wired
    with factory() as session:
        project_id, user_id = _project(session)
        operation = _operation(session, project_id, user_id, "succeeded")
        session.commit()
        operation_id = operation.id

    assert copilot_tasks.copilot_agent_operation_settled.run(str(operation_id))["woken"] == []
    assert sent == []
