"""Gap resolution on a research target: one attempt at a time, and a late result cannot win."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.candidates.models import Candidate
from backend_v2.app.candidates.service import (
    begin_gap_resolution,
    record_gap_resolution_operation,
    settle_gap_resolution,
)
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def session() -> Iterator[Session]:
    engine = enforce_foreign_keys(
        create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    )
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as opened:
        yield opened
    drop_all(engine, Base.metadata)


def _project(session: Session, name: str) -> Project:
    user = User(username=f"gap-{name}", display_name="G", role="researcher", enabled=True)
    organization = Organization(name=f"Gap Org {name}")
    session.add_all([user, organization])
    session.flush()
    project = Project(organization_id=organization.id, owner_id=user.id, name=name, project_type="research")
    session.add(project)
    session.flush()
    return project


def _target(session: Session, project: Project, kind: str = "research_target") -> Candidate:
    candidate = Candidate(project_id=project.id, candidate_key="C1", name="GPR65", candidate_kind=kind)
    session.add(candidate)
    session.flush()
    return candidate


def _reloaded(session: Session, candidate: Candidate) -> dict:
    session.commit()
    session.expire_all()
    return session.get(Candidate, candidate.id).properties["gap_resolution"]


def test_the_operation_id_is_saved_with_the_pending_attempt(session: Session) -> None:
    project = _project(session, "saved")
    candidate = _target(session, project)
    operation_id = uuid.uuid4()

    begin_gap_resolution(session, project, candidate.id)
    session.flush()
    record_gap_resolution_operation(candidate, operation_id)

    saved = _reloaded(session, candidate)
    assert saved["status"] == "pending"
    assert saved["attempt"] == 1
    assert saved["operation_id"] == str(operation_id)


def test_a_late_result_from_an_older_attempt_is_ignored(session: Session) -> None:
    project = _project(session, "race")
    candidate = _target(session, project)
    first, second = uuid.uuid4(), uuid.uuid4()
    begin_gap_resolution(session, project, candidate.id)
    record_gap_resolution_operation(candidate, first)
    session.commit()
    begin_gap_resolution(session, project, candidate.id)
    record_gap_resolution_operation(candidate, second)
    session.commit()

    assert settle_gap_resolution(session, candidate.id, str(first), {"status": "completed_with_failures"}) is True
    assert _reloaded(session, candidate)["status"] == "pending"

    settle_gap_resolution(session, candidate.id, str(second), {"status": "completed_with_remaining_scientific_gaps"})
    saved = _reloaded(session, candidate)
    assert saved["status"] == "completed_with_remaining_scientific_gaps"
    assert saved["attempt"] == 2


def test_settling_a_missing_target_reports_it(session: Session) -> None:
    assert settle_gap_resolution(session, uuid.uuid4(), "", {"status": "x"}) is False


@pytest.mark.parametrize("cross_project", [True, False])
def test_only_this_projects_research_targets_can_be_resolved(session: Session, cross_project: bool) -> None:
    owner = _project(session, f"owner-{cross_project}")
    candidate = _target(session, owner, kind="research_target" if cross_project else "design_candidate")
    caller = _project(session, f"caller-{cross_project}") if cross_project else owner

    with pytest.raises(DomainError) as raised:
        begin_gap_resolution(session, caller, candidate.id)
    assert raised.value.status_code == 404
