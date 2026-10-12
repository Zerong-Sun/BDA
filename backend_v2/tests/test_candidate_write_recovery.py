"""Recovery after a lost create response and competing edits preserves identity."""
import uuid

import pytest
from backend_v2.app.audit.models import AuditLog
from backend_v2.app.candidates.models import Candidate
from backend_v2.app.candidates.repository import CandidateRepository
from backend_v2.app.candidates.schemas import CandidateCreate, CandidateUpdate
from backend_v2.app.candidates.service import create_candidate, update_candidate
from backend_v2.app.core.problem import DomainError
from backend_v2.tests.test_copilot_agent_loop import _project
from backend_v2.tests.test_copilot_agent_loop import session as session_fixture
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError


@pytest.fixture(name="session")
def db_session():
    yield from session_fixture.__wrapped__()


def proposal(**changes):
    return CandidateCreate(candidate_key="manual-retry", name="Untested proposal", **changes)


def test_identical_retry_returns_saved_identity_without_duplicate_audit(session):
    project, user = _project(session)
    first = create_candidate(session, project, proposal(), user)
    session.commit()
    replay = create_candidate(session, project, proposal(), user)
    session.flush()
    assert replay.id == first.id and replay.version == 1
    assert len(session.scalars(select(Candidate)).all()) == 1
    logs = session.scalars(select(AuditLog).where(AuditLog.action == "candidate.create")).all()
    assert len(logs) == 1
    assert replay.status == "proposed" and replay.scores == {} and replay.score is None


def test_different_retry_reports_saved_id_and_preserves_original(session):
    project, user = _project(session)
    original = create_candidate(session, project, proposal(), user)
    session.flush()
    with pytest.raises(DomainError) as exc:
        create_candidate(session, project, proposal(properties={"sequence": "ACD"}), user)
    assert exc.value.status_code == 409
    assert exc.value.error_code == "candidate_key_conflict"
    assert exc.value.errors == [{"candidate_id": str(original.id)}]
    assert original.properties == {} and original.version == 1


def test_key_replay_is_project_scoped(session):
    project, user = _project(session)
    other, other_user = _project(session)
    first = create_candidate(session, project, proposal(), user)
    second = create_candidate(session, other, proposal(), other_user)
    assert first.id != second.id and second.project_id == other.id


@pytest.mark.parametrize("changed", [False, True])
def test_insert_race_recovers_through_savepoint(session, monkeypatch, changed):
    project, user = _project(session)
    first = create_candidate(session, project, proposal(), user)
    session.commit()
    real_lookup = CandidateRepository.get_by_key
    calls = 0

    def competing_insert(repository, project_id, key):
        nonlocal calls
        calls += 1
        # Simulate a competing commit between lookup and our unique-key insert.
        return None if calls == 1 else real_lookup(repository, project_id, key)

    monkeypatch.setattr(CandidateRepository, "get_by_key", competing_insert)
    if changed:
        with pytest.raises(DomainError) as exc:
            create_candidate(session, project, proposal(properties={"new": True}), user)
        assert exc.value.status_code == 409
    else:
        assert create_candidate(session, project, proposal(), user).id == first.id
    assert calls == 2
    # The outer transaction is still usable after the failed insert.
    assert session.scalar(select(Candidate.id)) == first.id
    session.commit()


def test_unrelated_integrity_failure_is_not_masked_as_replay(session):
    project, user = _project(session)
    with pytest.raises(IntegrityError):
        create_candidate(session, project, proposal(source_job_id=uuid.uuid4()), user)
    assert session.scalar(select(Candidate.id)) is None


def test_update_refreshes_stale_identity_before_version_check(session):
    project, user = _project(session)
    candidate = create_candidate(session, project, proposal(), user)
    session.flush()
    session.execute(update(Candidate).where(Candidate.id == candidate.id).values(name="Concurrent edit", version=2)
                    .execution_options(synchronize_session=False))
    assert candidate.version == 1  # Already-loaded API context is stale.
    with pytest.raises(DomainError) as exc:
        update_candidate(session, project, candidate, CandidateUpdate(name="Would overwrite"), user, 1)
    assert exc.value.status_code == 412
    assert candidate.name == "Concurrent edit" and candidate.version == 2


def test_update_uses_expected_version_preserving_scientific_fields(session):
    project, user = _project(session)
    candidate = create_candidate(session, project, proposal(properties={"sequence": "ACD", "untested": True}), user)
    result = update_candidate(session, project, candidate, CandidateUpdate(name="Better label"), user, 1)
    session.flush()
    assert result.id == candidate.id and result.version == 2
    assert result.properties == {"sequence": "ACD", "untested": True}
    assert result.status == "proposed" and result.scores == {}


def test_update_rejects_foreign_project(session):
    project, user = _project(session)
    other, _ = _project(session)
    candidate = create_candidate(session, project, proposal(), user)
    with pytest.raises(DomainError) as exc:
        update_candidate(session, other, candidate, CandidateUpdate(name="Wrong project"), user, 1)
    assert exc.value.status_code == 404 and candidate.version == 1
