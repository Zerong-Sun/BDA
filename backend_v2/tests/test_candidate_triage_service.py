"""Triage over real metric rows: which numbers a candidate actually has.

The threshold arithmetic is covered as a pure function. What only appears here
is the join: several seeds of one metric arriving as separate rows, a method
and an assessor travelling from the row into the verdict, and a candidate in
another project not being judged at all.

The assessor case is the one worth having. A design scored only by the model
that produced it has cleared nothing independently, and a triage that returned
"tier_a" without saying so would be laundering self-assessment into a result.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.candidates.models import Candidate, CandidateMetric
from backend_v2.app.candidates.service import triage_candidate
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_counter = itertools.count()

TIERS = {
    "tier_b": {"pae_interaction": "< 7", "binder_plddt": "> 85"},
    "tier_a": {"pae_interaction": "< 15", "binder_plddt": "> 70"},
}


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
    user = User(username=f"tri-{n}", display_name="T", role="researcher", enabled=True)
    organization = Organization(name=f"Tri Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"tri-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project, user


def _candidate(session: Session, project: Project, metrics: list[tuple[str, float, str, str]]) -> Candidate:
    """A candidate and its metric rows.

    `candidate_metrics` is unique on (candidate, key, method, model_variant,
    condition), so that re-collecting an attempt updates a row instead of
    duplicating it. Several seeds of one prediction are distinguished by
    `model_variant`, which is what the AlphaFold 3 parser writes; the fixture
    numbers them the same way rather than colliding.
    """
    candidate = Candidate(
        project_id=project.id, candidate_key=f"c-{next(_counter)}", name="Design 3",
    )
    session.add(candidate)
    session.flush()
    seen: dict[tuple[str, str], int] = {}
    for key, value, method, assessor in metrics:
        index = seen.get((key, method), 0)
        seen[(key, method)] = index + 1
        session.add(
            CandidateMetric(
                candidate_id=candidate.id, metric_key=key, value=value,
                method=method, assessor=assessor, evidence_kind="predicted",
                model_variant=f"seed-{index}_sample-0",
            )
        )
    session.flush()
    return candidate


def test_a_candidate_clearing_every_threshold_reaches_the_stricter_tier(session: Session) -> None:
    project, _user = _project(session)
    candidate = _candidate(
        session, project,
        [("pae_interaction", 5.0, "alphafold3", "independent_model"),
         ("plddt", 91.0, "alphafold3", "independent_model")],
    )

    verdict = triage_candidate(session, project, candidate.id, TIERS)

    assert verdict["tier"] == "tier_b"
    assert verdict["metric_count"] == 2


def test_several_seeds_of_one_metric_are_one_criterion(session: Session) -> None:
    """Five rows, one question: the kernel chooses, and says which row it used."""
    project, _user = _project(session)
    candidate = _candidate(
        session, project,
        [("pae_interaction", value, "alphafold3", "independent_model") for value in (4.0, 9.0, 21.0)]
        + [("plddt", 88.0, "alphafold3", "independent_model")],
    )

    verdict = triage_candidate(session, project, candidate.id, TIERS)

    criteria = {item["name"]: item for item in verdict["criteria"]}
    assert len(verdict["criteria"]) == 2
    assert criteria["pae_interaction"]["value"] == 4.0
    assert verdict["metric_count"] == 4


def test_the_verdict_says_who_produced_the_deciding_number(session: Session) -> None:
    """Self-assessment must be visible, not laundered into a tier."""
    project, _user = _project(session)
    candidate = _candidate(
        session, project,
        [("pae_interaction", 5.0, "alphafold2_superfold", "design_model"),
         ("plddt", 91.0, "alphafold2_superfold", "design_model")],
    )

    verdict = triage_candidate(session, project, candidate.id, TIERS)

    assert {item["assessor"] for item in verdict["criteria"]} == {"design_model"}
    assert {item["method"] for item in verdict["criteria"]} == {"alphafold2_superfold"}


def test_a_design_nobody_has_measured_is_missing_rather_than_failed(session: Session) -> None:
    project, _user = _project(session)
    candidate = _candidate(session, project, [])

    verdict = triage_candidate(session, project, candidate.id, TIERS)

    assert verdict["tier"] is None
    assert verdict["missing"] == 2
    assert verdict["failed"] == 0


def test_a_partially_measured_design_separates_the_two_reasons(session: Session) -> None:
    project, _user = _project(session)
    candidate = _candidate(
        session, project, [("pae_interaction", 30.0, "alphafold3", "independent_model")]
    )

    verdict = triage_candidate(session, project, candidate.id, TIERS)

    outcomes = {item["name"]: item["outcome"] for item in verdict["criteria"]}
    assert outcomes == {"pae_interaction": "fail", "binder_plddt": "missing"}
    assert verdict["failed"] == 1 and verdict["missing"] == 1


def test_another_projects_candidate_is_not_judged(session: Session) -> None:
    project, _user = _project(session)
    other, _other_user = _project(session)
    candidate = _candidate(session, other, [("plddt", 90.0, "alphafold3", "independent_model")])

    with pytest.raises(DomainError) as failure:
        triage_candidate(session, project, candidate.id, TIERS)

    assert failure.value.status_code == 404


def test_an_unknown_candidate_is_a_404(session: Session) -> None:
    project, _user = _project(session)

    with pytest.raises(DomainError) as failure:
        triage_candidate(session, project, uuid.uuid4(), TIERS)

    assert failure.value.status_code == 404
