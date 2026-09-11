"""Dispatch for the MCP capability surface.

This module is the whole of the MCP contract that is not transport. It answers
two questions and nothing else: which tools does this grant expose, and may this
call run. `mcp_app` turns JSON-RPC into calls here; nothing here knows about HTTP.

The design constraint that shapes everything below: **there is no second tool
layer.** `registry.REGISTRY` already declares each tool's schema, capability,
execution mode and handler in one object, and `REGISTRY.execute` is the only
dispatch point, which is what makes the capability check and the audit record
impossible to skip. Re-declaring tools for MCP would restore exactly the drift
`registry.py` was written to end, so this module derives everything from the
registry and adds only the two restrictions an external caller needs.

Restriction one - **intent**. `actions.request_allows` reads the *user's own
words* to decide whether a write was asked for. A chat turn has the message; an
agent run has `goal`, which is why `agent_loop` passes `request_text=run.goal`.
An MCP client has neither: its arguments were written by the model on the other
end, so treating them as the request would let that model authorize itself. A
grant therefore borrows a run's goal, and a grant with no live run exposes no
write tools at all.

Restriction two - **the run's own vocabulary**. When a grant is bound, the tools
are additionally intersected with `run.allowed_tools`, the same closed list
`agent_loop._schemas` uses. A grant cannot widen the run it borrows from.

Tools declaring `requires="agent_run"` are never exposed. They suspend a run and
wait for a poller to resume it; an MCP client cannot be suspended, and listing
them would put a second executor on one run. `tool_context` also leaves
`agent_run` unset, so `REGISTRY.execute` refuses them even if one were listed.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import set_request_rls_context
from ..core.problem import DomainError
from . import tools as _tools  # noqa: F401  (registers the tool catalogue)
from .capabilities import (
    normalize_capabilities,
    research_kinds_for_capabilities,
    tools_for_capabilities,
)
from .models import CopilotAgentRun, CopilotConfig, CopilotMcpSession
from .registry import REGISTRY, ToolContext, ToolSpec

#: Run states in which the goal is still a live mandate. A finished, failed or
#: cancelled run has spent its authority; the grant stays usable but degrades to
#: read-only rather than erroring, so a client mid-conversation keeps working and
#: simply stops being offered the writes.
LIVE_RUN_STATUSES = frozenset({"running", "awaiting_tasks"})

#: Context attributes a tool may require that MCP never provides.
UNSUPPORTED_REQUIRES = frozenset({"agent_run"})


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def resolve_session(session: Session, raw_token: str, *, now: datetime | None = None) -> CopilotMcpSession:
    """The grant this token names, or 401.

    Revoked and expired are the same answer on purpose: telling a caller which
    one it was says whether the token was ever valid.
    """
    moment = now or datetime.now(UTC)
    if not raw_token:
        raise DomainError("not_authenticated", "An MCP session token is required", status_code=401)
    row = session.scalar(
        select(CopilotMcpSession).where(CopilotMcpSession.token_hash == hash_token(raw_token))
    )
    if row is None or row.revoked_at is not None or _aware(row.expires_at) <= moment:
        raise DomainError(
            "mcp_session_invalid", "The MCP session is invalid, expired or revoked", status_code=401
        )
    return row


def _aware(value: datetime) -> datetime:
    """SQLite hands back naive datetimes for timezone-aware columns."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _actors(session: Session, grant: CopilotMcpSession) -> tuple[Any, Any]:
    from ..identity.models import User
    from ..projects.models import Project

    project = session.get(Project, grant.project_id)
    user = session.get(User, grant.issued_by)
    if project is None or user is None or not user.enabled:
        # The person who granted this is gone or disabled. The grant does not
        # outlive them: it carries their authority and nothing of its own.
        raise DomainError(
            "mcp_session_actor_unavailable",
            "The user who issued this MCP session is unavailable",
            status_code=401,
        )
    return project, user


def apply_rls(session: Session, grant: CopilotMcpSession) -> None:
    """Run every statement under the issuing user, never a service identity.

    Same call and same order as `identity.deps._resolve_user`. Skipping it would
    leave an MCP client reading across the organization fence that the issuer
    themselves is inside.
    """
    _, user = _actors(session, grant)
    set_request_rls_context(session, user_id=user.id, is_global_admin=user.role == "admin")


