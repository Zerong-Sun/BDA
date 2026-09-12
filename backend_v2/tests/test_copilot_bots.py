"""The roster's one law, attacked from every direction it could be broken.

`bots.narrow` is a hint. Hints are the classic place a narrowing control turns
into a widening one, because the failure is silent: an unknown id, a conflicting
pair, or a bot naming a capability the project never enabled all have an obvious
"be helpful" answer that hands back more than was authorised. Each test below is
one of those answers, asserted not to happen.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.copilot import agent_loop, agent_runs, bots
from backend_v2.app.copilot.capabilities import (
    capability_ids,
    normalize_capabilities,
    tools_for_capabilities,
)
from backend_v2.app.copilot.models import CopilotConfig
from backend_v2.app.copilot.schemas import AgentRunCreate
from backend_v2.app.copilot.service import start_agent_run
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ALL_CAPABILITIES = normalize_capabilities(["research"])


# --- The declaration is internally consistent --------------------------------


def test_every_bot_declares_registered_capabilities() -> None:
    known = capability_ids()
    for bot in bots.all_bots():
        assert set(bot.capabilities) <= known, bot.id
        assert bot.capabilities, bot.id


def test_every_handoff_names_an_existing_bot() -> None:
    ids = bots.bot_ids()
    for bot in bots.all_bots():
        assert set(bot.handoff) <= ids, bot.id


def test_roster_is_returned_in_chain_order() -> None:
    phases = [bot.phase for bot in bots.all_bots()]
    assert phases == sorted(phases)


def test_every_bot_grants_at_least_one_tool_when_everything_is_enabled() -> None:
    """A bot whose capabilities grant nothing is a bot that cannot act.

    It would look configured and answer every request with "I have no tools",
    which is the least debuggable kind of broken.
    """
    for bot in bots.all_bots():
        granted = tools_for_capabilities(bots.capabilities_for_bot(bot.id, ALL_CAPABILITIES))
        assert granted, bot.id


def test_charters_state_refusals_rather_than_only_duties() -> None:
    """The charter is the part a capability list cannot express.

    A charter with no prohibition is documentation, and the model will read it
    as encouragement. This asserts the shape, not the wording.
    """
    for bot in bots.all_bots():
        lowered = bot.charter.lower()
        assert any(word in lowered for word in ("never", "not ", "cannot", "do not")), bot.id


# --- The narrowing law -------------------------------------------------------


def test_bot_capabilities_are_an_intersection_for_every_bot_and_every_subset() -> None:
    """The law itself: resolved == declared ∩ enabled, for all of them."""
    for bot in bots.all_bots():
        for enabled in (
            ALL_CAPABILITIES,
            {"project-read"},
            {"project-read", "research-read"},
            set(),
        ):
            resolved = bots.capabilities_for_bot(bot.id, enabled)
            assert resolved == set(bot.capabilities) & enabled
            assert resolved <= enabled
            assert resolved <= set(bot.capabilities)


def test_a_bot_cannot_reach_a_capability_the_project_disabled() -> None:
    enabled = normalize_capabilities(["project-read"])

    resolved = bots.capabilities_for_bot("planner", enabled)

    assert "compute-drafting" not in resolved
    assert "create_compute_draft" not in tools_for_capabilities(resolved)


def test_a_project_with_everything_enabled_still_only_gets_what_the_bot_declares() -> None:
    resolved = bots.capabilities_for_bot("structuralist", ALL_CAPABILITIES)

    assert resolved == {"project-read", "structure-analysis"}
    granted = tools_for_capabilities(resolved)
    assert "start_literature_search" not in granted
    assert "create_compute_draft" not in granted
    assert "attach_to_research_goal" not in granted


def test_unknown_bot_hint_yields_nothing_rather_than_everything() -> None:
    """The failure this test exists for.

    Falling back to the enabled set on an unrecognised id would turn a typo
    into a turn with the project's full capability ceiling.
    """
    assert bots.narrow(ALL_CAPABILITIES, bot_hint="no-such-bot") == set()
    assert bots.narrow(ALL_CAPABILITIES, bot_hint="Planner") == set()  # case matters
    assert bots.narrow(ALL_CAPABILITIES, bot_hint="planner ") == set()


def test_two_hints_in_one_turn_are_denied_rather_than_merged() -> None:
    merged = bots.narrow(ALL_CAPABILITIES, skill_hint="compute-drafting", bot_hint="librarian")

    assert merged == set()


def test_no_hint_leaves_the_project_ceiling_untouched() -> None:
    assert bots.narrow(ALL_CAPABILITIES) == ALL_CAPABILITIES


def test_narrow_never_returns_more_than_it_was_given() -> None:
    hints: list[dict[str, str | None]] = [{"skill_hint": None, "bot_hint": None}]
    hints += [{"bot_hint": bot.id} for bot in bots.all_bots()]
    hints += [{"skill_hint": capability} for capability in sorted(capability_ids())]
    hints += [{"bot_hint": "planner", "skill_hint": "literature-search"}]
    hints += [{"bot_hint": ""}, {"bot_hint": "   "}]

    for enabled in (ALL_CAPABILITIES, {"project-read"}, set()):
        for hint in hints:
            assert bots.narrow(enabled, **hint) <= enabled  # type: ignore[arg-type]


# --- Lookup ------------------------------------------------------------------


def test_require_raises_not_found_for_an_unknown_bot() -> None:
    with pytest.raises(DomainError) as error:
        bots.require("ghost")

    assert error.value.status_code == 404


def test_capabilities_for_bot_refuses_an_unknown_bot_rather_than_returning_empty() -> None:
    """`narrow` answers empty for an unknown hint; `require`-backed lookup raises.

    The difference is deliberate: a hint arriving on a message is data that may
    be stale, and a run being created names a bot the caller chose. The first is
    ignored, the second is an error the caller must see.
    """
    with pytest.raises(DomainError):
        bots.capabilities_for_bot("ghost", ALL_CAPABILITIES)


# --- The roster covers the chain --------------------------------------------


def test_the_chain_has_an_owner_for_every_declared_capability() -> None:
    """No capability exists that no bot is accountable for.

    An unowned capability is one nobody's charter constrains: it stays reachable
    through the undifferentiated default and picks up none of the refusals the
    roster exists to state.
    """
    owned = {capability for bot in bots.all_bots() for capability in bot.capabilities}

    assert capability_ids() - owned == set()


def test_write_capabilities_are_not_spread_across_the_whole_roster() -> None:
    """Draft and queue capabilities belong to the phase that owns them.

    If every bot could draft compute, selecting a bot would stop meaning
    anything, and the narrowing law would be technically true and practically
    empty.
    """
    for capability in ("compute-drafting", "literature-search", "research-trace-authoring"):
        holders = [bot.id for bot in bots.all_bots() if capability in bot.capabilities]
        assert len(holders) == 1, (capability, holders)


# --- Through the service: a run created for a bot ----------------------------


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


def _project(session: Session, *, enabled_skills: list[str] | None = None) -> tuple[Project, User]:
    n = next(_counter)
    user = User(username=f"bot-{n}", display_name="Bot", role="editor", enabled=True)
    organization = Organization(name=f"Bot Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id,
        owner_id=user.id,
        name=f"bot-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    if enabled_skills is not None:
        session.add(CopilotConfig(project_id=project.id, enabled_skills=enabled_skills))
        session.flush()
    return project, user


def _run(session: Session, project: Project, user: User, **payload_fields):
    return start_agent_run(
        session,
        project,
        user,
        AgentRunCreate(project_id=project.id, goal="find out", **payload_fields),
    )[0]


def test_a_run_created_for_a_bot_gets_exactly_that_bots_tools(session: Session) -> None:
    project, user = _project(session, enabled_skills=["research"])

    run = _run(session, project, user, bot="structuralist")

    assert set(run.allowed_tools) == tools_for_capabilities(
        {"project-read", "structure-analysis"}
    )
    assert "analyse_structure" in run.allowed_tools
    assert "create_compute_draft" not in run.allowed_tools


def test_a_bot_run_cannot_exceed_what_the_project_enabled(session: Session) -> None:
    """The escalation this whole design is shaped to prevent.

    `planner` declares compute-drafting. A project that has not enabled it must
    get a planner run without it, rather than a planner run that quietly can.
    """
    project, user = _project(session, enabled_skills=["project-read", "workflow-planning"])

    run = _run(session, project, user, bot="planner")

    assert "create_compute_draft" not in run.allowed_tools
    assert set(run.allowed_tools) <= tools_for_capabilities(
        normalize_capabilities(["project-read", "workflow-planning"])
    )


def test_an_unknown_bot_is_rejected_rather_than_defaulted(session: Session) -> None:
    project, user = _project(session, enabled_skills=["research"])

    with pytest.raises(DomainError) as error:
        _run(session, project, user, bot="ghost")

    assert error.value.status_code == 404


def test_a_bot_and_an_explicit_skill_list_together_are_rejected(session: Session) -> None:
    project, user = _project(session, enabled_skills=["research"])

    with pytest.raises(DomainError) as error:
        _run(session, project, user, bot="planner", skills=["literature-search"])

    assert error.value.error_code == "copilot_hint_conflict"
    assert error.value.status_code == 422


def test_a_bot_whose_capabilities_are_all_disabled_is_refused_not_silently_empty(
    session: Session,
) -> None:
    """An empty intersection must not become a run with the project default.

    Nor a run with no tools: `start_agent_run` already refuses those, and
    reporting the reason as "no capability enabled for this bot" is what tells
    the user which switch to turn on.
    """
    project, user = _project(session, enabled_skills=["project-read"])

    with pytest.raises(DomainError) as error:
        _run(session, project, user, bot="librarian")

    assert error.value.error_code == "copilot_capability_disabled"
    assert error.value.status_code == 422


def test_no_bot_still_yields_the_projects_full_configured_set(session: Session) -> None:
    project, user = _project(session, enabled_skills=["project-read", "research-read"])

    run = _run(session, project, user)

    assert set(run.allowed_tools) == tools_for_capabilities(
        normalize_capabilities(["project-read", "research-read"])
    )


# --- The import-time guard ---------------------------------------------------
# `_validate_roster` runs once at import and can therefore never be exercised by
# the roster that exists. These call it against deliberately broken rosters,
# because a guard nobody has seen fire is a guard nobody knows works.


def _spec(**overrides) -> bots.BotSpec:
    base = {
        "id": "probe",
        "title": "Probe",
        "title_zh": "探针",
        "phase": 0,
        "summary": "s",
        "charter": "c",
        "capabilities": ("project-read",),
        "handoff": (),
    }
    base.update(overrides)
    return bots.BotSpec(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("broken", "message"),
    [
        (_spec(capabilities=("not-a-capability",)), "unknown capabilities"),
        (_spec(capabilities=()), "no capabilities"),
        (_spec(handoff=("ghost",)), "unknown bots"),
    ],
)
def test_a_broken_roster_fails_at_import_rather_than_at_use(
    broken: bots.BotSpec, message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bots, "BOTS", (broken,))
    monkeypatch.setattr(bots, "_BY_ID", {broken.id: broken})

    with pytest.raises(ValueError, match=message):
        bots._validate_roster()


def test_get_returns_the_spec_or_none_without_raising() -> None:
    """`get` is what a replayed message context is resolved through.

    It must answer "no such bot" rather than raise, because a stale hint on an
    old row is data, not a caller error.
    """
    assert bots.get("medic") is not None
    assert bots.get("ghost") is None


# --- The charter reaches the run --------------------------------------------


def test_a_bot_run_carries_its_charter_into_every_turn(session: Session) -> None:
    """The half of a bot a capability list cannot express.

    Without this the two bots differ only in their tools, and two bots that
    share a tool set become the same operator - which is most of the roster.
    """
    project, user = _project(session, enabled_skills=["research"])
    run = _run(session, project, user, bot="medic")

    system = [
        message
        for message in agent_loop.messages_for(run, [])
        if message["role"] == "system"
    ]

    assert any("medic bot" in message["content"] for message in system)
    assert any("invented cause" in message["content"] for message in system)
    # And it narrows the loop policy rather than replacing it.
    assert any("BDA_AGENT_LOOP_V1" in message["content"] for message in system)


def test_a_run_without_a_bot_gets_the_loop_policy_and_nothing_else(session: Session) -> None:
    project, user = _project(session, enabled_skills=["research"])
    run = _run(session, project, user)

    system = [m for m in agent_loop.messages_for(run, []) if m["role"] == "system"]

    assert len(system) == 1


def test_a_bot_removed_from_the_roster_leaves_an_undifferentiated_run(session: Session) -> None:
    """A stale id must not break a run that is already in flight.

    The charter is read from source each turn, so an id the roster no longer
    knows contributes nothing rather than raising inside the loop.
    """
    project, user = _project(session, enabled_skills=["research"])
    run = _run(session, project, user, bot="analyst")
    run.bot = "retired-bot"

    system = [m for m in agent_loop.messages_for(run, []) if m["role"] == "system"]

    assert len(system) == 1


def test_a_subagent_inherits_its_parents_charter(session: Session) -> None:
    """A child doing part of the medic's work is still bound by the medic's refusals."""
    project, user = _project(session, enabled_skills=["research"])
    parent = _run(session, project, user, bot="medic")

    child = agent_runs.create_run(
        session,
        project_id=project.id,
        user_id=user.id,
        goal="check the attempt history",
        allowed_tools=list(parent.allowed_tools),
        parent_run_id=parent.id,
    )

    assert child.bot == "medic"
