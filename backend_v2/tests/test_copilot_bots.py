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
    COPILOT_CAPABILITIES,
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
    resolved = bots.capabilities_for_bot("runner", ALL_CAPABILITIES)

    assert resolved == {"project-read", "workflow-planning", "agent-orchestration", "failure-diagnosis", "chain-messaging"}
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
    merged = bots.narrow(ALL_CAPABILITIES, skill_hint="compute-drafting", bot_hint="researcher")

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


# --- Stance: the axis that separates responsibilities from tool sets ---------
# Capabilities say what an operator may touch. Stance says what it is *for*, and
# is the reason the roster is no longer nine names for one responsibility
# structure. These assert the relationships rather than any operator's contents.


def test_every_bot_declares_a_known_stance() -> None:
    for bot in bots.all_bots():
        assert bot.stance in bots.STANCES, bot.id


def test_the_chain_has_all_three_stances() -> None:
    """A roster of producers only is the state this axis was added to fix.

    Nine operators that all produce have nobody checking any of them and nobody
    deciding who works next, which is a split of functions however the charters
    are worded.
    """
    present = {bot.stance for bot in bots.all_bots()}

    assert present == set(bots.STANCES)


def test_every_producer_is_reviewed_by_someone() -> None:
    """Accountability is the fourth thing a capability list cannot say.

    An operator nobody reviews can make any claim it likes, and the charter it
    is breaking is the only thing standing in the way.
    """
    for bot in bots.producers():
        assert bots.reviewers_of(bot.id), bot.id


def test_a_producer_does_not_choose_its_own_reviewer() -> None:
    """`reviews` is declared on the reviewer, which is what makes that true."""
    for bot in bots.producers():
        assert bot.reviews == ()


def test_review_and_delegation_terminate_on_producers() -> None:
    """Otherwise there is no bottom: a reviewer reviewing a reviewer, or a
    director directing a director, never reaches the work."""
    for bot in bots.all_bots():
        for target in bot.reviews + bot.directs:
            assert bots.require(target).stance == "produce", (bot.id, target)


def test_no_reviewer_can_repair_what_it_finds() -> None:
    """The stance rule as a statement about capabilities rather than about the
    validator: a reviewer holding a write is a second producer, and nobody
    checks the second producer."""
    granting = {
        item["id"]
        for item in COPILOT_CAPABILITIES
        if item.get("execution_mode", "read") != "read"
    }
    for bot in bots.all_bots():
        if bot.stance not in {"review", "direct"}:
            continue
        writes = set(bot.capabilities) & granting
        # The handover channel is copilot bookkeeping, not a research write -
        # see `bots._INTERNAL_WRITE_CAPABILITIES`.
        assert writes <= {"chain-messaging"}, (bot.id, sorted(writes))


def test_every_operator_that_hands_off_can_leave_something_behind() -> None:
    """A handover with no channel is the defect the channel was added to fix.

    An operator whose charter says "hand this to runner" while holding no way to
    record what it is handing over describes a step the platform cannot take.
    """
    for bot in bots.all_bots():
        if not bot.handoff:
            continue
        assert "chain-messaging" in bot.capabilities, bot.id


def test_a_director_may_direct_only_what_it_declares() -> None:
    assert bots.may_direct("conductor", "planner") is True
    # Review is asked for, not ordered: a director able to open a review run
    # would be selecting its own reviewer.
    assert bots.may_direct("conductor", "auditor") is False
    assert bots.may_direct("planner", "runner") is False
    assert bots.may_direct("ghost", "planner") is False


def test_orchestration_and_review_powers_belong_to_one_stance_each() -> None:
    for capability, stance in bots._STANCE_ONLY.items():
        holders = [bot for bot in bots.all_bots() if capability in bot.capabilities]
        assert holders, capability
        assert all(bot.stance == stance for bot in holders), capability


# --- Triggers: the routing vocabulary the frontend used to keep its own copy of
# The client had a second, hand-written capability list with its own bilingual
# triggers. Retiring it moved that vocabulary here, where the roster it describes
# already lives. These guard the two ways that move could go wrong.


def test_no_two_operators_claim_the_same_trigger() -> None:
    """A tie routes to nobody, so a shared token makes both unroutable.

    `researcher` and `auditor` both claimed "review" for one commit - one meaning
    a review article, the other the act - and the word that names each of them
    stopped naming either.
    """
    owners: dict[str, list[str]] = {}
    for bot in bots.all_bots():
        for token in bot.triggers:
            owners.setdefault(token.lower(), []).append(bot.id)

    shared = {token: ids for token, ids in owners.items() if len(ids) > 1}
    assert not shared, shared


