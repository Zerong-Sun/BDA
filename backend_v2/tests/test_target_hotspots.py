"""Who decided which residues a design targets.

The table exists to separate two things that looked identical in a chat
transcript: an operator's proposal and a person's decision. Every test here is
about that boundary, because crossing it silently is how a model's suggestion
would end up on a cluster job with nobody's name on it.

The last test is the one that matters most: only a confirmed set formats into a
design parameter, which is the property P4's wiring rests on.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project
from backend_v2.app.targets import hotspots
from backend_v2.app.targets.models import Target
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_counter = itertools.count()
RESIDUES = [{"chain": "A", "seq": 164, "name": "ARG"}, {"chain": "A", "seq": 168}]


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


def _target(session: Session) -> tuple[Project, Target, User]:
    n = next(_counter)
    user = User(username=f"hot-{n}", display_name="H", role="researcher", enabled=True)
    organization = Organization(name=f"Hot Org {n}")
    session.add_all([user, organization])
    session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="admin"))
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"hot-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    target = Target(project_id=project.id, name=f"PD-1 {n}")
    session.add(target)
    session.flush()
    return project, target, user


def _propose(session: Session, project: Project, target: Target, user: User, **overrides):
    payload = {
        "project_id": project.id,
        "target_id": target.id,
        "user_id": user.id,
        "label": "CC' loop face",
        "residues": RESIDUES,
        "origin": "agent",
    }
    payload.update(overrides)
    return hotspots.record(session, **payload)


# --- who said it -------------------------------------------------------------


def test_an_operators_set_is_pending_and_nobody_has_confirmed_it(session: Session) -> None:
    project, target, user = _target(session)

    row = _propose(session, project, target, user)

    assert (row.origin, row.status) == ("agent", "proposed")
    assert row.confirmed_by is None


def test_a_persons_own_set_is_confirmed_from_the_start(session: Session) -> None:
    project, target, user = _target(session)

    row = _propose(session, project, target, user, origin="human")

    assert (row.origin, row.status) == ("human", "confirmed")
    assert row.confirmed_by == user.id


def test_confirming_an_operators_set_records_that_both_took_part(session: Session) -> None:
    """Neither "agent" nor "human" is true of a set a model drafted and a person accepted."""
    project, target, user = _target(session)
    row = _propose(session, project, target, user)

    hotspots.confirm(session, row, user=user)

    assert row.origin == "agent_proposed_human_confirmed"
    assert row.status == "confirmed"
    assert row.confirmed_by == user.id


def test_an_origin_the_caller_invented_is_refused(session: Session) -> None:
    """A caller that could pass this state could mint a confirmed set."""
    project, target, user = _target(session)

    with pytest.raises(DomainError):
        _propose(session, project, target, user, origin="agent_proposed_human_confirmed")


# --- what is in it -----------------------------------------------------------


def test_residues_are_kept_in_order_and_de_duplicated(session: Session) -> None:
    project, target, user = _target(session)

    row = _propose(
        session, project, target, user,
        residues=[{"chain": "B", "seq": 31}, {"chain": "A", "seq": 164}, {"chain": "B", "seq": 31}],
    )

    assert row.residues == [{"chain": "B", "seq": 31}, {"chain": "A", "seq": 164}]


@pytest.mark.parametrize(
    "residues",
    [
        [],
        "A164",
        [{"chain": "A"}],
        [{"chain": "", "seq": 1}],
        [{"chain": "A", "seq": "the loop"}],
        [{"chain": "A", "seq": index} for index in range(hotspots.MAX_RESIDUES + 1)],
    ],
)
def test_a_set_that_cannot_be_acted_on_is_refused(session: Session, residues: object) -> None:
    project, target, user = _target(session)

    with pytest.raises(DomainError):
        _propose(session, project, target, user, residues=residues)


def test_the_residue_name_is_kept_when_given_because_a164_and_a164_arg_read_differently(
    session: Session,
) -> None:
    project, target, user = _target(session)

    row = _propose(session, project, target, user)

    assert row.residues[0]["name"] == "ARG"
    assert "name" not in row.residues[1]


# --- confirming and refusing --------------------------------------------------


def test_confirming_twice_is_not_a_conflict(session: Session) -> None:
    project, target, user = _target(session)
    row = _propose(session, project, target, user)
    hotspots.confirm(session, row, user=user)

    hotspots.confirm(session, row, user=user)

    assert row.status == "confirmed"


def test_a_rejected_set_stays_in_the_record_with_its_reason(session: Session) -> None:
    project, target, user = _target(session)
    row = _propose(session, project, target, user)

    hotspots.reject(session, row, user=user, reason="The loop is disordered in this model")

    assert row.status == "rejected"
    assert "disordered" in row.rationale
    with pytest.raises(DomainError):
        hotspots.confirm(session, row, user=user)


def test_a_confirmed_set_is_not_rejected_afterwards(session: Session) -> None:
    """A job may already have used it; the record does not get rewritten."""
    project, target, user = _target(session)
    row = _propose(session, project, target, user, origin="human")

    with pytest.raises(DomainError):
        hotspots.reject(session, row, user=user)


# --- reaching a job ------------------------------------------------------------


def test_only_a_confirmed_set_formats_into_a_design_parameter(session: Session) -> None:
    project, target, user = _target(session)
    row = _propose(session, project, target, user)

    with pytest.raises(DomainError):
        hotspots.as_residue_argument(row)

    hotspots.confirm(session, row, user=user)
    assert hotspots.as_residue_argument(row) == "A164,A168"


def test_listing_is_scoped_to_the_project_and_filterable_by_status(session: Session) -> None:
    project, target, user = _target(session)
    other_project, other_target, other_user = _target(session)
    _propose(session, project, target, user)
    confirmed = _propose(session, project, target, user, origin="human")
    _propose(session, other_project, other_target, other_user)

    assert len(hotspots.sets(session, project_id=project.id)) == 2
    assert [row.id for row in hotspots.sets(session, project_id=project.id, status="confirmed")] == [
        confirmed.id
    ]
    with pytest.raises(DomainError):
        hotspots.sets(session, project_id=project.id, status="pending")
