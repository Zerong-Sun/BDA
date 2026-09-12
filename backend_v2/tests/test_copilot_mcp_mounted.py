"""The MCP surface as it is actually mounted, not as a hand-built harness.

`test_copilot_mcp_transport.py` drives `mcp_app.endpoint` through a Starlette app it builds
itself. That covers the protocol and leaves the three things `main.py` decides untested:
that `POST /mcp` reaches the handler without a redirect, that the surface is *outside*
`production_write_gate`, and that a grant issued through the REST endpoint authenticates.

The third test is the important one. Mounting MCP beside `/api/v2` instead of inside it is
the central architectural choice of the surface, and its justification is that the cutover
fence cannot tell a read from a write when every call is one `POST /mcp`. If that fence
ever swallowed `/mcp`, reads would break during a cutover; if the per-tool check were
dropped, writes would escape one. Both halves are asserted together.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from backend_v2.app import main
from backend_v2.app.copilot import mcp_app
from backend_v2.app.copilot.registry import REGISTRY
from backend_v2.app.core.config import get_settings
from sqlalchemy.orm import Session

pytest_plugins = ["backend_v2.tests.test_v2_domains"]


@pytest.fixture
def mcp_client(domain_client, monkeypatch: pytest.MonkeyPatch):
    """The real app, with the MCP handler pointed at the fixture database.

    `/mcp` does not take `get_session` - it opens its own `session_scope`, because it is
    not a FastAPI route - so the override the fixture installs for the REST surface does
    not reach it.
    """
    client, ids = domain_client
    factory = ids["session_factory"]

    @contextmanager
    def scope() -> Iterator[Session]:
        with factory() as session:
            yield session
            session.commit()

    monkeypatch.setattr(mcp_app, "session_scope", scope)
    return client, ids


def _grant(client, project_id, *, capabilities=None) -> str:
    issued = client.post(
        "/api/v2/copilot/mcp-sessions",
        json={
            "project_id": str(project_id),
            "label": "mounted",
            "capabilities": capabilities or ["research"],
        },
    )
    assert issued.status_code == 201, issued.text
    return issued.json()["token"]


def _rpc(client, token: str, method: str, params: dict | None = None, path: str = "/mcp"):
    body: dict = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    return client.post(path, json=body, headers={"Authorization": f"Bearer {token}"})


def test_post_mcp_reaches_the_handler_without_a_redirect(mcp_client) -> None:
    """`app.mount` would answer this with a 307, and a client that drops the body or the
    Authorization header on redirect fails in a way that reads as an auth bug."""
    client, ids = mcp_client
    token = _grant(client, ids["project"])
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert response.json()["result"] == {}


def test_both_spellings_of_the_path_are_served(mcp_client) -> None:
    client, ids = mcp_client
    token = _grant(client, ids["project"])
    for path in ("/mcp", "/mcp/"):
        assert _rpc(client, token, "ping", path=path).status_code == 200, path


def test_a_grant_issued_over_rest_authenticates_on_the_mcp_surface(mcp_client) -> None:
    """The whole loop: a person issues a grant, an external client uses it."""
    client, ids = mcp_client
    token = _grant(client, ids["project"])

    listed = _rpc(client, token, "tools/list").json()["result"]["tools"]
    assert listed
    assert {tool["name"] for tool in listed} <= REGISTRY.ids()
    # Unbound grant, so no write tool is offered - checked here too because this is the
    # path a real client takes.
    assert not {tool["name"] for tool in listed} & REGISTRY.write_ids()


def _bound_grant(client, ids, goal: str) -> str:
    """A grant backed by a live agent run, so write tools are actually on offer."""
    from backend_v2.app.copilot import agent_runs
    from backend_v2.app.copilot.registry import REGISTRY as registry

    with ids["session_factory"]() as session:
        run = agent_runs.create_run(
            session,
            project_id=ids["project"],
            user_id=ids["user"],
            goal=goal,
            allowed_tools=sorted(registry.ids()),
        )
        session.commit()
        run_id = str(run.id)

    issued = client.post(
        "/api/v2/copilot/mcp-sessions",
        json={
            "project_id": str(ids["project"]),
            "label": "bound",
            "agent_run_id": run_id,
            "capabilities": ["research"],
        },
    )
    assert issued.status_code == 201, issued.text
    return issued.json()["token"]


def test_a_bound_grant_can_reach_a_write_tool_over_the_mounted_surface(mcp_client) -> None:
    """The mandate rule, end to end rather than in a harness."""
    client, ids = mcp_client
    token = _bound_grant(client, ids, "Search the literature for PD-1 binder affinity data and save it")

    names = {
        tool["name"] for tool in _rpc(client, token, "tools/list").json()["result"]["tools"]
    }
    assert "start_literature_search" in names


def test_the_cutover_fence_neither_swallows_nor_escapes_the_mcp_surface(
    mcp_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mounting outside `/api/v2` is only correct if both halves hold.

    `production_write_gate` matches on the `/api/v2` prefix and the HTTP method. Every MCP
    call is one `POST /mcp`, so inside the prefix it could only block the whole surface or
    be exempted; outside it, reads keep working during a cutover and the per-tool check in
    `mcp._authorize_write` is what stops writes. Both halves are driven through the
    mounted route, because asserting them on the functions would not notice the mount
    moving back inside the prefix.
    """
    client, ids = mcp_client
    token = _bound_grant(client, ids, "Search the literature for PD-1 binder affinity data and save it")
    monkeypatch.setattr(main.settings, "writes_enabled", False)
    monkeypatch.setattr(get_settings(), "writes_enabled", False)

    # A REST write is refused by the middleware - the behaviour being preserved.
    blocked = client.post(
        "/api/v2/copilot/mcp-sessions",
        json={"project_id": str(ids["project"]), "label": "x", "capabilities": ["research"]},
    )
    assert blocked.status_code == 503

    # The MCP surface is still readable: the middleware did not swallow it.
    read = _rpc(client, token, "tools/call", {"name": "list_proteins", "arguments": {}})
    assert read.status_code == 200
    assert read.json()["result"]["isError"] is False

    # And a write is refused by the rebuilt per-tool fence, carrying the platform's own
    # error code across the protocol boundary rather than a transport-level accident.
    write = _rpc(
        client,
        token,
        "tools/call",
        {"name": "start_literature_search", "arguments": {"query": "PD-1"}},
    )
    assert write.status_code == 200
    error = write.json()["error"]
    assert error["data"]["error_code"] == "writes_disabled"
    assert error["data"]["status"] == 503