def test_a_trigger_containing_another_operators_trigger_is_deliberate() -> None:
    """Substring matching means the long phrase always drags the short one in.

    The client resolves this by discarding a matched token that another matched
    token contains, so these pairs route to the longer one. Listed rather than
    forbidden, because "literature review" has to be able to outrank "review" -
    but a new pair should be a decision, not a surprise.
    """
    tokens = [(token.lower(), bot.id) for bot in bots.all_bots() for token in bot.triggers]
    nested = {
        (long, long_bot, short, short_bot)
        for long, long_bot in tokens
        for short, short_bot in tokens
        if long_bot != short_bot and short != long and short in long
    }

    assert nested == {
        ("review article", "researcher", "review", "auditor"),
        ("literature review", "researcher", "review", "auditor"),
        # 链 is one character and sits inside 全链条; the director wins, which is
        # right - "全链条" is a request to run the chain, not to read a chain of
        # a structure.
        ("全链条", "conductor", "链", "planner"),
    }


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        # Each of these was a case the retired skill registry routed. They are
        # here so the merge is provably not a loss of routing.
        ("Adjust the workflow threshold", "planner"),
        ("调整工作流阈值", "planner"),
        ("请补齐 Research target 的 gaps", "researcher"),
        ("run the target intelligence", "researcher"),
        ("跑一下靶点情报", "researcher"),
        ("create a compute draft", "planner"),
        ("生成计算草稿", "planner"),
        ("How should RFdiffusion connect to a protein workflow?", "planner"),
        ("Interpret the BLI experiment", "analyst"),
        ("save this to knowledge", "analyst"),
        ("保存到知识库", "analyst"),
        ("整理一下这些文献", "researcher"),
        ("find the reference", "researcher"),
    ],
)
def test_the_retired_skill_registrys_routing_still_resolves(message: str, expected: str) -> None:
    """Server-side mirror of the client matcher, applied to the roster.

    The client is where routing happens; this asserts the *vocabulary* is
    present and unambiguous, which is the half that lives here.
    """
    lowered = message.lower()
    hits = [
        (token.lower(), bot.id)
        for bot in bots.all_bots()
        for token in bot.triggers
        if token.lower() in lowered
    ]
    surviving = {
        bot_id
        for token, bot_id in hits
        if not any(other != token and token in other for other, _ in hits)
    }

    assert surviving == {expected}, sorted(hits)


