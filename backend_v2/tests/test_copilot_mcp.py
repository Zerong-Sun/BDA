"""The MCP capability surface: what a grant exposes, and what it refuses.

Two of these tests are structural rather than behavioural, and they are the ones
worth keeping longest:

* `test_listing_never_leaves_the_registry` fails if anyone hand-writes a tool for
  MCP instead of deriving it. That is the drift `registry.py` was written to end,
  and MCP is the obvious place for it to come back.
* `test_unbound_session_lists_no_write_tool` pins the rule the whole module
  exists for. An MCP client has no user message, so a grant with no live agent
  run has no mandate, so it is offered no writes.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.copilot import agent_runs, mcp
from backend_v2.app.copilot.models import CopilotConfig, CopilotMcpSession
from backend_v2.app.copilot.registry import REGISTRY
from backend_v2.app.copilot.schemas import McpSessionCreate
from backend_v2.app.copilot.service import issue_mcp_session, revoke_mcp_session
from backend_v2.app.core.config import get_settings
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
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

#: A goal that asks, in the user's own words, for one of the five gated actions.
#: `actions.request_allows` reads exactly this, which is why the wording matters.
GOAL_WITH_LITERATURE_REQUEST = "Search the literature for PD-1 binder affinity data and save what you find"
GOAL_WITHOUT_REQUEST = "Summarise what the project already knows about PD-1 binders"


def _project(session: Session, *, role: str = "researcher") -> tuple[Project, User]:
    n = next(_counter)
    user = User(username=f"mcp-{n}", display_name="M", role=role, enabled=True)
    organization = Organization(name=f"MCP Org {n}")
    session.add_all([user, organization])
    session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="admin"))
    project = Project(
        organization_id=organization.id,
        owner_id=user.id,
        name=f"mcp-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project, user


def _grant(
    session: Session,
    project: Project,
    user: User,
    *,
    capabilities: list[str] | None = None,
    run_id: uuid.UUID | None = None,
) -> tuple[CopilotMcpSession, str]:
    # `or ["research"]` would turn the empty-grant case into the default one.
    return issue_mcp_session(
        session,
        project,
        user,
        McpSessionCreate(
            project_id=project.id,
            label="client",
            agent_run_id=run_id,
            capabilities=["research"] if capabilities is None else capabilities,
        ),
    )


def _run(session: Session, project: Project, user: User, *, goal: str, tools: list[str] | None = None):
    return agent_runs.create_run(
        session,
        project_id=project.id,
        user_id=user.id,
        goal=goal,
        allowed_tools=tools if tools is not None else sorted(REGISTRY.ids()),
    )


# --- Structure ---------------------------------------------------------------


def test_listing_never_leaves_the_registry(session: Session) -> None:
    """Every listed tool is a registry tool, with the registry's own schema.

    The failure this guards is someone adding an MCP-only tool definition. It
    would work, and it would be the fourth place a tool is declared.
    """
    project, user = _project(session)
    grant, _ = _grant(session, project, user)
    listing = mcp.tool_listing(mcp.available_tools(session, grant))

    assert listing, "a research grant should expose something"
    for entry in listing:
        spec = REGISTRY.get(entry["name"])
        assert spec is not None, f"{entry['name']} is not in the registry"
        assert entry["inputSchema"] is spec.parameters
        assert entry["description"] == spec.description
        assert entry["annotations"]["readOnlyHint"] is (spec.execution_mode == "read")


def test_agent_run_tools_are_never_exposed(session: Session) -> None:
    """`requires="agent_run"` tools suspend a run; an MCP client cannot suspend."""
    project, user = _project(session)
    run = _run(session, project, user, goal=GOAL_WITH_LITERATURE_REQUEST)
    grant, _ = _grant(session, project, user, run_id=run.id)

    names = {spec.id for spec in mcp.available_tools(session, grant)}
    assert "spawn_subagent" not in names
    assert "await_compute_job" not in names
    # And the context refuses them even if one were listed.
    assert mcp.tool_context(session, grant).agent_run is None


# --- The mandate rule --------------------------------------------------------


def test_unbound_session_lists_no_write_tool(session: Session) -> None:
    project, user = _project(session)
    grant, _ = _grant(session, project, user)

    specs = mcp.available_tools(session, grant)
    assert specs, "a read-only grant still reads"
    assert all(spec.execution_mode == "read" for spec in specs)
    assert not {spec.id for spec in specs} & REGISTRY.write_ids()


def test_bound_session_gains_the_writes_its_goal_asked_for(session: Session) -> None:
    project, user = _project(session)
    run = _run(session, project, user, goal=GOAL_WITH_LITERATURE_REQUEST)
    grant, _ = _grant(session, project, user, run_id=run.id)

    names = {spec.id for spec in mcp.available_tools(session, grant)}
    assert "start_literature_search" in names


def test_intent_gate_drops_writes_the_goal_did_not_ask_for(session: Session) -> None:
    """The goal is the user's words. A goal that asks for nothing grants nothing."""
    project, user = _project(session)
    run = _run(session, project, user, goal=GOAL_WITHOUT_REQUEST)
    grant, _ = _grant(session, project, user, run_id=run.id)

    names = {spec.id for spec in mcp.available_tools(session, grant)}
    assert "start_literature_search" not in names
    assert "create_knowledge_draft" not in names


