"""Delegation and review: the two relationships the roster did not have.

The roster shipped nine operators with no relationship between any two of them.
`handoff` was prose, a subagent inherited its parent's bot, and no operator could
read another's work - so nine bots were nine tool sets, and the charters that
said "hand this to medic" described something the platform could not do.

These tests are about the relationships rather than about any operator:

* a director opens a run owned by *someone else*, and that is narrowing rather
  than escalation;
* a director cannot authorise a write by writing the user's half of the
  conversation, which is the one way routing could have become escalation;
* a reviewer can read what an operator actually called, and holds nothing that
  would let it repair what it finds.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.copilot import agent_loop, agent_runs, bots
from backend_v2.app.copilot import tools as _tools  # noqa: F401  (registers the catalogue)
from backend_v2.app.copilot.capabilities import normalize_capabilities, tools_for_capabilities
from backend_v2.app.copilot.registry import REGISTRY, ToolContext
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_counter = itertools.count()

#: The user's own words, asking for one of the gated actions. `request_allows`
#: reads exactly this string, which is the whole point of the delegation test
#: below: a director must not be able to supply it.
USER_ASKED_FOR_A_SEARCH = "Search the literature for PD-1 binder affinity data and save what you find"
DIRECTOR_INSTRUCTION = "Search the literature for PD-1 affinity data and save what you find"


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


def _project(session: Session) -> tuple[Project, User]:
    n = next(_counter)
    user = User(username=f"chain-{n}", display_name="C", role="researcher", enabled=True)
    organization = Organization(name=f"Chain Org {n}")
    session.add_all([user, organization])
    session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="admin"))
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"chain-{n}", project_type="protein_design"
    )
    session.add(project)
    session.flush()
    return project, user


def _conductor_run(session: Session, project: Project, user: User, *, goal: str):
    enabled = normalize_capabilities(None)
    return agent_runs.create_run(
        session,
        project_id=project.id,
        user_id=user.id,
        goal=goal,
        # What `start_agent_run` would derive for this bot, rather than a
        # hand-picked list: a director's own reach is part of what is under test.
        allowed_tools=sorted(tools_for_capabilities(bots.capabilities_for_bot("conductor", enabled))),
        max_turns=8,
        bot="conductor",
    )


def _ctx(session: Session, run, *, enabled: set[str] | None = None) -> ToolContext:
    return ToolContext(
        project_id=run.project_id,
        user_id=run.created_by,
        session=session,
        agent_run=run,
        bot=run.bot,
        allowed_capabilities=frozenset(
            enabled if enabled is not None else normalize_capabilities(None)
        ),
    )


# --- Delegation --------------------------------------------------------------


def test_a_delegated_run_is_owned_by_the_target_operator(session: Session) -> None:
    """The relationship the roster could not express.

    `spawn_subagent` deliberately inherits the parent's bot - a child of the
    medic is still doing the medic's work. Delegation is the opposite move, and
    is why a director needs a tool of its own rather than a flag on that one.
    """
    project, user = _project(session)
    run = _conductor_run(session, project, user, goal="Work out what to do about PD-1")

    result = REGISTRY.execute(
        "delegate_to_operator",
        _ctx(session, run),
        {"bot": "librarian", "instruction": "Collect the affinity literature"},
    )

    child = agent_runs.require_run(session, uuid.UUID(result["run_id"]))
    assert child.bot == "librarian"
    assert child.parent_run_id == run.id
    assert result["waiting"] is True


def test_delegating_resolves_the_targets_capabilities_not_the_directors(session: Session) -> None:
    """Routing, not escalation.

    The director holds no literature tool at all. The child holds one, because
    it resolved `librarian ∩ project` - so the reach of the pair is bounded by
    what the project enabled and never by the director, who executes none of it.
    """
    project, user = _project(session)
    run = _conductor_run(session, project, user, goal=USER_ASKED_FOR_A_SEARCH)
    assert "start_literature_search" not in set(run.allowed_tools)

    result = REGISTRY.execute(
        "delegate_to_operator",
        _ctx(session, run),
        {"bot": "librarian", "instruction": "Collect the affinity literature"},
    )

    child = agent_runs.require_run(session, uuid.UUID(result["run_id"]))
    librarian = set(
        tools_for_capabilities(bots.capabilities_for_bot("librarian", normalize_capabilities(None)))
    )
    # Exactly the target's resolution. An earlier version intersected the child
    # with the parent the way `spawn_subagent` does, which dropped
    # `start_literature_search` - the one tool that makes a librarian a
    # librarian - and produced a child that read like an operator that failed.
    assert set(child.allowed_tools) == librarian
    assert "start_literature_search" in child.allowed_tools


def test_every_delegable_operator_keeps_the_tools_that_define_it(session: Session) -> None:
    """The general form of the defect above, across the whole roster.

    A director holds four capabilities and every producer holds at least one it
    does not. Intersecting against the director therefore silently removes each
    operator's defining tool, and the resulting child is indistinguishable from
    an operator that could not do its job.
    """
    project, user = _project(session)
    enabled = normalize_capabilities(None)

    for target in bots.require("conductor").directs:
        run = _conductor_run(session, project, user, goal="Work out what to do")
        result = REGISTRY.execute(
            "delegate_to_operator",
            _ctx(session, run),
            {"bot": target, "instruction": "Do your part"},
        )
        child = agent_runs.require_run(session, uuid.UUID(result["run_id"]))
        assert set(child.allowed_tools) == tools_for_capabilities(
            bots.capabilities_for_bot(target, enabled)
        ), target


def test_a_subagent_is_still_bounded_by_its_parent(session: Session) -> None:
    """The rule delegation is an exception to, not a rule it replaces.

    A child of the *same* operator is splitting work rather than routing it, so
    it must not be able to reach past what the parent may call.
    """
    project, user = _project(session)
    run = _conductor_run(session, project, user, goal="Work out what to do")

    child = agent_runs.create_run(
        session,
        project_id=project.id,
        user_id=user.id,
        goal="Part of it",
        allowed_tools=["start_literature_search", "research_overview"],
        parent_run_id=run.id,
    )

    assert child.bot == "conductor"
    assert "start_literature_search" not in child.allowed_tools
    assert "research_overview" in child.allowed_tools


def test_a_turn_without_the_projects_capabilities_refuses_to_delegate(
    session: Session,
) -> None:
    """The value that bounds the child, so a missing one stops the call.

    Defaulting to the target's full declaration would hand a delegated operator
    every capability it declares regardless of the project's configuration.
    """
    project, user = _project(session)
    run = _conductor_run(session, project, user, goal="Work out what to do")
    context = ToolContext(
        project_id=run.project_id,
        user_id=run.created_by,
        session=session,
        agent_run=run,
        bot=run.bot,
    )

    with pytest.raises(ValueError, match="copilot_project_capabilities_required"):
        REGISTRY.execute(
            "delegate_to_operator", context, {"bot": "librarian", "instruction": "Go"}
        )


def test_a_director_may_only_delegate_to_operators_it_declares(session: Session) -> None:
    """Bounded by the roster rather than by "any bot".

    `auditor` is not in `conductor.directs`: review is asked for, not ordered,
    and a director able to open a review run of its own choosing would be
    selecting its own reviewer.
    """
    project, user = _project(session)
    run = _conductor_run(session, project, user, goal="Work out what to do")

    with pytest.raises(ValueError, match="copilot_delegation_not_allowed"):
        REGISTRY.execute(
            "delegate_to_operator",
            _ctx(session, run),
            {"bot": "auditor", "instruction": "Check the planner"},
        )


def test_an_operator_with_nothing_enabled_is_refused_rather_than_delegated_to(
    session: Session,
) -> None:
    """An empty resolution is a real answer, and it is not the operator's fault.

    Delegating into it would produce a child run with no tools, which reads in
    the transcript as the operator failing rather than as the project not
    granting it anything.
    """
    project, user = _project(session)
    run = _conductor_run(session, project, user, goal="Work out what to do")

    with pytest.raises(ValueError, match="copilot_delegate_no_capabilities"):
        REGISTRY.execute(
            "delegate_to_operator",
            _ctx(session, run, enabled={"project-read"}),
            {"bot": "librarian", "instruction": "Collect the literature"},
        )


def test_delegation_is_unreachable_from_chat(session: Session) -> None:
    """No run to own the child, so no delegation.

    Same boundary `spawn_subagent` has: a chat turn that could open runs would
    be starting durable work behind the user's back.
    """
    spec = REGISTRY.get("delegate_to_operator")

    assert spec is not None
    assert spec.requires == "agent_run"


# --- The constraint that keeps routing from becoming escalation --------------


def test_a_director_cannot_authorise_a_write_by_writing_the_users_words(
    session: Session,
) -> None:
    """The sharpest rule in the design, and the reason `authorising_text` exists.

    The write-intent gate reads the user's own request. If a delegated run's
    goal counted as that request, a director could emit "search the literature
    and save it" and unlock every gated write in the project by asking itself
    for one. So the authorising words come from the root run, whatever the
    instruction says.
    """
    project, user = _project(session)
    run = _conductor_run(session, project, user, goal="Summarise what we already know about PD-1")

    result = REGISTRY.execute(
        "delegate_to_operator",
        _ctx(session, run),
        {"bot": "librarian", "instruction": DIRECTOR_INSTRUCTION},
    )
    child = agent_runs.require_run(session, uuid.UUID(result["run_id"]))

    assert child.goal == DIRECTOR_INSTRUCTION
    assert agent_loop.authorising_text(session, child) == run.goal


def test_the_users_own_words_still_reach_a_delegated_run(session: Session) -> None:
    """Narrowing, not blanket refusal.

    The rule above must not make delegation useless: when the person did ask for
    the search, the operator the director hands it to can still perform it.
    """
    project, user = _project(session)
    run = _conductor_run(session, project, user, goal=USER_ASKED_FOR_A_SEARCH)

    result = REGISTRY.execute(
        "delegate_to_operator",
        _ctx(session, run),
        {"bot": "librarian", "instruction": "Collect the affinity literature"},
    )
    child = agent_runs.require_run(session, uuid.UUID(result["run_id"]))

    assert agent_loop.authorising_text(session, child) == USER_ASKED_FOR_A_SEARCH


def test_a_root_run_authorises_with_its_own_goal(session: Session) -> None:
    project, user = _project(session)
    run = _conductor_run(session, project, user, goal=USER_ASKED_FOR_A_SEARCH)

    assert agent_loop.authorising_text(session, run) == USER_ASKED_FOR_A_SEARCH


def test_a_subagent_no_longer_authorises_with_its_parents_instruction(
    session: Session,
) -> None:
    """The same defect `spawn_subagent` had before delegation existed.

    A child's goal has always been written by the parent model. Fixing it only
    for `delegate_to_operator` would have left the older tool as the way round
    the rule.
    """
    project, user = _project(session)
    run = _conductor_run(session, project, user, goal="Summarise what we already know about PD-1")
    child = agent_runs.create_run(
        session,
        project_id=project.id,
        user_id=user.id,
        goal=DIRECTOR_INSTRUCTION,
        allowed_tools=list(run.allowed_tools),
        parent_run_id=run.id,
    )

    assert agent_loop.authorising_text(session, child) != child.goal
    assert agent_loop.authorising_text(session, child) == run.goal


# --- Review ------------------------------------------------------------------


def test_a_reviewer_reads_what_an_operator_called_not_what_it_said(session: Session) -> None:
    """The gap between the two is the subject of review.

    An operator that reports a saved search while having called only a read is
    exactly the claim `auditor` exists to rule on, so the tool returns the tool
    calls and not the assistant text around them.
    """
    project, user = _project(session)
    worked = agent_runs.create_run(
        session,
        project_id=project.id,
        user_id=user.id,
        goal="Collect the affinity literature",
        allowed_tools=["research_overview"],
        bot="librarian",
    )
    agent_runs.append_turn(
        session,
        worked,
        role="assistant",
        content="I saved four papers.",
        tool_calls=[{"name": "research_overview", "arguments": {}, "status": "completed"}],
    )
    reviewer = agent_runs.create_run(
        session,
        project_id=project.id,
        user_id=user.id,
        goal="Check the librarian",
        allowed_tools=sorted(
            tools_for_capabilities(bots.capabilities_for_bot("auditor", normalize_capabilities(None)))
        ),
        bot="auditor",
    )

    result = REGISTRY.execute(
        "read_operator_work", _ctx(session, reviewer), {"run_id": str(worked.id)}
    )

    assert result["bot"] == "librarian"
    assert [call["name"] for call in result["tool_calls"]] == ["research_overview"]


def test_a_reviewer_cannot_read_across_projects(session: Session) -> None:
    """Refused as not-found, because whether a run exists elsewhere is not this
    project's to learn."""
    project, user = _project(session)
    other_project, other_user = _project(session)
    elsewhere = agent_runs.create_run(
        session,
        project_id=other_project.id,
        user_id=other_user.id,
        goal="Someone else's work",
        allowed_tools=["research_overview"],
        bot="planner",
    )
    reviewer = agent_runs.create_run(
        session,
        project_id=project.id,
        user_id=user.id,
        goal="Check",
        allowed_tools=["read_operator_work"],
        bot="auditor",
    )

    with pytest.raises(ValueError, match="copilot_agent_run_not_found"):
        REGISTRY.execute(
            "read_operator_work", _ctx(session, reviewer), {"run_id": str(elsewhere.id)}
        )