def bound_run(session: Session, grant: CopilotMcpSession) -> CopilotAgentRun | None:
    """The live run backing this grant, if there is one."""
    if grant.agent_run_id is None:
        return None
    run = session.get(CopilotAgentRun, grant.agent_run_id)
    if run is None or run.status not in LIVE_RUN_STATUSES:
        return None
    if run.project_id != grant.project_id:
        # A run reassigned to another project is not a mandate for this one.
        return None
    return run


def granted_capabilities(session: Session, grant: CopilotMcpSession) -> set[str]:
    """The grant's capabilities, narrowed by the project's own configuration.

    Intersected on every call rather than frozen at issue time, so turning a
    capability off for the project immediately narrows the grants already out.

    An empty `granted_capabilities` means *none*. `normalize_capabilities([])`
    returns the full research alias set - correct for a project config, where
    empty means "unconfigured, use the default", and wrong here, where empty
    means the issuer granted nothing.
    """
    if not grant.granted_capabilities:
        return set()
    config = session.scalar(select(CopilotConfig).where(CopilotConfig.project_id == grant.project_id))
    enabled = normalize_capabilities(list(config.enabled_skills) if config and config.enabled_skills else None)
    return normalize_capabilities(list(grant.granted_capabilities)) & enabled


def available_tools(session: Session, grant: CopilotMcpSession) -> list[ToolSpec]:
    """Exactly the tools this grant may call, in registry order.

    A tool that is not callable is not listed. Listing it and refusing the call
    teaches the model on the other end to retry, and a refusal it can retry reads
    as an obstacle rather than a boundary.
    """
    # Validated here, not only in `tool_context`: a listing is already a
    # disclosure, and a grant whose issuer is gone should stop disclosing before
    # it stops writing.
    _actors(session, grant)
    capabilities = granted_capabilities(session, grant)
    names = tools_for_capabilities(capabilities)
    run = bound_run(session, grant)

    if run is None:
        # No live mandate: reads only. This is the rule the whole module exists
        # for - see the intent restriction in the module docstring.
        writes = REGISTRY.write_ids()
        names = {name for name in names if name not in writes}
    else:
        names &= set(run.allowed_tools or [])
        names = _intent_filtered(session, grant, run, names)

    # Selected by tool id over the whole registry, the way `agent_loop._schemas`
    # does, rather than by `for_capabilities`. The two differ: a capability may
    # list a tool another capability owns (`result-interpretation` lists
    # `list_project_candidates`, whose spec belongs to `project-read`), and
    # filtering by the owning capability would silently grant less here than the
    # same capability grants an agent run. One vocabulary, one meaning.
    return [
        spec
        for spec in REGISTRY.all()
        if spec.id in names and spec.requires not in UNSUPPORTED_REQUIRES
    ]


def _intent_filtered(
    session: Session, grant: CopilotMcpSession, run: CopilotAgentRun, names: set[str]
) -> set[str]:
    """Drop writes the run's goal did not ask for.

    Only the five action-service tools can be checked this way: `request_allows`
    is defined over `actions._ACTION_REQUEST_TERMS` and knows no others. The rest
    of the write tools are gated by the run binding alone, which is why a grant
    without a run exposes none of them.
    """
    from .research_agent import WRITE_TOOL_NAMES

    gated = names & WRITE_TOOL_NAMES
    if not gated:
        return names
    from .actions import CopilotActionService

    project, user = _actors(session, grant)
    service = CopilotActionService(
        session, project, user, request_text=run.goal, source_message_id=run.id
    )
    return {name for name in names if name not in WRITE_TOOL_NAMES or service.request_allows(name)}


def tool_context(session: Session, grant: CopilotMcpSession) -> ToolContext:
    """The services an MCP call may use.

    Mirrors `agent_loop._tool_context`, with two differences that are the point:
    `agent_run` is left unset, and `request_text` comes from the bound run's goal
    - never from the client's arguments.
    """
    from .actions import CopilotActionService
    from .project_context import ProjectContextService
    from .research_context import ResearchContextService

    project, user = _actors(session, grant)
    run = bound_run(session, grant)
    return ToolContext(
        project_id=project.id,
        user_id=user.id,
        session=session,
        research=ResearchContextService(session, project),
        project=ProjectContextService(session, project),
        actions=(
            CopilotActionService(
                session, project, user, request_text=run.goal, source_message_id=run.id
            )
            if run is not None
            else None
        ),
        allowed_kinds=research_kinds_for_capabilities(granted_capabilities(session, grant)),
        agent_run=None,
    )


