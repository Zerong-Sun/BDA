"""The copilot tool registry.

These tests exist because the previous arrangement could drift silently: a tool
declared in one of its three places and missed in another was either unreachable
or, worse, reachable without its capability check. Asserting the registry is the
single source is what keeps that from coming back.
"""

from __future__ import annotations

import pytest
from backend_v2.app.copilot import tools  # noqa: F401  (registers the catalogue)
from backend_v2.app.copilot.registry import REGISTRY, ToolContext, ToolRegistry, ToolSpec
from backend_v2.app.core.problem import DomainError

#: Every tool the pre-registry dispatch chain in research_agent._execute handled.
#: Losing one would silently remove a capability, so the list is pinned here.
LEGACY_TOOLS = {
    "list_project_targets",
    "list_project_candidates",
    "list_experiment_results",
    "get_workflow_status",
    "get_compute_status",
    "search_project_knowledge",
    "resolve_research_gaps",
    "start_literature_search",
    "start_target_intelligence",
    "create_knowledge_draft",
    "create_compute_draft",
    "research_overview",
    "search_research",
    "get_research_items",
    "get_dataset_slice",
    "get_reference",
    "get_reference_content",
}


def test_every_legacy_tool_survived_the_move() -> None:
    assert LEGACY_TOOLS <= REGISTRY.ids()


def test_the_registry_is_the_only_place_a_tool_is_declared() -> None:
    """Schema, capability and handler come from one object, so they cannot disagree."""
    for spec in REGISTRY.all():
        schema = spec.schema()
        assert schema["function"]["name"] == spec.id
        assert schema["function"]["parameters"]["type"] == "object"
        assert spec.capability
        assert spec.execution_mode in {"read", "draft", "queue"}
        assert callable(spec.handler)


def test_writes_are_audited_and_reads_are_not() -> None:
    """An audit row per read would bury the writes worth finding."""
    for spec in REGISTRY.all():
        if spec.execution_mode == "read":
            assert not spec.audit, f"{spec.id} is a read but is marked audited"
        else:
            assert spec.audit, f"{spec.id} writes but is not audited"


def test_capability_manifest_marks_every_write_capability_explicit_request() -> None:
    manifest = REGISTRY.capability_manifest()
    for entry in manifest.values():
        if entry["execution_mode"] != "read":
            assert entry.get("requires_explicit_request") is True


def test_schemas_are_filtered_by_capability() -> None:
    granted = {"project-read"}
    ids = {schema["function"]["name"] for schema in REGISTRY.schemas_for(granted)}
    assert "list_project_candidates" in ids
    # A capability the session does not hold contributes nothing to the prompt,
    # so the model is never told about a tool it may not call.
    assert "create_compute_draft" not in ids
    assert "list_proteins" not in ids


def test_execute_refuses_a_tool_the_session_was_not_granted() -> None:
    with pytest.raises(DomainError) as raised:
        REGISTRY.execute(
            "create_knowledge_draft",
            ToolContext(actions=object()),
            {"title": "t", "content": "c"},
            granted={"project-read"},
        )
    assert raised.value.error_code == "copilot_capability_not_enabled"
    assert raised.value.status_code == 403


def test_execute_refuses_an_unknown_tool() -> None:
    with pytest.raises(DomainError) as raised:
        REGISTRY.execute("drop_database", ToolContext(), {})
    assert raised.value.error_code == "copilot_unknown_tool"


def test_execute_refuses_when_the_required_service_is_absent() -> None:
    """The old chain checked this inside each handler and kept forgetting one."""
    with pytest.raises(DomainError) as raised:
        REGISTRY.execute("list_project_targets", ToolContext(project=None), {})
    assert raised.value.error_code == "copilot_service_not_available"


def test_a_granted_tool_runs_through_the_single_dispatch_point() -> None:
    class FakeProject:
        def list_targets(self, limit: int) -> list[dict[str, int]]:
            return [{"limit": limit}]

    result = REGISTRY.execute(
        "list_project_targets",
        ToolContext(project=FakeProject()),
        {"limit": 7},
        granted={"project-read"},
    )
    assert result == [{"limit": 7}]


def test_duplicate_registration_is_rejected() -> None:
    """Two tools under one name would make dispatch depend on import order."""
    registry = ToolRegistry()
    spec = ToolSpec(
        id="only-once",
        description="",
        parameters={"type": "object", "properties": {}},
        capability="x",
        execution_mode="read",
        requires="session",
        handler=lambda ctx, args: None,
    )
    registry.register(spec)
    with pytest.raises(ValueError, match="duplicate"):
        registry.register(spec)


def test_sequences_are_unreachable_through_any_tool() -> None:
    """The bench tools must not become a way to read plaintext out of the library."""
    for spec in REGISTRY.all():
        properties = spec.parameters.get("properties", {})
        assert "sequence" not in properties, f"{spec.id} accepts a sequence argument"


# --- The manifest and the registry must not drift ----------------------------


def test_every_capability_tool_exists_in_the_registry() -> None:
    """A capability naming a tool that does not exist grants nothing, silently."""
    from backend_v2.app.copilot.capabilities import COPILOT_CAPABILITIES

    unknown = {
        (capability["id"], tool)
        for capability in COPILOT_CAPABILITIES
        for tool in capability.get("chat_tools", [])
        if tool not in REGISTRY.ids()
    }
    assert not unknown, f"capabilities name tools that do not exist: {sorted(unknown)}"


def test_every_registered_tool_is_reachable_from_some_capability() -> None:
    """A tool nothing grants is dead code that still looks like a feature."""
    from backend_v2.app.copilot.capabilities import COPILOT_CAPABILITIES

    granted = {
        tool for capability in COPILOT_CAPABILITIES for tool in capability.get("chat_tools", [])
    }
    orphans = REGISTRY.ids() - granted
    assert not orphans, f"tools no capability grants: {sorted(orphans)}"


def test_a_default_session_can_reach_the_wet_bench() -> None:
    """The wet half of the loop is useless to the agent if nothing grants it."""
    from backend_v2.app.copilot.capabilities import normalize_capabilities, tools_for_capabilities

    available = tools_for_capabilities(normalize_capabilities(None))
    assert {"list_proteins", "compute_concentration", "plan_dilution_series"} <= available
    assert "list_research_goals" in available
