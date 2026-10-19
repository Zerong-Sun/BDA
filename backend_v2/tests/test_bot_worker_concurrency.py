"""Offline regressions for redelivery racing operation signals and task contexts."""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Event
from types import SimpleNamespace

import pytest
from backend_v2.app.compute import tasks
from backend_v2.app.compute.models import OutboxEvent
from backend_v2.app.core import celery_app as worker
from backend_v2.app.core.config import get_settings
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.platform.models import Operation
from backend_v2.app.platform.operations import enqueue_operation, finish_operation, mark_operation_running
from backend_v2.app.projects.models import Project
from backend_v2.tests.test_platform_operations import _queue
from backend_v2.tests.test_platform_operations import session as session  # noqa: F401
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


def test_same_task_id_in_parallel_contexts_restores_each_original_project(monkeypatch):
    marker = ContextVar("concurrent_test_project", default=None)
    monkeypatch.setattr("backend_v2.app.core.database.bind_worker_project_context", marker.set)
    monkeypatch.setattr("backend_v2.app.core.database.reset_worker_project_context", marker.reset)
    first_bound, second_bound, first_reset = Event(), Event(), Event()
    task_id = str(uuid.uuid4())

    def execute(project, first):
        original = marker.set(f"original-{project}")
        try:
            if not first:
                assert first_bound.wait(5)
            sender = SimpleNamespace(request=SimpleNamespace(headers={"bda_project_id": project}))
            worker._bind_operation_project(sender=sender, task_id=task_id)
            assert marker.get() == project
            if first:
                first_bound.set()
                assert second_bound.wait(5)
            else:
                second_bound.set()
                assert first_reset.wait(5)
            try:
                worker._reset_operation_project(task_id=task_id)
            finally:
                if first:
                    first_reset.set()
            assert marker.get() == f"original-{project}"
        finally:
            marker.reset(original)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(execute, "project-a", True), pool.submit(execute, "project-b", False)]
        for future in futures:
            future.result(timeout=10)


def test_nested_same_task_id_restores_the_outer_project(monkeypatch):
    marker = ContextVar("nested_test_project", default=None)
    monkeypatch.setattr("backend_v2.app.core.database.bind_worker_project_context", marker.set)
    monkeypatch.setattr("backend_v2.app.core.database.reset_worker_project_context", marker.reset)
    task_id = str(uuid.uuid4())
    for project in ("outer", "inner"):
        sender = SimpleNamespace(request=SimpleNamespace(headers={"bda_project_id": project}))
        worker._bind_operation_project(sender=sender, task_id=task_id)
    worker._reset_operation_project(task_id=task_id)
    assert marker.get() == "outer"
    worker._reset_operation_project(task_id=task_id)
    assert marker.get() is None


def test_duplicate_start_does_not_mutate_running_operation(session):
    operation = _queue(session)
    mark_operation_running(session, operation.id)
    session.flush()
    session.refresh(operation)
    original = (operation.version, operation.started_at)
    mark_operation_running(session, operation.id)
    session.flush()
    assert (operation.version, operation.started_at) == original


def test_start_refreshes_an_operation_completed_after_it_was_loaded(session):
    operation = _queue(session)
    session.commit()
    # Keep an old identity-map row while another worker's commit is represented
    # by an unsynchronized SQL update. The transition must re-read under its lock.
    session.execute(
        Operation.__table__.update().where(Operation.id == operation.id).values(status="succeeded", version=2)
    )
    assert operation.status == "pending"
    mark_operation_running(session, operation.id)
    session.flush()
    assert operation.status == "succeeded"
    assert operation.version == 2


def test_finish_refreshes_an_operation_already_finished_by_another_worker(session):
    operation = _queue(session)
    session.commit()
    session.execute(
        Operation.__table__.update().where(Operation.id == operation.id).values(
            status="failed", version=2, result={"original": True}, error_code="original_failure"
        )
    )
    finish_operation(session, operation.id, result={"late": True})
    session.flush()
    assert operation.status == "failed"
    assert operation.result == {"original": True}
    assert operation.error_code == "original_failure"


@pytest.mark.skipif(os.getenv("BDA_V2_RUN_BOT_CONCURRENCY_DB_TESTS") != "1", reason="Dedicated bda_tests concurrency test disabled")
def test_outbox_publish_serializes_a_consumer_before_committing_queued(monkeypatch):
    url = make_url(get_settings().database_url)
    assert (url.host, url.port, url.database) == ("127.0.0.1", 55439, "bda_tests")
    engine = create_engine(url)
    factory = sessionmaker(engine, expire_on_commit=False)
    with engine.connect() as connection:
        assert connection.scalar(text("select current_database()")) == "bda_tests"
    suffix = uuid.uuid4().hex
    with factory.begin() as session:
        user = User(username=f"outbox-race-{suffix}", display_name="Offline concurrency", role="admin")
        organization = Organization(name=f"Outbox concurrency {suffix}")
        session.add_all([user, organization])
        session.flush()
        project = Project(name=f"Race {suffix}", project_type="test", owner_id=user.id, organization_id=organization.id)
        session.add(project)
        session.flush()
        operation = enqueue_operation(session, topic="copilot.agent_step", resource_type="test",
                                      resource_id=uuid.uuid4(), project_id=project.id,
                                      organization_id=organization.id, user=user)
        ids = operation.id, project.id, organization.id, user.id

    @contextmanager
    def scoped():
        with factory.begin() as session:
            yield session

    monkeypatch.setattr(tasks, "session_scope", scoped)
    monkeypatch.setattr(tasks, "SessionFactory", factory)
    attempts = []
    waiting = Event()

    def consume():
        with factory.begin() as session:
            waiting.set()
            mark_operation_running(session, ids[0])
        with factory.begin() as session:
            finish_operation(session, ids[0], result={"offline_consumer": True})

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            futures = []
            blocked_until_commit = []

            def send(*args, **kwargs):
                attempts.append(kwargs["task_id"])
                future = pool.submit(consume)
                futures.append(future)
                assert waiting.wait(5)
                try:
                    future.result(timeout=0.25)
                except TimeoutError:
                    blocked_until_commit.append(True)

            monkeypatch.setattr(tasks.celery_app, "send_task", send)
            result = tasks.publish_outbox.run(batch_size=1, event_ids=[str(ids[0])])
            for future in futures:
                future.result(timeout=5)
            assert result["published"] == 1
            assert blocked_until_commit == [True]
            assert tasks.publish_outbox.run(batch_size=1, event_ids=[str(ids[0])])["published"] == 0
            assert attempts == [str(ids[0])]
        with factory() as session:
            operation = session.get(Operation, ids[0])
            assert operation.status == "succeeded"
            assert operation.result == {"offline_consumer": True}
            event = session.get(OutboxEvent, ids[0])
            assert event.published_at is not None and event.attempts == 0
            settled = list(session.scalars(select(OutboxEvent).where(
                OutboxEvent.topic == "operation.settled", OutboxEvent.aggregate_id == ids[0]
            )))
            assert len(settled) == 1
    finally:
        with factory.begin() as session:
            session.execute(delete(OutboxEvent).where((OutboxEvent.id == ids[0]) | (OutboxEvent.aggregate_id == ids[0])))
            session.execute(delete(Operation).where(Operation.id == ids[0]))
            session.execute(delete(Project).where(Project.id == ids[1]))
            session.execute(delete(OrganizationMember).where(OrganizationMember.organization_id == ids[2]))
            session.execute(delete(Organization).where(Organization.id == ids[2]))
            session.execute(delete(User).where(User.id == ids[3]))
        engine.dispose()