def test_run_vocabulary_narrows_the_grant(session: Session) -> None:
    project, user = _project(session)
    run = _run(
        session,
        project,
        user,
        goal=GOAL_WITH_LITERATURE_REQUEST,
        tools=["list_proteins", "start_literature_search"],
    )
    grant, _ = _grant(session, project, user, run_id=run.id)

    names = {spec.id for spec in mcp.available_tools(session, grant)}
    assert names == {"list_proteins", "start_literature_search"}


def test_finished_run_degrades_the_grant_to_read_only(session: Session) -> None:
    """A spent mandate narrows the grant instead of breaking the client."""
    project, user = _project(session)
    run = _run(session, project, user, goal=GOAL_WITH_LITERATURE_REQUEST)
    grant, _ = _grant(session, project, user, run_id=run.id)
    assert "start_literature_search" in {spec.id for spec in mcp.available_tools(session, grant)}

    agent_runs.finish(session, run, status="succeeded")
    session.flush()

    specs = mcp.available_tools(session, grant)
    assert specs
    assert all(spec.execution_mode == "read" for spec in specs)


# --- Capability narrowing ----------------------------------------------------


def test_project_configuration_narrows_outstanding_grants(session: Session) -> None:
    """Turning a capability off narrows grants already issued, without revoking."""
    project, user = _project(session)
    grant, _ = _grant(session, project, user, capabilities=["research"])
    assert "list_proteins" in {spec.id for spec in mcp.available_tools(session, grant)}

    session.add(CopilotConfig(project_id=project.id, enabled_skills=["knowledge"]))
    session.flush()

    names = {spec.id for spec in mcp.available_tools(session, grant)}
    assert "list_proteins" not in names
    assert "search_project_knowledge" in names


def test_a_grant_cannot_exceed_the_project_configuration(session: Session) -> None:
    project, user = _project(session)
    session.add(CopilotConfig(project_id=project.id, enabled_skills=["knowledge"]))
    session.flush()

    with pytest.raises(DomainError) as excinfo:
        _grant(session, project, user, capabilities=["wetlab-authoring"])
    assert excinfo.value.error_code == "copilot_capability_disabled"


def test_unknown_capability_is_refused(session: Session) -> None:
    project, user = _project(session)
    with pytest.raises(DomainError) as excinfo:
        _grant(session, project, user, capabilities=["not-a-capability"])
    assert excinfo.value.error_code == "copilot_capability_not_found"


