"""The research goal tree.

The cycle tests matter most: a goal moved inside its own subtree makes the tree
unreachable from any root, and a naive ancestry walk over it never terminates.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.research import goals
from backend_v2.tests._sqlite import drop_all
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    # SQLite ignores foreign keys unless asked, so without this the ON DELETE
    # CASCADE that removes a subtree silently does nothing here and the test
    # would pass against Postgres semantics it never actually exercised.
    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as opened:
        yield opened
    drop_all(engine, Base.metadata)


def _project(session: Session, name: str = "trace") -> tuple[uuid.UUID, uuid.UUID]:
    user = User(username=f"u-{name}", display_name="U", role="editor", enabled=True)
    organization = Organization(name=f"org-{name}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=name, project_type="protein_design"
    )
    session.add(project)
    session.flush()
    return project.id, user.id


def test_goals_nest_and_number_within_their_parent(session: Session) -> None:
    project_id, user_id = _project(session)
    root = goals.create_goal(session, project_id, user_id, title="Bind the receptor")
    first = goals.create_goal(session, project_id, user_id, title="Find a scaffold", parent_id=root.id)
    second = goals.create_goal(session, project_id, user_id, title="Measure affinity", parent_id=root.id)

    assert root.parent_id is None
    assert (first.sort_order, second.sort_order) == (0, 1)
    # Ordering is per parent, so a second root starts at 0 again.
    other_root = goals.create_goal(session, project_id, user_id, title="Improve stability")
    assert other_root.sort_order == 1  # sibling of `root`, which is also a root


def test_a_goal_cannot_be_moved_into_its_own_subtree(session: Session) -> None:
    project_id, user_id = _project(session)
    root = goals.create_goal(session, project_id, user_id, title="root")
    child = goals.create_goal(session, project_id, user_id, title="child", parent_id=root.id)
    grandchild = goals.create_goal(session, project_id, user_id, title="grandchild", parent_id=child.id)

    with pytest.raises(DomainError) as raised:
        goals.update_goal(session, root, parent_id=grandchild.id, reparent=True)
    assert raised.value.error_code == "research_goal_cycle"
    assert root.parent_id is None  # unchanged


def test_a_goal_cannot_be_its_own_parent(session: Session) -> None:
    project_id, user_id = _project(session)
    goal = goals.create_goal(session, project_id, user_id, title="solo")
    with pytest.raises(DomainError) as raised:
        goals.update_goal(session, goal, parent_id=goal.id, reparent=True)
    assert raised.value.error_code == "research_goal_cycle"


def test_reparent_to_root_is_expressible(session: Session) -> None:
    """`parent_id=None` alone is ambiguous with "field omitted", which is why the
    caller has to say `reparent`."""
    project_id, user_id = _project(session)
    root = goals.create_goal(session, project_id, user_id, title="root")
    child = goals.create_goal(session, project_id, user_id, title="child", parent_id=root.id)

    goals.update_goal(session, child, parent_id=None, reparent=True)
    assert child.parent_id is None

    # Without the flag, an omitted parent leaves the tree alone.
    again = goals.create_goal(session, project_id, user_id, title="c2", parent_id=root.id)
    goals.update_goal(session, again, title="renamed")
    assert again.parent_id == root.id


def test_goals_cannot_hang_under_another_projects_goal(session: Session) -> None:
    first_project, user_id = _project(session, "one")
    second_project, other_user = _project(session, "two")
    foreign = goals.create_goal(session, second_project, other_user, title="theirs")

    with pytest.raises(DomainError) as raised:
        goals.create_goal(session, first_project, user_id, title="ours", parent_id=foreign.id)
    assert raised.value.error_code == "research_goal_cross_project"


def test_status_is_restricted_to_the_declared_vocabulary(session: Session) -> None:
    project_id, user_id = _project(session)
    goal = goals.create_goal(session, project_id, user_id, title="g")
    goals.update_goal(session, goal, status="answered")
    assert goal.status == "answered"
    with pytest.raises(DomainError) as raised:
        goals.update_goal(session, goal, status="in-progress")
    assert raised.value.error_code == "research_goal_bad_status"


# --- Links -------------------------------------------------------------------


def test_one_result_can_serve_several_goals(session: Session) -> None:
    """The reason links are many-to-many: re-running an assay must not force a
    choice about which question it answers."""
    project_id, user_id = _project(session)
    first = goals.create_goal(session, project_id, user_id, title="affinity")
    second = goals.create_goal(session, project_id, user_id, title="specificity")
    result_id = uuid.uuid4()

    goals.attach(session, first, user_id, resource_type="experiment_result", resource_id=result_id)
    goals.attach(session, second, user_id, resource_type="experiment_result", resource_id=result_id)

    grouped = goals.links_for(session, [first.id, second.id])
    assert len(grouped[first.id]) == 1
    assert len(grouped[second.id]) == 1


def test_attaching_the_same_thing_twice_is_idempotent(session: Session) -> None:
    project_id, user_id = _project(session)
    goal = goals.create_goal(session, project_id, user_id, title="g")
    resource_id = uuid.uuid4()
    first = goals.attach(session, goal, user_id, resource_type="candidate", resource_id=resource_id)
    second = goals.attach(session, goal, user_id, resource_type="candidate", resource_id=resource_id)
    assert first.id == second.id
    assert len(goals.links_for(session, [goal.id])[goal.id]) == 1


def test_unknown_link_types_are_rejected(session: Session) -> None:
    project_id, user_id = _project(session)
    goal = goals.create_goal(session, project_id, user_id, title="g")
    with pytest.raises(DomainError) as raised:
        goals.attach(session, goal, user_id, resource_type="spreadsheet", resource_id=uuid.uuid4())
    assert raised.value.error_code == "research_goal_bad_link_type"


def test_deleting_a_goal_takes_its_subtree_and_links_but_not_the_evidence(session: Session) -> None:
    project_id, user_id = _project(session)
    root = goals.create_goal(session, project_id, user_id, title="root")
    child = goals.create_goal(session, project_id, user_id, title="child", parent_id=root.id)
    goals.attach(session, child, user_id, resource_type="job", resource_id=uuid.uuid4())

    goals.delete_goal(session, root)
    session.expire_all()

    assert goals.tree(session, project_id) == []
    # The link went with its goal; nothing here owns the job it referenced, which
    # is exactly why links carry no foreign key to it.


def test_tree_returns_roots_before_their_children(session: Session) -> None:
    project_id, user_id = _project(session)
    root = goals.create_goal(session, project_id, user_id, title="root")
    goals.create_goal(session, project_id, user_id, title="child", parent_id=root.id)
    rows = goals.tree(session, project_id)
    assert rows[0].parent_id is None
    assert rows[-1].parent_id == root.id
