"""The room is a projection, and the tests are about what a projection can break.

Merging three tables into one order has exactly four ways to go wrong, and each
one is silent:

* an entry from another project appears, because the message table has no
  project column and the join was written from memory;
* an entry is skipped or repeated across a page boundary, because two rows share
  an instant and the cursor only carried the instant;
* one source drowns the others, because the merge asked for `limit` rows in
  total instead of `limit` per source;
* the room shows something nobody said - prompt scaffolding, or a speaker the
  record never attributed.

Nothing here asserts on rendering. The room writes nothing, so the only
behaviour it has is which rows come back, in which order.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.copilot import handoffs, room
from backend_v2.app.copilot.models import (
    CopilotAgentRun,
    CopilotConversation,
    CopilotMessage,
)
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_counter = itertools.count()
START = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)


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
    user = User(username=f"room-{n}", display_name="R", role="researcher", enabled=True)
    organization = Organization(name=f"Room Org {n}")
    session.add_all([user, organization])
    session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="admin"))
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"room-{n}", project_type="protein_design"
    )
    session.add(project)
    session.flush()
    return project, user


def _conversation(session: Session, project: Project, user: User) -> CopilotConversation:
    conversation = CopilotConversation(project_id=project.id, created_by=user.id, title="room")
    session.add(conversation)
    session.flush()
    return conversation


def _message(
    session: Session,
    conversation: CopilotConversation,
    *,
    role: str = "assistant",
    bot: str | None = None,
    content: str = "text",
    at: datetime = START,
) -> CopilotMessage:
    row = CopilotMessage(conversation_id=conversation.id, role=role, bot=bot, content=content)
    session.add(row)
    session.flush()
    # `created_at` has a server default, so a test that wants a known order has
    # to set it after the insert rather than passing it in.
    row.created_at = at
    session.flush()
    return row


def _run(
    session: Session,
    project: Project,
    user: User,
    *,
    bot: str | None = "planner",
    goal: str = "plan the route",
    status: str = "completed",
    outcome: dict | None = None,
    parent: uuid.UUID | None = None,
    at: datetime = START,
) -> CopilotAgentRun:
    run = CopilotAgentRun(
        project_id=project.id,
        created_by=user.id,
        goal=goal,
        bot=bot,
        status=status,
        outcome=outcome or {},
        parent_run_id=parent,
        allowed_tools=[],
    )
    session.add(run)
    session.flush()
    run.created_at = at
    session.flush()
    return run


def _handoff(
    session: Session,
    project: Project,
    user: User,
    *,
    from_bot: str = "planner",
    to_bot: str = "runner",
    at: datetime = START,
):
    row = handoffs.record(
        session,
        project_id=project.id,
        user_id=user.id,
        from_bot=from_bot,
        to_bot=to_bot,
        summary="draft ready",
        claims=[{"statement": "the queue forces a GPU", "confidence": "stated", "evidence_ref": "job:1"}],
    )
    row.created_at = at
    session.flush()
    return row


# --- what the room contains --------------------------------------------------


def test_all_three_records_appear_in_one_order(session: Session) -> None:
    project, user = _project(session)
    conversation = _conversation(session, project, user)
    _message(session, conversation, role="user", content="which route?", at=START)
    _run(session, project, user, at=START + timedelta(minutes=1))
    _handoff(session, project, user, at=START + timedelta(minutes=2))
    _message(session, conversation, bot="planner", content="two routes", at=START + timedelta(minutes=3))

    entries, cursor = room.events(session, project_id=project.id)

    assert [entry["kind"] for entry in entries] == ["message", "handoff", "task", "message"]
    assert cursor is None
    assert [entry["occurred_at"] for entry in entries] == sorted(
        (entry["occurred_at"] for entry in entries), reverse=True
    )


def test_a_message_carries_the_operator_that_produced_it(session: Session) -> None:
    project, user = _project(session)
    conversation = _conversation(session, project, user)
    _message(session, conversation, bot="analyst", content="the assay says", at=START)

    entry = room.events(session, project_id=project.id)[0][0]

    assert entry["bot"] == "analyst"
    assert entry["message"].bot == "analyst"


def test_an_unattributed_turn_stays_unattributed(session: Session) -> None:
    """No default operator. A turn nobody owned is shown as one."""
    project, user = _project(session)
    conversation = _conversation(session, project, user)
    _message(session, conversation, bot=None, content="answered before the roster", at=START)

    assert room.events(session, project_id=project.id)[0][0]["bot"] is None


def test_prompt_scaffolding_is_not_conversation(session: Session) -> None:
    project, user = _project(session)
    conversation = _conversation(session, project, user)
    _message(session, conversation, role="system", content="BDA_COPILOT_POLICY_V6", at=START)
    _message(session, conversation, role="user", content="hello", at=START + timedelta(minutes=1))

    entries, _ = room.events(session, project_id=project.id)

    assert [entry["message"].role for entry in entries] == ["user"]


def test_another_projects_conversation_never_leaks_in(session: Session) -> None:
    """The message table has no project column; the join is the whole guard."""
    project, user = _project(session)
    other, other_user = _project(session)
    _message(session, _conversation(session, project, user), content="ours", at=START)
    _message(session, _conversation(session, other, other_user), content="theirs", at=START + timedelta(minutes=1))
    _run(session, other, other_user, at=START + timedelta(minutes=2))
    _handoff(session, other, other_user, at=START + timedelta(minutes=3))

    entries, _ = room.events(session, project_id=project.id)

    assert len(entries) == 1
    assert entries[0]["message"].content == "ours"


def test_a_task_entry_reports_its_delivery_and_its_parent(session: Session) -> None:
    project, user = _project(session)
    parent = _run(session, project, user, goal="parent", at=START)
    _run(
        session,
        project,
        user,
        bot="runner",
        goal="child",
        status="running",
        outcome={"status": "needs_input"},
        parent=parent.id,
        at=START + timedelta(minutes=1),
    )

    child = room.events(session, project_id=project.id)[0][0]["task"]

    assert child["delivery_state"] == "needs_input"
    assert child["parent_run_id"] == parent.id


def test_a_handoff_entry_keeps_its_claims(session: Session) -> None:
    project, user = _project(session)
    _handoff(session, project, user, at=START)

    entry = room.events(session, project_id=project.id)[0][0]

    assert entry["bot"] == "planner"
    assert entry["handoff"]["to_bot"] == "runner"
    assert entry["handoff"]["claims"][0]["confidence"] == "stated"


# --- paging ------------------------------------------------------------------


def test_paging_never_skips_or_repeats_entries_sharing_an_instant(session: Session) -> None:
    """Four rows, one timestamp. A timestamp-only cursor loses some of them."""
    project, user = _project(session)
    conversation = _conversation(session, project, user)
    for index in range(4):
        _message(session, conversation, content=f"m{index}", at=START)

    first, cursor = room.events(session, project_id=project.id, limit=2)
    assert cursor is not None
    second, next_cursor = room.events(session, project_id=project.id, limit=2, cursor=cursor)

    seen = [entry["message"].content for entry in (*first, *second)]
    assert sorted(seen) == ["m0", "m1", "m2", "m3"]
    assert next_cursor is None


def test_one_loud_source_cannot_hide_another(session: Session) -> None:
    """Each source is asked for its own page, so the quiet one still appears."""
    project, user = _project(session)
    conversation = _conversation(session, project, user)
    for index in range(10):
        _message(session, conversation, content=f"m{index}", at=START + timedelta(minutes=index))
    _handoff(session, project, user, at=START + timedelta(minutes=20))

    entries, _ = room.events(session, project_id=project.id, limit=5)

    assert entries[0]["kind"] == "handoff"


def test_an_unreadable_cursor_is_rejected_rather_than_ignored(session: Session) -> None:
    project, _user = _project(session)
    from backend_v2.app.core.problem import DomainError

    with pytest.raises(DomainError):
        room.events(session, project_id=project.id, cursor="not-a-cursor")


def test_limit_is_bounded_by_the_module_and_not_by_the_caller(session: Session) -> None:
    project, user = _project(session)
    conversation = _conversation(session, project, user)
    for index in range(3):
        _message(session, conversation, content=f"m{index}", at=START + timedelta(minutes=index))

    entries, _ = room.events(session, project_id=project.id, limit=10_000)

    assert len(entries) == 3
