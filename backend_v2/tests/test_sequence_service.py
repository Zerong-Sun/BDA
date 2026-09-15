"""Resolving an id to a sequence, and the rule about what comes back.

The kernels are tested as pure functions. What is only testable here is the
resolution: three places a sequence lives, a project boundary around each, and
the distinction between "no such row" and "that row has no sequence" - which
are different problems for the reader and must not share a status code.

The last test is the one that matters beyond this module. A registered protein's
`sequence` column is the only plaintext copy the platform holds, and the API
that serves it deliberately returns the digest instead. A tool that resolved a
protein id and handed the residues back to a model would undo that quietly.
"""

from __future__ import annotations

import itertools
import json
import uuid
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.candidates.models import Candidate
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.sequences import kernels, service
from backend_v2.app.targets.models import Target
from backend_v2.app.wetlab.models import Protein
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_counter = itertools.count()
BINDER = "GSEQANGSTKLDGAMEEKWACLLEQAKKLLEEC"


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
    user = User(username=f"seq-{n}", display_name="S", role="researcher", enabled=True)
    organization = Organization(name=f"Seq Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"seq-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project, user


def _candidate(session: Session, project: Project, *, sequence: str | None = BINDER) -> Candidate:
    row = Candidate(
        project_id=project.id,
        candidate_key=f"cand-{next(_counter)}",
        name="Design 7",
        properties={"sequence": sequence} if sequence is not None else {},
    )
    session.add(row)
    session.flush()
    return row


# --- the three sources --------------------------------------------------------


def test_a_candidates_designed_sequence_is_read_from_where_the_parsers_write_it(
    session: Session,
) -> None:
    project, _user = _project(session)
    candidate = _candidate(session, project)

    result = service.analyse(session, project.id, candidate_id=candidate.id)

    assert result["source"]["kind"] == "candidate"
    assert result["source"]["name"] == "Design 7"
    assert result["properties"]["length"] == len(BINDER)


def test_a_target_sequence_resolves(session: Session) -> None:
    project, _user = _project(session)
    target = Target(project_id=project.id, name="PD-1", sequence=BINDER)
    session.add(target)
    session.flush()

    result = service.analyse(session, project.id, target_id=target.id)

    assert result["source"]["kind"] == "target"
    assert "n_glycosylation" in result["summary"]["high_severity_kinds"]


def test_a_registered_construct_resolves_and_keeps_the_library_digest(session: Session) -> None:
    """The row's own digest, not a recomputed one: it is the construct's identity."""
    project, user = _project(session)
    protein = Protein(
        project_id=project.id, name="Binder-1", sequence=BINDER,
        sequence_sha256="f" * 64, length=len(BINDER), created_by=user.id,
    )
    session.add(protein)
    session.flush()

    result = service.analyse(session, project.id, protein_id=protein.id)

    assert result["source"]["kind"] == "protein"
    assert result["source"]["sequence_sha256"] == "f" * 64


def test_a_pasted_sequence_needs_no_row_at_all(session: Session) -> None:
    project, _user = _project(session)

    result = service.analyse(session, project.id, sequence=BINDER)

    assert result["source"]["kind"] == "sequence"
    assert len(result["source"]["sequence_sha256"]) == 64


# --- boundaries ----------------------------------------------------------------


def test_naming_no_source_or_two_is_refused(session: Session) -> None:
    project, _user = _project(session)
    candidate = _candidate(session, project)

    with pytest.raises(DomainError):
        service.analyse(session, project.id)
    with pytest.raises(DomainError):
        service.analyse(session, project.id, sequence=BINDER, candidate_id=candidate.id)


def test_a_row_without_a_sequence_says_so_rather_than_reporting_nothing(session: Session) -> None:
    """422 and not 404: the candidate is right there, it just has no sequence."""
    project, _user = _project(session)
    candidate = _candidate(session, project, sequence=None)

    with pytest.raises(DomainError) as failure:
        service.analyse(session, project.id, candidate_id=candidate.id)

    assert failure.value.status_code == 422
    assert "no recorded sequence" in failure.value.detail


def test_another_projects_candidate_is_not_analysed(session: Session) -> None:
    project, _user = _project(session)
    other, _other_user = _project(session)
    candidate = _candidate(session, other)

    with pytest.raises(DomainError) as failure:
        service.analyse(session, project.id, candidate_id=candidate.id)

    assert failure.value.status_code == 404


def test_an_unreadable_stored_sequence_is_reported_as_such(session: Session) -> None:
    project, _user = _project(session)
    candidate = _candidate(session, project, sequence="???")

    with pytest.raises(DomainError) as failure:
        service.analyse(session, project.id, candidate_id=candidate.id)

    assert failure.value.status_code == 422


def test_the_patch_settings_reach_the_kernels(session: Session) -> None:
    project, _user = _project(session)

    result = service.analyse(session, project.id, sequence=BINDER, window=7, threshold=2.5)

    assert result["patch_settings"] == {"window": 7, "threshold": 2.5}


# --- the privacy rule -----------------------------------------------------------


def test_no_source_ever_returns_the_plaintext_sequence(session: Session) -> None:
    project, user = _project(session)
    candidate = _candidate(session, project)
    protein = Protein(
        project_id=project.id, name="Binder-1", sequence=BINDER,
        sequence_sha256=kernels.sanitise(BINDER) and "a" * 64, length=len(BINDER), created_by=user.id,
    )
    target = Target(project_id=project.id, name="PD-1", sequence=BINDER)
    session.add_all([protein, target])
    session.flush()

    for kwargs in (
        {"candidate_id": candidate.id},
        {"protein_id": protein.id},
        {"target_id": target.id},
        {"sequence": BINDER},
    ):
        serialised = json.dumps(service.analyse(session, project.id, **kwargs))
        assert BINDER not in serialised
        assert BINDER[:15] not in serialised


def test_an_unknown_id_is_a_404_for_every_source(session: Session) -> None:
    project, _user = _project(session)

    for kwargs in ({"candidate_id": uuid.uuid4()}, {"target_id": uuid.uuid4()}, {"protein_id": uuid.uuid4()}):
        with pytest.raises(DomainError) as failure:
            service.analyse(session, project.id, **kwargs)
        assert failure.value.status_code == 404
