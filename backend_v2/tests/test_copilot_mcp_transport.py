"""The JSON-RPC surface in front of `copilot.mcp`.

What is worth pinning here is the protocol edges, not the authorization - that is
`test_copilot_mcp.py`. A handshake that answers wrongly, a notification answered
with an error, or a domain refusal that arrives as a transport crash all look
like the server is broken rather than like the client asked for something it may
not have.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.copilot import agent_runs, mcp_app
from backend_v2.app.copilot.registry import REGISTRY
from backend_v2.app.copilot.schemas import McpSessionCreate
from backend_v2.app.copilot.service import issue_mcp_session
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

_counter = itertools.count()
GOAL = "Search the literature for PD-1 binder affinity data and save what you find"


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


@pytest.fixture
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The real endpoint, over the test session rather than the process engine."""

    @contextmanager
    def scope() -> Iterator[Session]:
        yield session

    monkeypatch.setattr(mcp_app, "session_scope", scope)
    app = Starlette(routes=[Route("/mcp", mcp_app.endpoint, methods=["POST"])])
    with TestClient(app) as opened:
        yield opened


def _token(session: Session, *, bind_run: bool = False) -> str:
    n = next(_counter)
    user = User(username=f"rpc-{n}", display_name="R", role="researcher", enabled=True)
    organization = Organization(name=f"RPC Org {n}")
    session.add_all([user, organization])
    session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="admin"))
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"rpc-{n}", project_type="protein_design"
    )
    session.add(project)
    session.flush()
    run_id = None
    if bind_run:
        run = agent_runs.create_run(
            session,
            project_id=project.id,
            user_id=user.id,
            goal=GOAL,
            allowed_tools=sorted(REGISTRY.ids()),
        )
        run_id = run.id
    _, raw = issue_mcp_session(
        session,
        project,
        user,
        McpSessionCreate(
            project_id=project.id, label="rpc", agent_run_id=run_id, capabilities=["research"]
        ),
    )
    session.flush()
    return raw


def _call(client: TestClient, token: str, method: str, params: dict | None = None, request_id: int | None = 1):
    body: dict = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        body["id"] = request_id
    if params is not None:
        body["params"] = params
    return client.post("/mcp", json=body, headers={"Authorization": f"Bearer {token}"})


def test_missing_token_is_a_problem_document_not_a_jsonrpc_error(client: TestClient) -> None:
    """Authentication fails before JSON-RPC begins, so it answers in HTTP terms."""
    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error_code"] == "mcp_session_invalid"


def test_invalid_token_says_nothing_about_why(client: TestClient) -> None:
    response = client.post(
        "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, headers={"Authorization": "Bearer nope"}
    )
    assert response.status_code == 401


def test_initialize_reports_only_what_is_implemented(client: TestClient, session: Session) -> None:
    token = _token(session)
    result = _call(client, token, "initialize", {"protocolVersion": mcp_app.PROTOCOL_VERSION}).json()["result"]

    assert result["protocolVersion"] == mcp_app.PROTOCOL_VERSION
    # Prompts, resources and sampling are not implemented and are not claimed.
    assert set(result["capabilities"]) == {"tools"}
    assert result["serverInfo"]["name"] == "bda-copilot"
    assert "read-only" in result["instructions"]


def test_initialize_falls_back_on_an_unknown_protocol_version(client: TestClient, session: Session) -> None:
    token = _token(session)
    result = _call(client, token, "initialize", {"protocolVersion": "1999-01-01"}).json()["result"]
    assert result["protocolVersion"] == mcp_app.PROTOCOL_VERSION


def test_notification_is_accepted_without_a_response(client: TestClient, session: Session) -> None:
    """`notifications/initialized` has no id. Answering it with an error would
    make a successful handshake look like a failure."""
    token = _token(session)
    response = _call(client, token, "notifications/initialized", request_id=None)
    assert response.status_code == 202
    assert not response.content


def test_ping_answers_empty(client: TestClient, session: Session) -> None:
    token = _token(session)
    assert _call(client, token, "ping").json()["result"] == {}


def test_unknown_method_is_method_not_found(client: TestClient, session: Session) -> None:
    token = _token(session)
    error = _call(client, token, "resources/list").json()["error"]
    assert error["code"] == mcp_app.METHOD_NOT_FOUND


def test_unparseable_body_is_a_parse_error(client: TestClient, session: Session) -> None:
    token = _token(session)
    response = client.post("/mcp", content=b"{not json", headers={"Authorization": f"Bearer {token}"})
    assert response.json()["error"]["code"] == mcp_app.PARSE_ERROR


def test_batches_are_refused(client: TestClient, session: Session) -> None:
    token = _token(session)
    response = client.post("/mcp", json=[{"jsonrpc": "2.0", "id": 1, "method": "ping"}],
                           headers={"Authorization": f"Bearer {token}"})
    assert response.json()["error"]["code"] == mcp_app.INVALID_REQUEST


def test_tools_list_carries_registry_schemas(client: TestClient, session: Session) -> None:
    token = _token(session)
    tools = _call(client, token, "tools/list").json()["result"]["tools"]
    assert tools
    for tool in tools:
        spec = REGISTRY.get(tool["name"])
        assert spec is not None
        assert tool["inputSchema"] == spec.parameters


def test_read_only_listing_offers_no_write(client: TestClient, session: Session) -> None:
    token = _token(session)
    names = {tool["name"] for tool in _call(client, token, "tools/list").json()["result"]["tools"]}
    assert not names & REGISTRY.write_ids()


def test_bound_listing_offers_the_requested_write(client: TestClient, session: Session) -> None:
    token = _token(session, bind_run=True)
    names = {tool["name"] for tool in _call(client, token, "tools/list").json()["result"]["tools"]}
    assert "start_literature_search" in names


def test_tools_call_returns_content(client: TestClient, session: Session) -> None:
    token = _token(session)
    result = _call(client, token, "tools/call", {"name": "list_proteins", "arguments": {}}).json()["result"]
    assert result["isError"] is False
    assert result["content"][0]["type"] == "text"


def test_call_without_a_name_is_invalid_params(client: TestClient, session: Session) -> None:
    token = _token(session)
    assert _call(client, token, "tools/call", {}).json()["error"]["code"] == mcp_app.INVALID_PARAMS


def test_non_object_arguments_are_invalid_params(client: TestClient, session: Session) -> None:
    token = _token(session)
    body = {"name": "list_proteins", "arguments": ["nope"]}
    assert _call(client, token, "tools/call", body).json()["error"]["code"] == mcp_app.INVALID_PARAMS


def test_a_refused_tool_keeps_the_platform_error_code(client: TestClient, session: Session) -> None:
    """One failure, one name, whichever surface reads it."""
    token = _token(session)
    error = _call(
        client, token, "tools/call", {"name": "start_literature_search", "arguments": {"query": "x"}}
    ).json()["error"]
    assert error["data"]["error_code"] == "mcp_tool_not_available"
    assert error["data"]["status"] == 403
