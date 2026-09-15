"""A question an operator may not answer itself.

The table is small; the properties that make it worth having are not:

* an operator can ask, and has no path to answering - if one existed, the
  "decision" recorded would be the model agreeing with itself;
* the options are bounded and each carries what it rests on, because a list
  nobody can hold is a list a reviewer stops reading;
* an answer lands in the project's record attributed
  `agent_proposed_human_confirmed`, the state that exists precisely for work a
  model drafted and a person accepted. Collapsing it to either side destroys
  the only comparison the column is for;
* the branches not taken are written down at the moment of the decision, which
  is the only moment anybody has them.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.copilot import decisions
from backend_v2.app.copilot import tools as _tools  # noqa: F401  (registers the catalogue)
from backend_v2.app.copilot.registry import REGISTRY
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project
from backend_v2.app.timeline.models import ProjectTimelineEntry
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_counter = itertools.count()

OPTIONS = [
    {
        "label": "Target the CC' loop",
        "rationale": "Covers the native interface",
        "evidence_refs": ["artifact:1"],
    },
    {"key": "hot3", "label": "Target I126/L128/A132", "rationale": "Higher designability"},
]


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
    user = User(username=f"decide-{n}", display_name="D", role="researcher", enabled=True)
    organization = Organization(name=f"Decide Org {n}")
    session.add_all([user, organization])
    session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="admin"))
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"decide-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project, user


def _ask(session: Session, project: Project, user: User, **overrides):
    payload = {
        "project_id": project.id,
        "user_id": user.id,
        "asked_by": "planner",
        "question": "Which hotspot set should the binder target?",
        "options": OPTIONS,
    }
    payload.update(overrides)
    return decisions.record(session, **payload)


# --- asking ------------------------------------------------------------------


def test_an_option_without_a_key_gets_one_and_keeps_its_evidence(session: Session) -> None:
    project, user = _project(session)

    row = _ask(session, project, user)

    assert [option["key"] for option in row.options] == ["a", "hot3"]
    assert row.options[0]["evidence_refs"] == ["artifact:1"]
    assert row.status == "open"
    assert row.answered_by is None


def test_an_option_with_no_rationale_is_recorded_rather_than_dropped(session: Session) -> None:
    """An operator offering an option it cannot justify has said something."""
    project, user = _project(session)

    row = _ask(session, project, user, options=[{"label": "Wait for the assay"}, {"label": "Design now"}])

    assert [option["rationale"] for option in row.options] == ["", ""]


@pytest.mark.parametrize(
    "options",
    [
        [{"label": "only one"}],
        [{"label": f"option {index}"} for index in range(7)],
        "not a list",
        [{"label": "a"}, {"label": ""}],
    ],
)
def test_a_choice_that_cannot_be_read_is_refused(session: Session, options: object) -> None:
    project, user = _project(session)

    with pytest.raises(DomainError):
        _ask(session, project, user, options=options)


def test_duplicate_option_keys_are_refused(session: Session) -> None:
    project, user = _project(session)

    with pytest.raises(DomainError):
        _ask(session, project, user, options=[{"key": "x", "label": "A"}, {"key": "x", "label": "B"}])


def test_a_recommendation_must_name_an_option_that_exists(session: Session) -> None:
    project, user = _project(session)

    with pytest.raises(DomainError):
        _ask(session, project, user, recommended="nope")

    row = _ask(session, project, user, recommended="hot3")
    assert row.recommended == "hot3"


def test_only_a_roster_operator_can_ask(session: Session) -> None:
    project, user = _project(session)

    with pytest.raises(DomainError):
        _ask(session, project, user, asked_by="not-a-bot")


def test_a_retired_operator_cannot_open_new_questions(session: Session) -> None:
    """`structuralist` was merged into `planner`; new work uses the successor."""
    project, user = _project(session)

    with pytest.raises(DomainError):
        _ask(session, project, user, asked_by="structuralist")


# --- answering ---------------------------------------------------------------


def test_an_answer_becomes_a_decision_record_attributed_to_both(session: Session) -> None:
    project, user = _project(session)
    row = _ask(session, project, user)

    decisions.answer(session, row, project=project, user=user, choice="hot3", note="assay first")

    entry = session.scalar(select(ProjectTimelineEntry).where(ProjectTimelineEntry.id == row.decision_entry_id))
    assert entry is not None
    assert entry.decided_by == "agent_proposed_human_confirmed"
    assert entry.entry_type == "decision"
    assert row.status == "answered"
    assert row.answered_by == user.id
    assert row.answered_at is not None


def test_the_record_says_what_was_not_chosen(session: Session) -> None:
    """The branch not taken is worth the most later and is never written down."""
    project, user = _project(session)
    row = _ask(session, project, user)

    decisions.answer(session, row, project=project, user=user, choice="hot3")

    entry = session.get(ProjectTimelineEntry, row.decision_entry_id)
    assert entry is not None
    assert "Not chosen: Target the CC' loop" in entry.body
    assert "Covers the native interface" in entry.body


def test_the_record_can_be_traced_back_to_the_question(session: Session) -> None:
    project, user = _project(session)
    row = _ask(session, project, user)

    decisions.answer(session, row, project=project, user=user, choice="a")

    entry = session.get(ProjectTimelineEntry, row.decision_entry_id)
    assert entry is not None
    assert f"copilot-decision-request:{row.id}" in entry.provenance["external_refs"]
    assert "artifact:1" in entry.provenance["external_refs"]


def test_an_answer_must_name_an_option_that_was_offered(session: Session) -> None:
    project, user = _project(session)
    row = _ask(session, project, user)

    with pytest.raises(DomainError):
        decisions.answer(session, row, project=project, user=user, choice="whatever")


def test_a_settled_question_is_not_answered_twice(session: Session) -> None:
    project, user = _project(session)
    row = _ask(session, project, user)
    decisions.answer(session, row, project=project, user=user, choice="a")

    with pytest.raises(DomainError):
        decisions.answer(session, row, project=project, user=user, choice="hot3")


def test_an_answered_question_cannot_be_withdrawn_out_of_the_record(session: Session) -> None:
    project, user = _project(session)
    row = _ask(session, project, user)
    decisions.answer(session, row, project=project, user=user, choice="a")

    with pytest.raises(DomainError):
        decisions.withdraw(session, row)


def test_a_question_the_work_moved_past_is_withdrawn_and_stays_readable(session: Session) -> None:
    project, user = _project(session)
    row = _ask(session, project, user)

    decisions.withdraw(session, row)

    assert row.status == "withdrawn"
    assert row.question
    assert session.get(type(row), row.id) is not None


# --- listing -----------------------------------------------------------------


def test_questions_are_listed_newest_first_and_filterable_by_status(session: Session) -> None:
    project, user = _project(session)
    first = _ask(session, project, user)
    _ask(session, project, user, question="Which queue?")
    decisions.answer(session, first, project=project, user=user, choice="a")

    assert len(decisions.requests(session, project_id=project.id)) == 2
    assert [row.id for row in decisions.requests(session, project_id=project.id, status="answered")] == [first.id]


def test_an_unknown_status_filter_is_refused_rather_than_ignored(session: Session) -> None:
    project, _user = _project(session)

    with pytest.raises(DomainError):
        decisions.requests(session, project_id=project.id, status="pending")


def test_another_projects_questions_are_not_listed(session: Session) -> None:
    project, user = _project(session)
    other, other_user = _project(session)
    _ask(session, other, other_user)

    assert decisions.requests(session, project_id=project.id) == []


# --- the operator cannot settle its own question -----------------------------


def test_no_tool_can_answer_a_decision_request(session: Session) -> None:
    """Asking is a tool; answering is not, and that is the whole guard.

    `decisions.answer` requires a `User` and is reachable only from the REST
    endpoint behind `require_command`. A tool that could call it would let an
    operator record its own preference as a human-confirmed decision.
    """
    chain_tools = {spec.id for spec in REGISTRY.all() if spec.capability == "chain-messaging"}

    assert chain_tools == {"post_handoff", "read_handoffs", "request_decision"}
    assert not any("answer" in spec.id or "settle" in spec.id for spec in REGISTRY.all())


def test_asking_is_a_draft_that_changes_no_research_record(session: Session) -> None:
    spec = next(item for item in REGISTRY.all() if item.id == "request_decision")

    assert spec.execution_mode == "draft"
    assert spec.needs_operator is True
    assert spec.audit is True
    # Internal, like a handover: asking a person a question is not an action
    # taken on their behalf, so it does not need the user's own words first.
    assert spec.intent == "internal"