def test_the_charters_a_reviewer_rules_against_are_returned_as_data(session: Session) -> None:
    """`outside_charter` is a verdict about a specific sentence.

    A reviewer quoting a charter from memory would be inventing the standard it
    applies, so the standard is fetched.
    """
    project, user = _project(session)
    reviewer = agent_runs.create_run(
        session,
        project_id=project.id,
        user_id=user.id,
        goal="Check",
        allowed_tools=["list_operator_charters"],
        bot="auditor",
    )

    charters = REGISTRY.execute("list_operator_charters", _ctx(session, reviewer), {})

    by_id = {entry["id"]: entry for entry in charters}
    assert set(by_id) == {bot.id for bot in bots.producers()}
    assert by_id["planner"]["charter"] == bots.require("planner").charter
    assert "auditor" in by_id["planner"]["reviewed_by"]
    assert "steward" in by_id["planner"]["reviewed_by"]


def test_a_reviewer_holds_nothing_that_could_repair_what_it_finds(session: Session) -> None:
    """The stance rule, checked against resolved tools rather than declarations.

    `_validate_roster` refuses a reviewer that declares a write capability. This
    is the same statement one level down: after resolving against a project with
    everything enabled, no reviewer can reach a write.
    """
    enabled = normalize_capabilities(None)
    writes = REGISTRY.write_ids()

    for bot in bots.all_bots():
        if bot.stance != "review":
            continue
        resolved = tools_for_capabilities(bots.capabilities_for_bot(bot.id, enabled))
        # `post_handoff` is how a verdict is delivered, and changes no research
        # record - see `registry.ToolSpec.intent`.
        assert (resolved & writes) <= {"post_handoff"}, sorted(resolved & writes)


