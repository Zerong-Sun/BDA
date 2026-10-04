from __future__ import annotations

import uuid
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.compute.models import OutboxEvent
from backend_v2.app.copilot.api import router
from backend_v2.app.copilot.models import (
    CopilotAgentRun,
    CopilotAgentTurn,
    CopilotConversation,
    CopilotMessage,
)
from backend_v2.app.core.database import get_session
from backend_v2.app.core.models import Base
from backend_v2.app.identity.deps import current_user
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.platform.models import Operation
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.tests._sqlite import enforce_foreign_keys
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from starlette.types import Message, Receive, Scope, Send


def _snapshot(factory: sessionmaker[Session]) -> dict:
    # A separate connection must see committed state, unlike StaticPool tests
    # that share the request's connection and can read its uncommitted writes.
    with factory() as session:
        return {
            "runs": {
                str(row.id): (row.status, row.turn_count, row.version)
                for row in session.scalars(select(CopilotAgentRun))
            },
            "conversations": [str(row.id) for row in session.scalars(select(CopilotConversation))],
            "messages": {
                str(row.id): (str(row.conversation_id), row.content)
                for row in session.scalars(select(CopilotMessage))
            },
            "turns": {
                str(row.id): (str(row.run_id), row.role, row.content)
                for row in session.scalars(select(CopilotAgentTurn))
            },
            "operations": {
                str(row.id): str(row.resource_id) for row in session.scalars(select(Operation))
            },
            "outbox": {
                str(row.id): str(row.aggregate_id) for row in session.scalars(select(OutboxEvent))
            },
        }


@pytest.fixture
def acceptance_client(tmp_path: Path) -> Generator[SimpleNamespace]:
    engine = enforce_foreign_keys(create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'acceptance.db'}", connect_args={"check_same_thread": False}
    ))
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        user = User(username="acceptance-admin", display_name="Acceptance Admin", role="admin", enabled=True)
        organization = Organization(name="Acceptance Org")
        session.add_all([user, organization])
        session.flush()
        session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
        project = Project(
            organization_id=organization.id, owner_id=user.id, name="Acceptance project", project_type="protein_design"
        )
        session.add(project)
        session.flush()
        session.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
        stopped_run = CopilotAgentRun(
            project_id=project.id, created_by=user.id, goal="Stopped synthetic task",
            bot="researcher", status="succeeded", allowed_tools=["research_overview"],
        )
        session.add(stopped_run)
        session.commit()
        project_id, user_id, stopped_run_id = project.id, user.id, stopped_run.id

    state = SimpleNamespace(fail_commit=False, starts=[], factory=factory)

    class RequestSession(Session):
        def commit(self) -> None:
            if state.fail_commit:
                raise OperationalError("COMMIT", {}, RuntimeError("synthetic commit failure"))
            super().commit()

    request_factory = sessionmaker(engine, class_=RequestSession, autoflush=False, expire_on_commit=False)

    def session_override() -> Generator[Session]:
        # Match production get_session: its default request-scoped finalizer
        # runs after FastAPI has sent the response, so it cannot establish 202.
        with request_factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def user_override() -> User:
        with factory() as session:
            user = session.get(User, user_id)
            assert user is not None
            return user

    application = FastAPI()
    application.include_router(router, prefix="/api/v2")
    application.dependency_overrides[get_session] = session_override
    application.dependency_overrides[current_user] = user_override

    async def probe(scope: Scope, receive: Receive, send: Send) -> None:
        async def observed_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                state.starts.append((message["status"], _snapshot(factory)))
            await send(message)

        await application(scope, receive, observed_send)

    state.client = TestClient(probe, raise_server_exceptions=False)
    state.project_id, state.stopped_run_id = str(project_id), str(stopped_run_id)
    try:
        yield state
    finally:
        state.client.close()
        engine.dispose()


def _request(state: SimpleNamespace, kind: str):
    if kind == "chat":
        return state.client.post("/api/v2/copilot/chat", json={
            "project_id": state.project_id, "message": "Synthetic chat acceptance", "bot": "researcher",
        })
    if kind == "start":
        return state.client.post("/api/v2/copilot/agent-runs", json={
            "project_id": state.project_id, "goal": "Synthetic run acceptance", "bot": "researcher",
            "service_kind": "custom", "authorized_writes": [],
        })
    return state.client.post(f"/api/v2/copilot/agent-runs/{state.stopped_run_id}/continuations",
        headers={"If-Match": 'W/"1"'}, json={"message": "Synthetic continuation acceptance"})


@pytest.mark.parametrize("kind", ["chat", "start", "continuation"])
def test_accepted_resources_and_outbox_visible_when_202_starts(acceptance_client, kind: str) -> None:
    state = acceptance_client
    response = _request(state, kind)
    assert response.status_code == 202, response.text
    assert len(state.starts) == 1
    status, sent = state.starts[0]
    assert status == 202
    body = response.json()
    if kind == "chat":
        resource_id = body["message"]["id"]
        assert body["conversation_id"] in sent["conversations"]
        assert sent["messages"][resource_id] == (body["conversation_id"], "Synthetic chat acceptance")
    else:
        run = body["run"]
        resource_id = run["id"]
        assert sent["runs"][resource_id] == ("running", run["turn_count"], run["version"])
        if kind == "continuation":
            assert resource_id == state.stopped_run_id
            assert run["turn_count"] == 1
            assert run["version"] > 1
            assert list(sent["turns"].values()) == [
                (resource_id, "user", "Synthetic continuation acceptance")
            ]
    assert sent["operations"] == {body["operation_id"]: resource_id}
    assert sent["outbox"] == {body["operation_id"]: resource_id}


@pytest.mark.parametrize("kind", ["chat", "start", "continuation"])
def test_commit_failure_never_sends_accepted_or_leaves_partial_work(acceptance_client, kind: str) -> None:
    state = acceptance_client
    before = _snapshot(state.factory)
    state.fail_commit = True
    response = _request(state, kind)
    assert response.status_code == 500
    assert [status for status, _ in state.starts] == [500]
    assert _snapshot(state.factory) == before
    # The existing stopped task must also remain unmodified after a failed
    # continuation, so retrying does not inherit a phantom running task.
    with state.factory() as session:
        run = session.get(CopilotAgentRun, uuid.UUID(state.stopped_run_id))
        assert run is not None
        assert (run.status, run.turn_count, run.version) == ("succeeded", 0, 1)
