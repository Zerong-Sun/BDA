"""What a chat turn may offer, and that it matches what a chat turn may run.

These exist because the two had silently disagreed. `research_agent` advertised
tools from three hand-written schema lists while `_execute` dispatched through
`REGISTRY`, so a tool could be perfectly callable and never offered. Thirteen
were: every tool needing only a session - the bench tools, the research-goal
tools, and the whole structure and diagnosis surface - because no fourth list was
ever written for them. Nothing failed; the tools simply did not exist as far as
the model could tell, which is the exact failure `registry.py` was written to end
and which no test was watching for.

So the assertions here are about *agreement between surfaces*, not about any one
tool. A new tool must become offerable by being registered, and a new write must
become gated by being registered, or these fail.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from backend_v2.app.copilot import research_agent
from backend_v2.app.copilot import tools as _tools  # noqa: F401  (registers the catalogue)
from backend_v2.app.copilot.actions import _ACTION_REQUEST_TERMS, CopilotActionService
from backend_v2.app.copilot.capabilities import normalize_capabilities, tools_for_capabilities
from backend_v2.app.copilot.registry import REGISTRY

#: A turn with every service present, which is what an ordinary project chat has.
FULL_TURN = {
    "has_research": True,
    "has_project": True,
    "has_actions": True,
    "has_session": True,
}


def _names(**overrides) -> set[str]:
    kwargs = {**FULL_TURN, "allowed_tools": None, "has_operator": True, **overrides}
    return {schema["function"]["name"] for schema in research_agent.chat_schemas(**kwargs)}


# --- Offered matches runnable ------------------------------------------------


def test_every_registry_tool_chat_can_run_is_also_offered() -> None:
    """The regression that started this file.

    `requires="agent_run"` tools are the only legitimate absence: an MCP client
    or a chat turn has no run to suspend.
    """
    runnable = {spec.id for spec in REGISTRY.all() if spec.requires != "agent_run"}

    assert _names() == runnable


def test_agent_run_tools_are_never_offered_in_chat() -> None:
    offered = _names()

    assert "await_compute_job" not in offered
    assert "spawn_subagent" not in offered


def test_the_structure_and_diagnosis_tools_are_reachable_from_chat() -> None:
    """Named explicitly because their absence made two bots inert.

    `planner` resolved its capabilities, passed the narrowing law and
    appeared in the picker while having none of its tools; `runner` kept
    `get_compute_status` and lost the tool that says *why* a job failed.
    """
    offered = _names()

    for bot_tools in (
        tools_for_capabilities({"project-read", "structure-analysis"}),
        tools_for_capabilities({"project-read", "failure-diagnosis"}),
    ):
        assert bot_tools <= offered, sorted(bot_tools - offered)


def test_a_missing_service_withdraws_exactly_the_tools_that_need_it() -> None:
    """Availability is decided by the same `requires` rule `execute` enforces.

    This also pins the behaviour the three hand-written lists used to have, so
    the 17 tools that did work still gain and lose availability at the same
    moments.
    """
    for attribute, requires in (
        ("has_research", "research"),
        ("has_project", "project"),
        ("has_actions", "actions"),
        ("has_session", "session"),
    ):
        without = _names(**{attribute: False})
        withdrawn = _names() - without
        assert withdrawn == {spec.id for spec in REGISTRY.all() if spec.requires == requires}


def test_allowed_tools_still_narrows_the_offer() -> None:
    assert _names(allowed_tools={"research_overview"}) == {"research_overview"}
    assert _names(allowed_tools=set()) == set()


def test_an_allowed_tool_the_turn_cannot_run_is_not_offered() -> None:
    """`allowed_tools` narrows; it never grants.

    A capability set naming an agent-run tool must not make it offerable in a
    turn that has no run to suspend.
    """
    assert _names(allowed_tools={"await_compute_job", "research_overview"}) == {"research_overview"}


# --- The write gate ----------------------------------------------------------


def test_the_write_gate_covers_every_write_the_registry_has() -> None:
    """The hand-written version named five of ten.

    That was harmless only while the other five were unreachable. `tasks.py`
    filters exactly this set through the user's own words, so a write missing
    from it is a write the model could call on a turn nobody asked for one.
    """
    assert research_agent.WRITE_TOOL_NAMES == REGISTRY.user_intent_write_ids()
    assert "analyse_bli_run" in research_agent.WRITE_TOOL_NAMES
    assert "promote_candidate_to_bench" in research_agent.WRITE_TOOL_NAMES
    assert "attach_to_research_goal" in research_agent.WRITE_TOOL_NAMES


def test_the_only_writes_outside_the_intent_gate_are_copilot_bookkeeping() -> None:
    """The exemption is an argument about one table, not a category to grow.

    `intent="internal"` means the tool changes no research record, so the gate
    that reads the user's words has nothing to protect. Pinning the membership
    here makes adding a second exemption a deliberate edit with this test in
    front of it, rather than a default a new spec falls into.

    The second member was added with that edit. `request_decision` writes a
    question for a person to answer: the row is copilot bookkeeping, no
    research record moves, and the timeline entry is written later by
    `decisions.answer`, which requires a `User` and is unreachable from any
    tool. Asking somebody a question is also not an action taken on their
    behalf, which is what the intent gate exists to stop.
    """
    exempt = REGISTRY.write_ids() - REGISTRY.user_intent_write_ids()

    assert exempt == {"post_handoff", "request_decision"}


def test_the_conservative_write_set_is_what_a_read_only_surface_gets() -> None:
    """`mcp.available_tools` degrades an unbound grant with `write_ids`.

    Written down because the two sets differ by exactly the tool a read-only
    surface would most easily be given by accident: a draft-mode write whose
    intent gate does not apply.
    """
    assert REGISTRY.user_intent_write_ids() < REGISTRY.write_ids()
    assert "post_handoff" in REGISTRY.write_ids()


def test_no_read_tool_is_in_the_write_gate() -> None:
    reads = {spec.id for spec in REGISTRY.all() if spec.execution_mode == "read"}

    assert not (research_agent.WRITE_TOOL_NAMES & reads)


def _allows(text: str, action: str) -> bool:
    """`request_allows` reads only `request_text`, so this is the whole of it."""
    return CopilotActionService.request_allows(SimpleNamespace(request_text=text, authorized_writes=None), action)


@pytest.mark.parametrize("write", sorted(REGISTRY.write_ids()))
def test_every_write_answers_the_intent_check_without_raising(write: str) -> None:
    """Deny by default, never KeyError.

    The gate is reached for every write now, including ones whose bilingual
    request vocabulary nobody has written. Raising would take the whole turn
    down; allowing would run a write nobody asked for.
    """
    assert _allows("please do the thing", write) in {True, False}


def test_a_write_with_no_declared_vocabulary_is_denied_and_therefore_not_offered() -> None:
    """The five bench and trace writes are in this state today.

    Denied rather than listed-and-refused: `tasks.py` drops a write the request
    does not authorise from `allowed_tools`, so the model is never shown a tool
    that would always say no. Giving one of these an entry in
    `_ACTION_REQUEST_TERMS` is what turns it on, deliberately.
    """
    ungoverned = REGISTRY.write_ids() - set(_ACTION_REQUEST_TERMS)

    assert ungoverned, "if this is empty the test below no longer proves anything"
    for write in ungoverned:
        assert _allows("please analyse the BLI run and promote the candidate", write) is False


def test_a_governed_write_still_needs_the_users_own_words() -> None:
    assert _allows("please run a literature search on PD-1", "start_literature_search") is True
    assert _allows("do not search the literature", "start_literature_search") is False
    assert _allows("what is PD-1?", "start_literature_search") is False


# --- Capability declarations agree with the registry -------------------------


def test_capability_chat_tools_are_all_real_registry_tools() -> None:
    """A capability naming a tool that does not exist grants nothing silently."""
    declared = tools_for_capabilities(normalize_capabilities(["research"]))

    assert declared <= REGISTRY.ids(), sorted(declared - REGISTRY.ids())


# --- Tools that need an operator ---------------------------------------------


def test_a_turn_with_no_operator_is_not_offered_the_tools_that_need_one() -> None:
    """The same rule as `requires`, one axis over.

    A handover whose sender is "the assistant" names nobody accountable, so an
    unhinted turn cannot post one. Offering it anyway would put a guaranteed
    failure in front of the model - the exact state this module's other tests
    exist to prevent.
    """
    needs = {spec.id for spec in REGISTRY.all() if spec.needs_operator}

    assert needs, "if this is empty the assertion below proves nothing"
    assert needs & _names(), "an owned turn still gets them"
    assert not (needs & _names(has_operator=False))


def test_reading_the_roster_never_needs_an_operator() -> None:
    """A turn that has not chosen one is the likeliest to be asking who they are."""
    unowned = _names(has_operator=False)

    assert "list_operators" in unowned
    assert "read_handoffs" in unowned


def test_withdrawing_the_operator_withdraws_nothing_else() -> None:
    """Bounded, so a future `needs_operator` cannot quietly take a tool with it.

    Compared against the tools chat offers at all: `delegate_to_operator` also
    needs an operator and is already absent, because it needs a run to own the
    child it opens.
    """
    withdrawn = _names() - _names(has_operator=False)

    assert withdrawn == {spec.id for spec in REGISTRY.all() if spec.needs_operator} & _names()