def test_a_grant_with_no_capability_is_refused(session: Session) -> None:
    """An empty grant would read as 'everything' through `normalize_capabilities`."""
    project, user = _project(session)
    with pytest.raises(DomainError) as excinfo:
        _grant(session, project, user, capabilities=[])
    assert excinfo.value.error_code == "copilot_mcp_session_without_capabilities"

    # And the dispatch agrees, for a row written some other way.
    grant = CopilotMcpSession(
        project_id=project.id,
        issued_by=user.id,
        label="hand-written",
        granted_capabilities=[],
        token_hash="0" * 64,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add(grant)
    session.flush()
    assert mcp.available_tools(session, grant) == []


# --- Token lifecycle ---------------------------------------------------------


def test_token_resolves_once_and_is_stored_hashed(session: Session) -> None:
    project, user = _project(session)
    grant, token = _grant(session, project, user)

    assert grant.token_hash != token
    assert mcp.resolve_session(session, token).id == grant.id


def test_revoked_and_expired_answer_the_same_way(session: Session) -> None:
    project, user = _project(session)
    grant, token = _grant(session, project, user)
    revoke_mcp_session(session, grant, user, project)
    session.flush()

    with pytest.raises(DomainError) as revoked:
        mcp.resolve_session(session, token)
    assert revoked.value.status_code == 401

    other, other_token = _grant(session, project, user)
    other.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.flush()
    with pytest.raises(DomainError) as expired:
        mcp.resolve_session(session, other_token)
    assert expired.value.error_code == revoked.value.error_code


def test_revocation_is_idempotent(session: Session) -> None:
    project, user = _project(session)
    grant, _ = _grant(session, project, user)
    revoke_mcp_session(session, grant, user, project)
    first = grant.revoked_at
    revoke_mcp_session(session, grant, user, project)
    assert grant.revoked_at == first


def test_a_grant_does_not_outlive_its_issuer(session: Session) -> None:
    project, user = _project(session)
    grant, _ = _grant(session, project, user)
    user.enabled = False
    session.flush()

    with pytest.raises(DomainError) as excinfo:
        mcp.available_tools(session, grant)
    assert excinfo.value.error_code == "mcp_session_actor_unavailable"


def test_issuing_against_a_finished_run_is_refused(session: Session) -> None:
    project, user = _project(session)
    run = _run(session, project, user, goal=GOAL_WITH_LITERATURE_REQUEST)
    agent_runs.finish(session, run, status="succeeded")
    session.flush()

    with pytest.raises(DomainError) as excinfo:
        _grant(session, project, user, run_id=run.id)
    assert excinfo.value.error_code == "copilot_agent_run_not_live"


# --- Calling -----------------------------------------------------------------


def test_call_refuses_a_tool_that_was_never_offered(session: Session) -> None:
    project, user = _project(session)
    grant, _ = _grant(session, project, user)

    with pytest.raises(DomainError) as excinfo:
        mcp.call_tool(session, grant, "start_literature_search", {})
    assert excinfo.value.error_code == "mcp_tool_not_available"
    assert excinfo.value.status_code == 403


def test_unknown_tool_is_refused(session: Session) -> None:
    project, user = _project(session)
    grant, _ = _grant(session, project, user)
    with pytest.raises(DomainError):
        mcp.call_tool(session, grant, "rm_rf", {})


def test_read_tool_runs_and_is_counted(session: Session) -> None:
    project, user = _project(session)
    grant, _ = _grant(session, project, user)

    call = mcp.call_tool(session, grant, "list_proteins", {})
    assert call.result is not None
    assert grant.call_count == 1
    assert grant.last_used_at is not None


def test_the_cutover_write_fence_is_rebuilt_per_tool(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`production_write_gate` cannot see execution mode; this check can."""
    project, user = _project(session)
    run = _run(session, project, user, goal=GOAL_WITH_LITERATURE_REQUEST)
    grant, _ = _grant(session, project, user, run_id=run.id)
    monkeypatch.setattr(get_settings(), "writes_enabled", False)

    with pytest.raises(DomainError) as excinfo:
        mcp.call_tool(session, grant, "start_literature_search", {"query": "PD-1"})
    assert excinfo.value.error_code == "writes_disabled"
    assert excinfo.value.status_code == 503

    # Reads are untouched: a cutover stops writes, it does not blind the surface.
    assert mcp.call_tool(session, grant, "list_proteins", {}).result is not None


def test_describe_reports_what_the_grant_can_do_now(session: Session) -> None:
    project, user = _project(session)
    run = _run(session, project, user, goal=GOAL_WITH_LITERATURE_REQUEST)
    grant, _ = _grant(session, project, user, run_id=run.id)

    described = mcp.describe(session, grant)
    assert described["mandate_live"] is True
    assert "start_literature_search" in described["write_tools"]
    assert set(described["write_tools"]) <= set(described["tools"])


# --- Addresses have to be real ------------------------------------------------


def test_every_declared_project_route_exists_in_the_api() -> None:
    """A citation URI that resolves to a fabricated path is worse than none.

    `PROJECT_ROUTES` used to be `f"/api/v2/{kind}s/{id}"`, which is wrong for most kinds -
    `experiment_result` is served under `/projects/{id}/experiment-results` and `finding`
    under `/research-findings/{id}`. This pins each declared route against the real
    OpenAPI document, so renaming a route fails here rather than silently handing an
    external agent a dead link.
    """
    import json
    from pathlib import Path

    document = json.loads((Path(__file__).resolve().parents[1] / "openapi.json").read_text())
    paths = set(document["paths"])
    for kind, route in mcp.PROJECT_ROUTES.items():
        if route is None:
            continue  # addressed but not fetchable; there is no path to check
        # The template uses `{id}`; the document names its own parameter.
        prefix = route.split("{")[0]
        assert any(
            path.startswith(prefix) and path.count("/") == route.count("/") for path in paths
        ), f"{kind}: {route} matches no path in openapi.json"


def test_every_kind_this_server_can_emit_dereferences(session: Session) -> None:
    """A link the server handed out must never come back as "nothing is addressed by this".

    The kinds are read out of `ProjectContextService` rather than listed here, so adding a
    citable kind to the context service without teaching `PROJECT_ROUTES` about it fails
    right here. That is how this was missed the first time: `PROJECT_ROUTES` was written
    from the kinds that came to mind, and `target` - the first one a real server emitted -
    was not among them.
    """
    import re
    from pathlib import Path as _Path

    source = (_Path(mcp.__file__).parent / "project_context.py").read_text()
    emitted = set(re.findall(r'_item\(\s*\n\s*"([a-z_]+)"', source))
    assert emitted, "the extraction stopped matching; fix the pattern, not the assertion"

    project, user = _project(session)
    grant, _ = _grant(session, project, user)
    for kind in sorted(emitted):
        uri = f"bda://project/{kind}/11111111-1111-1111-1111-111111111111"
        found = mcp.read_resource(session, grant, uri)
        assert found["uri"] == uri
        assert found["payload"]["workspace_type"] == kind


def test_an_unknown_project_kind_addresses_nothing(session: Session) -> None:
    """Previously any string at all came back as a success with a made-up path."""
    project, user = _project(session)
    grant, _ = _grant(session, project, user)
    with pytest.raises(DomainError) as excinfo:
        mcp.read_resource(session, grant, "bda://project/frobnicate/whatever")
    assert excinfo.value.error_code == "mcp_resource_not_found"
    assert excinfo.value.status_code == 404


def test_a_known_project_kind_points_at_its_real_route(session: Session) -> None:
    project, user = _project(session)
    grant, _ = _grant(session, project, user)
    found = mcp.read_resource(session, grant, "bda://project/candidate/abc-123")
    assert found["payload"]["authoritative_path"] == "/api/v2/candidates/abc-123"
