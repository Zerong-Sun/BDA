from backend_v2.app.copilot.capabilities import (
    capabilities_for_turn,
    normalize_capabilities,
    research_kinds_for_capabilities,
    tools_for_capabilities,
)


def test_skill_hint_narrows_enabled_capabilities() -> None:
    enabled = normalize_capabilities(["research"])

    active = capabilities_for_turn(enabled, "literature-search")

    assert active == {"literature-search"}
    assert tools_for_capabilities(active) == {"start_literature_search"}


def test_skill_hint_never_grants_a_disabled_capability() -> None:
    enabled = normalize_capabilities(["project-read"])

    active = capabilities_for_turn(enabled, "compute-drafting")

    assert active == set()
    assert tools_for_capabilities(active) == set()


def test_turn_without_hint_retains_configured_capability_ceiling() -> None:
    enabled = normalize_capabilities(["project-read", "result-interpretation"])

    assert capabilities_for_turn(enabled, None) == enabled


def test_compute_turn_can_read_state_without_gaining_submit_access() -> None:
    enabled = normalize_capabilities(["compute-drafting"])

    tools = tools_for_capabilities(capabilities_for_turn(enabled, "compute-drafting"))

    assert tools == {"get_compute_status", "create_compute_draft"}
    assert "confirm_compute_draft" not in tools
    assert "submit_compute_draft" not in tools


def test_gap_repair_turn_can_resolve_only_research_targets() -> None:
    capabilities = {"research-gap-repair"}

    assert research_kinds_for_capabilities(capabilities) == {"research_target"}
    assert research_kinds_for_capabilities({"research-read"}) is None