def call_tool(
    session: Session, grant: CopilotMcpSession, tool_id: str, arguments: dict[str, Any] | None
) -> Any:
    """Run one tool for one grant.

    The availability check is done against `available_tools` rather than against
    the capability alone, so the call goes through the same narrowing the listing
    did. Anything else would let a client call a tool it was never offered.
    """
    allowed = {spec.id for spec in available_tools(session, grant)}
    if tool_id not in allowed:
        raise DomainError(
            "mcp_tool_not_available",
            f"{tool_id} is not available to this MCP session",
            status_code=403,
        )
    spec = REGISTRY.get(tool_id)
    assert spec is not None  # available_tools only returns registered specs
    _authorize_write(session, grant, spec)
    result = REGISTRY.execute(
        tool_id, tool_context(session, grant), dict(arguments or {}), granted=None
    )
    grant.last_used_at = datetime.now(UTC)
    grant.call_count = (grant.call_count or 0) + 1
    _audit(session, grant, spec)
    return result


def _audit(session: Session, grant: CopilotMcpSession, spec: ToolSpec) -> None:
    """Record which grant made a write, over and above the action's own row.

    `actions._once` already audits the five gated actions, but it names the
    *mandate* (`source_message_id`, which for a bound grant is the run). That
    cannot distinguish work the run's own loop did from work an external client
    did through this grant, and "who was holding the token" is the question an
    incident actually starts from.

    Reads are not audited, following the rule the registry already states: a row
    per read buries the writes that matter.
    """
    if not spec.audit:
        return
    from ..audit.service import record_audit

    project, user = _actors(session, grant)
    record_audit(
        session,
        action=f"copilot.mcp.{spec.id}",
        entity_type="copilot_mcp_session",
        entity_id=grant.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
        payload={"tool": spec.id, "execution_mode": spec.execution_mode, "label": grant.label},
    )


def _authorize_write(session: Session, grant: CopilotMcpSession, spec: ToolSpec) -> None:
    """The two checks a write needs that a read does not.

    **The cutover fence.** `main.production_write_gate` decides from the HTTP
    method and path prefix. Every MCP call is one POST to one path, so that
    middleware cannot tell a read from a write here and would have to either
    block the whole surface or exempt it. Exempting it would be a way around the
    fence, so the check moves to the only place that knows which it is: the
    tool's own execution mode.

    **The issuer's current authority.** A grant carries its issuer's authority
    and no more, so it has to be re-checked rather than captured at issue time -
    a researcher demoted to viewer after issuing one would otherwise keep writing
    through it until it expired. Read tools are left to RLS, which already fences
    them per statement; this is about the role, which RLS does not model.
    """
    if spec.execution_mode == "read":
        return
    if not get_settings().writes_enabled:
        raise DomainError(
            "writes_disabled",
            "BDA v2 writes are disabled for cutover validation",
            status_code=503,
        )
    from ..projects.service import require_project_permission

    _, user = _actors(session, grant)
    require_project_permission(session, grant.project_id, user, "write")


def describe(session: Session, grant: CopilotMcpSession) -> dict[str, Any]:
    """What this grant currently is, for the issuing human rather than the model."""
    run = bound_run(session, grant)
    tools = available_tools(session, grant)
    return {
        "session_id": str(grant.id),
        "project_id": str(grant.project_id),
        "agent_run_id": str(grant.agent_run_id) if grant.agent_run_id else None,
        "mandate_live": run is not None,
        "capabilities": sorted(granted_capabilities(session, grant)),
        "tools": [spec.id for spec in tools],
        "write_tools": [spec.id for spec in tools if spec.execution_mode != "read"],
    }


def tool_listing(specs: list[ToolSpec]) -> list[dict[str, Any]]:
    """Registry specs in MCP's `tools/list` shape.

    `inputSchema` is `ToolSpec.parameters` unchanged - the same JSON Schema the
    internal loop hands its provider. Two consumers, one declaration.
    """
    return [
        {
            "name": spec.id,
            "description": spec.description,
            "inputSchema": spec.parameters,
            "annotations": {"readOnlyHint": spec.execution_mode == "read"},
        }
        for spec in specs
    ]