def test_no_trigger_is_a_bare_common_verb() -> None:
    """A token that matches most sentences names nobody.

    `runner` claimed "run" for one commit, which is the verb in nearly every
    imperative a user types - so "run the target intelligence" tied `runner`
    against `researcher` and routed to neither. The vocabulary has to name each
    operator's subject, not the act of asking.
    """
    swamping = {"run", "do", "get", "make", "show", "find", "use", "set", "add", "go"}

    for bot in bots.all_bots():
        offending = {token.lower() for token in bot.triggers} & swamping
        assert not offending, (bot.id, sorted(offending))


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

    run = _run(session, project, user, bot="planner")

    assert set(run.allowed_tools) == tools_for_capabilities(
        set(bots.require("planner").capabilities) & normalize_capabilities(["research"])
    )
    assert "analyse_structure" in run.allowed_tools
    # Another producer's write stays with that producer.
    assert "start_literature_search" not in run.allowed_tools


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
    project, user = _project(session, enabled_skills=["wetlab-read"])

    with pytest.raises(DomainError) as error:
        _run(session, project, user, bot="researcher")

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
        "stance": "produce",
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
        (_spec(stance="supervisor"), "unknown stance"),
        # The stance rules, each stated as the roster error it produces. These
        # are the whole of what makes stance more than a label: without them a
        # reviewer holding a write is a reviewer that repairs its own findings,
        # and a director holding one is an operator that does the work it was
        # meant to route.
        (
            _spec(
                stance="review",
                capabilities=("project-read", "knowledge-authoring"),
                reviews=("planner",),
            ),
            "second producer",
        ),
        (
            _spec(
                stance="direct",
                capabilities=("chain-orchestration", "compute-drafting"),
                directs=("planner",),
            ),
            "will do the work",
        ),
        (
            _spec(stance="produce", capabilities=("project-read", "review-audit")),
            "belongs to the review stance",
        ),
        (
            _spec(stance="produce", capabilities=("project-read", "chain-orchestration")),
            "belongs to the direct stance",
        ),
        (_spec(stance="review", capabilities=("review-audit",)), "names nobody to review"),
        (
            _spec(stance="direct", capabilities=("chain-orchestration",)),
            "names nobody to direct",
        ),
        (_spec(reviews=("planner",)), "cannot review other operators"),
        (_spec(directs=("planner",)), "cannot direct other operators"),
        (
            _spec(stance="review", capabilities=("review-audit",), reviews=("ghost",)),
            "unknown operator",
        ),
        (_spec(task_services=("not-a-service",)), "unknown task service"),
        (
            _spec(stance="review", capabilities=("review-audit",), reviews=("planner",), task_services=("brief",)),
            "only a producer delivers",
        ),
        # Owning a recipe whose steps the owner cannot call would be a task that
        # is assigned to someone and can never be delivered by them.
        (_spec(task_services=("planning",)), "cannot reach its steps"),
    ],
)
def test_a_broken_roster_fails_at_import_rather_than_at_use(
    broken: bots.BotSpec, message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The real roster stays reachable by id so that a `reviews`/`directs` target
    # naming a live operator resolves; only the bot under test is broken.
    monkeypatch.setattr(bots, "BOTS", (broken,))
    monkeypatch.setattr(bots, "_BY_ID", {**bots._BY_ID, broken.id: broken})

    with pytest.raises(ValueError, match=message):
        bots._validate_roster()


def test_every_guided_task_has_exactly_one_producing_owner() -> None:
    from backend_v2.app.copilot.task_contracts import SERVICES

    owners = {kind: [bot.id for bot in bots.BOTS if kind in bot.task_services] for kind in SERVICES}

    assert all(len(ids) == 1 for ids in owners.values()), owners
    assert {bots.get(ids[0]).stance for ids in owners.values()} == {"produce"}  # type: ignore[union-attr]


def test_a_recipe_with_two_owners_fails_at_import(monkeypatch: pytest.MonkeyPatch) -> None:
    rival = _spec(id="rival", capabilities=("project-read", "research-read"), task_services=("brief",))
    monkeypatch.setattr(bots, "BOTS", (*bots.BOTS, rival))
    monkeypatch.setattr(bots, "_BY_ID", {**bots._BY_ID, rival.id: rival})

    with pytest.raises(ValueError, match="exactly one owning bot"):
        bots._validate_roster()


def test_an_owner_is_offered_only_the_writes_it_can_be_granted() -> None:
    # Per owned recipe: the researcher answers for both the brief (no writes) and
    # the literature review (search and pending-review notes); a reviewer owns none.
    assert bots.task_write_tools(bots.require("researcher")) == {
        "brief": [],
        "literature": ["start_literature_search", "create_knowledge_draft"],
    }
    assert bots.task_write_tools(bots.require("auditor")) == {}


def test_retired_ids_resolve_for_history_but_cannot_be_addressed() -> None:
    # A run or handover recorded under a retired id keeps an operator to read...
    assert bots.get("scout") is bots.require("researcher")
    assert bots.absorbed_by("researcher") == ["briefing", "librarian", "scout"]
    # ...but nothing new starts under the old name, and the refusal says where to go.
    with pytest.raises(DomainError) as error:
        bots.require("medic")
    assert error.value.error_code == "copilot_bot_retired"
    assert "runner" in str(error.value.detail)
    # A retired hint narrows to nothing rather than to its successor's wider set.
    assert bots.narrow(ALL_CAPABILITIES, bot_hint="structuralist") == set()


def test_a_guided_task_assigned_to_a_non_owner_is_refused(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend_v2.app.copilot import qualification

    monkeypatch.setattr(qualification, "readiness", lambda *a: {"eligible_services": ["literature", "planning"]})
    project, user = _project(session, enabled_skills=["research"])

    with pytest.raises(DomainError) as error:
        _run(session, project, user, bot="planner", service_kind="literature")
    assert error.value.error_code == "copilot_task_owner_mismatch"
    assert error.value.status_code == 422

    run = _run(session, project, user, bot="researcher", service_kind="literature", authorized_writes=[])
    assert run.bot == "researcher"
    assert run.task_contract["service_kind"] == "literature"


def test_get_returns_the_spec_or_none_without_raising() -> None:
    """`get` is what a replayed message context is resolved through.

    It must answer "no such bot" rather than raise, because a stale hint on an
    old row is data, not a caller error.
    """
    assert bots.get("runner") is not None
    assert bots.get("ghost") is None


# --- The charter reaches the run --------------------------------------------


def test_a_bot_run_carries_its_charter_into_every_turn(session: Session) -> None:
    """The half of a bot a capability list cannot express.

    Without this the two bots differ only in their tools, and two bots that
    share a tool set become the same operator - which is most of the roster.
    """
    project, user = _project(session, enabled_skills=["research"])
    run = _run(session, project, user, bot="runner")

    system = [
        message
        for message in agent_loop.messages_for(run, [])
        if message["role"] == "system"
    ]

    assert any("runner bot" in message["content"] for message in system)
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
    """A child doing part of the runner's work is still bound by the runner's refusals."""
    project, user = _project(session, enabled_skills=["research"])
    parent = _run(session, project, user, bot="runner")

    child = agent_runs.create_run(
        session,
        project_id=project.id,
        user_id=user.id,
        goal="check the attempt history",
        allowed_tools=list(parent.allowed_tools),
        parent_run_id=parent.id,
    )

    assert child.bot == "runner"


def test_the_structuralist_can_reach_a_structure_to_analyse() -> None:
    """Its only route to an artifact id is `project-read`.

    `planner` deliberately has no `research-read`, so nothing else in its
    tool set returns an artifact id. Trimming `project-read` off it would leave
    three structure tools that need an `artifact_id` and no way to obtain one -
    a bot that looks configured and can never do anything. The ids it needs are
    on targets (`structure_artifact_id`) and on candidates (`structure_artifact_id`
    and `complex_artifact_id`, the latter being what an interface question is
    actually asked about).
    """
    granted = tools_for_capabilities(bots.capabilities_for_bot("planner", ALL_CAPABILITIES))

    assert {"list_project_targets", "list_project_candidates"} <= granted
    assert {"analyse_structure", "list_structure_contacts", "describe_structure_site"} <= granted
