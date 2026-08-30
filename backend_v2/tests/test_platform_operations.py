"""The operation lifecycle, and what it tells the rest of the platform.

An operation is how queued work becomes observable: one row per async action,
started by an outbox event and finished by a Celery signal. What it did *not*
do was say when it finished, so anything waiting on queued work had to poll —
the same gap compute had before `job.settled`, and with the same fix.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.compute.models import OutboxEvent
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.platform.models import Operation
from backend_v2.app.platform.operations import (
    enqueue_operation,
    finish_operation,
    mark_operation_running,
)
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_counter = itertools.count()


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


def _actors(session: Session) -> tuple[Project, User]:
    n = next(_counter)
    user = User(username=f"ops-{n}", display_name="O", role="editor", enabled=True)
    organization = Organization(name=f"Ops Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"ops-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project, user


def _queue(session: Session) -> Operation:
    project, user = _actors(session)
    return enqueue_operation(
        session,
        topic="literature.search",
        resource_type="literature_search_run",
        resource_id=uuid.uuid4(),
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
    )


def _settled(session: Session, operation: Operation) -> list[OutboxEvent]:
    return list(
        session.scalars(
            select(OutboxEvent).where(
                OutboxEvent.topic == "operation.settled",
                OutboxEvent.aggregate_id == operation.id,
            )
        )
    )


def test_finishing_an_operation_announces_it(session: Session) -> None:
    operation = _queue(session)
    assert _settled(session, operation) == []

    finish_operation(session, operation.id, result={"documents": 3})

    events = _settled(session, operation)
    assert len(events) == 1
    assert events[0].payload["status"] == "succeeded"
    assert events[0].payload["project_id"] == str(operation.project_id)
    assert events[0].payload["kind"] == "literature.search"


def test_queued_operation_carries_its_rls_scope(session: Session) -> None:
    operation = _queue(session)

    event = session.scalar(
        select(OutboxEvent).where(
            OutboxEvent.id == operation.id,
            OutboxEvent.topic == "literature.search",
        )
    )

    assert event is not None
    assert event.payload["project_id"] == str(operation.project_id)
    assert event.payload["organization_id"] == str(operation.organization_id)


def test_a_failed_operation_is_announced_the_same_way(session: Session) -> None:
    """Success-only announcement is what left every waiting consumer polling to
    discover failure — the exact gap `job.settled` closed in compute."""
    operation = _queue(session)

    finish_operation(session, operation.id, error=RuntimeError("europe pmc timed out"))

    events = _settled(session, operation)
    assert len(events) == 1
    assert events[0].payload["status"] == "failed"
    assert operation.error_code == "runtimeerror"


def test_starting_an_operation_announces_nothing(session: Session) -> None:
    """`running` is not terminal, and a wake-up on it would wake a run whose work
    has not happened yet."""
    operation = _queue(session)
    mark_operation_running(session, operation.id)
    assert _settled(session, operation) == []


def test_finishing_an_operation_that_is_gone_is_not_an_error(session: Session) -> None:
    """A redelivered signal for a purged operation must not fail the task."""
    finish_operation(session, uuid.uuid4(), result={})
    assert list(session.scalars(select(OutboxEvent).where(OutboxEvent.topic == "operation.settled"))) == []
