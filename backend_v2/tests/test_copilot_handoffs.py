"""The channel between operators, and the shape that makes it checkable.

`BotSpec.handoff` named a successor and carried nothing across. These tests are
about the half that carries: a handover is a row, it names two accountable
operators, and its claims arrive in the shape a reviewer reads rather than as
prose somebody has to interpret.

The claim normalisation tests are the ones worth keeping longest. A claim with
no evidence reference is exactly the defect review exists to find, so it must be
*recorded as unsupported* rather than rejected at the door - rejecting it would
mean the operator's own mistake never reaches the record, and the handover would
look clean because the bad claim is missing from it.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.copilot import agent_runs, handoffs
from backend_v2.app.copilot import tools as _tools  # noqa: F401  (registers the catalogue)
from backend_v2.app.copilot.registry import REGISTRY, ToolContext
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_counter = itertools.count()


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
    user = User(username=f"handoff-{n}", display_name="H", role="researcher", enabled=True)
    organization = Organization(name=f"Handoff Org {n}")
    session.add_all([user, organization])
    session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="admin"))
    project = Project(
        organization_id=organization.id,
        owner_id=user.id,
        name=f"handoff-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project, user


def _post(session: Session, project: Project, user: User, **kwargs):
    payload = {
        "project_id": project.id,
        "user_id": user.id,
        "from_bot": "researcher",
        "to_bot": "planner",
        "summary": "Collected the PD-1 affinity literature.",
    }
    payload.update(kwargs)
    return handoffs.record(session, **payload)  # type: ignore[arg-type]


# --- Who a note is between ---------------------------------------------------


def test_a_handover_names_two_real_operators(session: Session) -> None:
    project, user = _project(session)

    row = _post(session, project, user)

    assert (row.from_bot, row.to_bot) == ("researcher", "planner")


@pytest.mark.parametrize(
    ("from_bot", "to_bot"),
    [("ghost", "planner"), ("researcher", "ghost")],
)
def test_an_unknown_operator_is_refused(
    session: Session, from_bot: str, to_bot: str
) -> None:
    """A note addressed to nobody is never read, and looks like a completed
    handover to whoever wrote it."""
    project, user = _project(session)

    with pytest.raises(DomainError) as raised:
        _post(session, project, user, from_bot=from_bot, to_bot=to_bot)

    assert raised.value.status_code == 404


def test_an_operator_does_not_hand_over_to_itself(session: Session) -> None:
    project, user = _project(session)

    with pytest.raises(DomainError, match="does not hand over to itself"):
        _post(session, project, user, to_bot="researcher")


def test_an_unusual_route_is_reported_rather_than_refused() -> None:
    """`auditor` is in nobody's `handoff` tuple, and must still be able to report.

    Enforcing the tuple would make the review stance structurally unable to
    deliver a verdict, so the route is surfaced instead.
    """
    assert handoffs.is_off_chain("auditor", "runner") is True
    assert handoffs.is_off_chain("researcher", "planner") is False


# --- The shape a reviewer reads ----------------------------------------------


def test_a_claim_keeps_its_evidence_and_its_level(session: Session) -> None:
    project, user = _project(session)

    row = _post(
        session,
        project,
        user,
        claims=[
            {
                "statement": "PD-1 binder A has a recorded KD of 4 nM",
                "evidence_ref": "result:9f1b",
                "confidence": "stated",
            }
        ],
    )

    assert row.claims == [
        {
            "statement": "PD-1 binder A has a recorded KD of 4 nM",
            "evidence_ref": "result:9f1b",
            "confidence": "stated",
        }
    ]


def test_a_claim_citing_nothing_is_recorded_as_unsupported_not_dropped(
    session: Session,
) -> None:
    """The defect review exists to find, so it has to survive into the record.

    Rejecting the note would mean the operator's own unsupported claim never
    reaches the reviewer, and the handover would read as clean precisely because
    the bad claim is missing from it.
    """
    project, user = _project(session)

    row = _post(session, project, user, claims=[{"statement": "This target is druggable"}])

    assert row.claims[0]["confidence"] == "unsupported"
    assert row.claims[0]["evidence_ref"] == ""


def test_an_operator_cannot_assert_its_way_past_a_missing_reference(
    session: Session,
) -> None:
    """Confidence is about evidence, not about how sure the operator sounds."""
    project, user = _project(session)

    row = _post(
        session,
        project,
        user,
        claims=[{"statement": "This target is druggable", "confidence": "stated"}],
    )

    assert row.claims[0]["confidence"] == "unsupported"


def test_an_unrecognised_confidence_falls_back_to_what_the_evidence_supports(
    session: Session,
) -> None:
    project, user = _project(session)

    row = _post(
        session,
        project,
        user,
        claims=[
            {"statement": "s", "evidence_ref": "reference:1", "confidence": "very sure"},
        ],
    )

    assert row.claims[0]["confidence"] == "consistent"


def test_a_claim_with_no_statement_is_refused(session: Session) -> None:
    """Unlike a missing reference: an empty statement records nothing at all."""
    project, user = _project(session)

    with pytest.raises(DomainError, match="claim statement"):
        _post(session, project, user, claims=[{"evidence_ref": "reference:1"}])


@pytest.mark.parametrize("field", ["claims", "open_questions", "refs"])
def test_a_list_field_that_is_not_a_list_is_refused(session: Session, field: str) -> None:
    project, user = _project(session)

    with pytest.raises(DomainError):
        _post(session, project, user, **{field: "not a list"})


def test_the_carried_lists_are_bounded(session: Session) -> None:
    """A handover is a summary for the next operator, not a transcript."""
    project, user = _project(session)

    with pytest.raises(DomainError, match="at most"):
        _post(
            session,
            project,
            user,
            claims=[{"statement": f"s{n}"} for n in range(handoffs.MAX_CLAIMS + 1)],
        )


def test_empty_open_questions_and_refs_are_dropped_rather_than_stored(
    session: Session,
) -> None:
    project, user = _project(session)

    row = _post(session, project, user, open_questions=["", "  ", "Which ortholog?"], refs=[""])

    assert row.open_questions == ["Which ortholog?"]
    assert row.refs == []


# --- Reading the channel -----------------------------------------------------


def test_an_operator_reads_the_notes_addressed_to_it(session: Session) -> None:
    project, user = _project(session)
    _post(session, project, user, from_bot="researcher", to_bot="planner", summary="for planner")
    _post(session, project, user, from_bot="planner", to_bot="runner", summary="for runner")

    inbox = handoffs.inbox(session, project_id=project.id, to_bot="planner")

    assert [row.summary for row in inbox] == ["for planner"]


def test_a_reviewer_reads_what_one_operator_has_been_claiming(session: Session) -> None:
    project, user = _project(session)
    _post(session, project, user, from_bot="researcher", to_bot="planner", summary="a")
    _post(session, project, user, from_bot="researcher", to_bot="analyst", summary="b")
    _post(session, project, user, from_bot="planner", to_bot="runner", summary="c")

    sent = handoffs.inbox(session, project_id=project.id, from_bot="researcher")

    assert {row.summary for row in sent} == {"a", "b"}


def test_notes_do_not_cross_projects(session: Session) -> None:
    project, user = _project(session)
    other_project, other_user = _project(session)
    _post(session, project, user, summary="ours")
    _post(session, other_project, other_user, summary="theirs")

    assert [row.summary for row in handoffs.inbox(session, project_id=project.id)] == ["ours"]


def test_an_unknown_operator_in_a_filter_is_refused(session: Session) -> None:
    """Rather than returning an empty inbox, which reads as "nothing to do"."""
    project, user = _project(session)

    with pytest.raises(DomainError):
        handoffs.inbox(session, project_id=project.id, to_bot="ghost")


# --- The tool ----------------------------------------------------------------


def _ctx(session: Session, project: Project, user: User, *, bot: str | None, run=None):
    return ToolContext(
        project_id=project.id,
        user_id=user.id,
        session=session,
        bot=bot,
        agent_run=run,
    )


def test_an_unowned_turn_cannot_hand_over(session: Session) -> None:
    """A note whose sender is "the assistant" names nobody accountable, and a
    reviewer would have no charter to check it against."""
    project, user = _project(session)

    with pytest.raises(ValueError, match="copilot_bot_context_required"):
        REGISTRY.execute(
            "post_handoff",
            _ctx(session, project, user, bot=None),
            {"to_bot": "planner", "summary": "s"},
        )


def test_the_tool_reports_unsupported_claims_back_to_their_author(session: Session) -> None:
    """Told while the operator can still fix the note, rather than only to the
    reviewer afterwards."""
    project, user = _project(session)

    result = REGISTRY.execute(
        "post_handoff",
        _ctx(session, project, user, bot="researcher"),
        {
            "to_bot": "planner",
            "summary": "Collected the literature",
            "claims": [
                {"statement": "a", "evidence_ref": "reference:1"},
                {"statement": "b"},
            ],
        },
    )

    assert result["unsupported_claims"] == 1
    assert result["off_chain"] is False


def test_a_note_written_inside_a_run_remembers_it(session: Session) -> None:
    """A note with no run behind it has no transcript for the reviewer to read,
    and `auditor` reports that as unreviewable rather than as clean."""
    project, user = _project(session)
    run = agent_runs.create_run(
        session,
        project_id=project.id,
        user_id=user.id,
        goal="Collect the literature",
        allowed_tools=["post_handoff"],
        bot="researcher",
    )

    result = REGISTRY.execute(
        "post_handoff",
        _ctx(session, project, user, bot="researcher", run=run),
        {"to_bot": "planner", "summary": "done"},
    )

    assert result["produced_by_run"] == str(run.id)


def test_a_chat_note_records_no_run(session: Session) -> None:
    project, user = _project(session)

    result = REGISTRY.execute(
        "post_handoff",
        _ctx(session, project, user, bot="researcher"),
        {"to_bot": "planner", "summary": "done"},
    )

    assert result["produced_by_run"] is None


def test_reading_the_channel_needs_no_operator(session: Session) -> None:
    """Only writing does. A person reading the chain through chat has no bot,
    and refusing the read would make the record invisible from the UI."""
    project, user = _project(session)
    _post(session, project, user)

    rows = REGISTRY.execute("read_handoffs", _ctx(session, project, user, bot=None), {})

    assert [row["to_bot"] for row in rows] == ["planner"]


# --- Through the API ---------------------------------------------------------


def _list(session: Session, project: Project, user: User, **filters):
    """Call the endpoint with every parameter supplied.

    FastAPI's `Query(...)` defaults are only resolved by the request pipeline;
    calling the function directly would otherwise pass the `Query` object itself
    into the roster lookup.
    """
    from backend_v2.app.copilot.api import list_handoffs

    return list_handoffs(
        project_id=project.id,
        to_bot=filters.get("to_bot"),
        from_bot=filters.get("from_bot"),
        limit=filters.get("limit", handoffs.DEFAULT_LIMIT),
        session=session,
        user=user,
    )


def test_a_person_can_read_the_chain_not_only_the_next_operator(session: Session) -> None:
    """The channel's justification is that claims are auditable afterwards.

    A record only the bots can read would make that true for `auditor` and false
    for the reader it is ultimately for, so the rows are a resource.
    """
    project, user = _project(session)
    _post(session, project, user, from_bot="researcher", to_bot="planner", summary="a")
    _post(session, project, user, from_bot="planner", to_bot="runner", summary="b")
    session.commit()

    page = _list(session, project, user)

    assert {item.summary for item in page.items} == {"a", "b"}
    assert {item.from_bot for item in page.items} == {"researcher", "planner"}


def test_the_api_filters_by_operator(session: Session) -> None:
    project, user = _project(session)
    _post(session, project, user, from_bot="researcher", to_bot="planner", summary="a")
    _post(session, project, user, from_bot="planner", to_bot="runner", summary="b")
    session.commit()

    page = _list(session, project, user, to_bot="runner")

    assert [item.summary for item in page.items] == ["b"]


def test_the_api_returns_claims_in_the_shape_a_reader_can_judge(session: Session) -> None:
    project, user = _project(session)
    _post(
        session,
        project,
        user,
        claims=[
            {"statement": "a", "evidence_ref": "result:1", "confidence": "stated"},
            {"statement": "b"},
        ],
    )
    session.commit()

    claims = _list(session, project, user).items[0].claims

    assert [claim.confidence for claim in claims] == ["stated", "unsupported"]
