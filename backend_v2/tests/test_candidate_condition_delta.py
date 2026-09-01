"""Δ between conditions must be storable, queryable, and never silently overwritten.

Before this, `_record_metrics` matched an existing row on (candidate, key, method,
variant) without `condition`, so a control score silently overwrote the target score
instead of accumulating beside it; a selectivity panel could never form.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from backend_v2.app.candidates.delta import compute_condition_deltas, upsert_condition_deltas
from backend_v2.app.candidates.models import Candidate, CandidateMetric
from backend_v2.app.candidates.repository import CandidateRepository
from backend_v2.app.compute.parsers.base import ParsedMetric
from backend_v2.app.compute.tasks import _record_metrics
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.tests._sqlite import enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def _metric(**overrides) -> CandidateMetric:
    defaults = dict(
        candidate_id=uuid.uuid4(),
        metric_key="iptm",
        value=0.8,
        method="boltz2",
        model_variant="",
        assessor="design_model",
        condition="ligand:TCI",
        unit="",
    )
    return CandidateMetric(**{**defaults, **overrides})


def test_two_conditions_produce_one_delta() -> None:
    thc = _metric(value=0.81, condition="ligand:TCI")
    cbd = _metric(value=0.86, condition="ligand:P0T")
    deltas = compute_condition_deltas([thc, cbd])
    assert len(deltas) == 1
    delta = deltas[0]
    assert delta.metric_key == "iptm"
    # Conditions sort lexicographically so the pairing is deterministic regardless of
    # input order: "ligand:P0T" < "ligand:TCI".
    assert (delta.condition_a, delta.condition_b) == ("ligand:P0T", "ligand:TCI")
    assert round(delta.value, 2) == round(0.86 - 0.81, 2)


def test_a_single_condition_produces_no_delta() -> None:
    assert compute_condition_deltas([_metric(condition="ligand:TCI")]) == []


def test_metrics_with_no_condition_are_ignored() -> None:
    assert compute_condition_deltas([_metric(condition=""), _metric(condition="")]) == []


def test_three_conditions_are_skipped_rather_than_guessed() -> None:
    """Which pair to compare becomes a modelling choice once there are three or more."""
    metrics = [_metric(condition=c) for c in ("ligand:TCI", "ligand:P0T", "ligand:E7Y")]
    assert compute_condition_deltas(metrics) == []


def test_two_rows_sharing_a_condition_are_ambiguous_and_skipped() -> None:
    """E.g. two seeds filed under the same condition label - "the" value is undefined."""
    metrics = [
        _metric(condition="ligand:TCI", value=0.80),
        _metric(condition="ligand:TCI", value=0.83),
        _metric(condition="ligand:P0T", value=0.70),
    ]
    assert compute_condition_deltas(metrics) == []


def test_mismatched_units_are_not_compared() -> None:
    metrics = [
        _metric(condition="ligand:TCI", unit="", value=0.8),
        _metric(condition="ligand:P0T", unit="angstrom", value=4.8),
    ]
    assert compute_condition_deltas(metrics) == []


def test_different_methods_are_kept_separate() -> None:
    """One model's target score must not be diffed against another model's control."""
    metrics = [
        _metric(condition="ligand:TCI", method="boltz2", value=0.87),
        _metric(condition="ligand:P0T", method="alphafold3", value=0.73),
    ]
    assert compute_condition_deltas(metrics) == []


def test_a_prior_delta_row_is_not_re_diffed() -> None:
    metrics = [
        _metric(condition="ligand:TCI", metric_key="iptm", value=0.87),
        _metric(condition="ligand:P0T", metric_key="iptm", value=0.73),
        _metric(condition="ligand:P0T vs ligand:TCI", metric_key="delta_iptm", value=-0.14, assessor="derived"),
    ]
    deltas = compute_condition_deltas(metrics)
    assert [d.metric_key for d in deltas] == ["iptm"]


# --- database-backed behaviour -------------------------------------------------------


@pytest.fixture
def db_session() -> Generator[Session]:
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://"))
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def _project(session: Session) -> Project:
    user = User(username="delta-tester", display_name="Delta Tester", role="admin", enabled=True)
    org = Organization(name="Delta Org")
    session.add_all([user, org])
    session.flush()
    project = Project(organization_id=org.id, owner_id=user.id, name="Delta", project_type="design")
    session.add(project)
    session.flush()
    session.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
    session.flush()
    return project


def test_a_second_condition_no_longer_overwrites_the_first(db_session: Session) -> None:
    """The bug this fix closes: recording CBD's score used to erase THC's."""
    project = _project(db_session)
    candidate = Candidate(project_id=project.id, candidate_key="b0_c4", name="b0_c4")
    db_session.add(candidate)
    db_session.flush()

    _record_metrics(
        db_session,
        candidate,
        [ParsedMetric(key="iptm", value=0.94, method="alphafold3", condition="ligand:TCI")],
        job_id=None,
    )
    _record_metrics(
        db_session,
        candidate,
        [ParsedMetric(key="iptm", value=0.73, method="alphafold3", condition="ligand:P0T")],
        job_id=None,
    )
    db_session.flush()

    rows = CandidateRepository(db_session).metrics_for(candidate.id)
    by_condition = {r.condition: r.value for r in rows}
    assert by_condition == {"ligand:TCI": 0.94, "ligand:P0T": 0.73}


def test_recollecting_the_same_condition_still_updates_in_place(db_session: Session) -> None:
    project = _project(db_session)
    candidate = Candidate(project_id=project.id, candidate_key="b0_c4", name="b0_c4")
    db_session.add(candidate)
    db_session.flush()

    for value in (0.90, 0.94):
        _record_metrics(
            db_session,
            candidate,
            [ParsedMetric(key="iptm", value=value, method="alphafold3", condition="ligand:TCI")],
            job_id=None,
        )
        db_session.flush()

    rows = CandidateRepository(db_session).metrics_for(candidate.id)
    assert len(rows) == 1 and rows[0].value == 0.94


def test_upsert_condition_deltas_writes_a_queryable_delta_metric(db_session: Session) -> None:
    project = _project(db_session)
    candidate = Candidate(project_id=project.id, candidate_key="b0_c4", name="b0_c4")
    db_session.add(candidate)
    db_session.flush()

    _record_metrics(
        db_session,
        candidate,
        [
            ParsedMetric(key="iptm", value=0.94, method="alphafold3", condition="ligand:TCI"),
            ParsedMetric(key="iptm", value=0.73, method="alphafold3", condition="ligand:P0T"),
        ],
        job_id=None,
    )
    db_session.flush()

    written = upsert_condition_deltas(db_session, candidate.id)
    assert len(written) == 1
    delta_row = written[0]
    assert delta_row.metric_key == "delta_iptm"
    assert round(delta_row.value, 2) == round(0.73 - 0.94, 2)
    assert delta_row.assessor == "derived"
    assert delta_row.condition == "ligand:P0T vs ligand:TCI"

    # Idempotent: recomputing with unchanged inputs updates the row rather than
    # duplicating it.
    upsert_condition_deltas(db_session, candidate.id)
    rows = CandidateRepository(db_session).metrics_for(candidate.id)
    assert sum(1 for r in rows if r.metric_key == "delta_iptm") == 1


def test_upsert_condition_deltas_is_a_no_op_with_only_one_condition(db_session: Session) -> None:
    project = _project(db_session)
    candidate = Candidate(project_id=project.id, candidate_key="b0_c4", name="b0_c4")
    db_session.add(candidate)
    db_session.flush()

    _record_metrics(
        db_session,
        candidate,
        [ParsedMetric(key="iptm", value=0.94, method="alphafold3", condition="ligand:TCI")],
        job_id=None,
    )
    db_session.flush()

    assert upsert_condition_deltas(db_session, candidate.id) == []