def test_a_director_holds_nothing_that_could_do_the_work(session: Session) -> None:
    enabled = normalize_capabilities(None)
    writes = REGISTRY.write_ids()

    for bot in bots.all_bots():
        if bot.stance != "direct":
            continue
        resolved = tools_for_capabilities(bots.capabilities_for_bot(bot.id, enabled))
        assert (resolved & writes) <= {"post_handoff"}, sorted(resolved & writes)


# --- Resuming a delegated wait ----------------------------------------------


def test_a_settled_delegation_is_folded_back_under_the_right_tool_name(
    session: Session,
) -> None:
    """The provider rejects a tool message naming a call it does not answer.

    `kind == "subagent"` stopped naming one tool when `delegate_to_operator`
    joined `spawn_subagent`, so the fallback reads the child's operator - the
    same signal `create_run` used - rather than guessing from the kind.
    """
    from backend_v2.app.copilot.models import CopilotAgentTask

    project, user = _project(session)
    run = _conductor_run(session, project, user, goal="Work out what to do")
    result = REGISTRY.execute(
        "delegate_to_operator",
        _ctx(session, run),
        {"bot": "librarian", "instruction": "Collect the literature"},
    )
    child_id = uuid.UUID(result["run_id"])
    session.add(
        CopilotAgentTask(
            run_id=run.id,
            kind="subagent",
            resource_id=child_id,
            status="succeeded",
            tool_call_id="call_gone_from_view",
        )
    )
    session.flush()

    agent_loop.fold_settled_tasks(session, run)

    folded = [turn for turn in agent_runs.transcript(session, run) if turn.role == "tool"]
    assert folded[-1].tool_calls[0]["name"] == "delegate_to_operator"


def test_a_settled_subagent_still_folds_back_as_spawn_subagent(session: Session) -> None:
    """A child of the same operator is the other half of the same fallback."""
    from backend_v2.app.copilot.models import CopilotAgentTask

    project, user = _project(session)
    run = _conductor_run(session, project, user, goal="Work out what to do")
    child = agent_runs.create_run(
        session,
        project_id=project.id,
        user_id=user.id,
        goal="Part of it",
        allowed_tools=list(run.allowed_tools),
        parent_run_id=run.id,
    )
    session.add(
        CopilotAgentTask(
            run_id=run.id,
            kind="subagent",
            resource_id=child.id,
            status="succeeded",
            tool_call_id="call_gone_from_view",
        )
    )
    session.flush()

    agent_loop.fold_settled_tasks(session, run)

    folded = [turn for turn in agent_runs.transcript(session, run) if turn.role == "tool"]
    assert folded[-1].tool_calls[0]["name"] == "spawn_subagent"
