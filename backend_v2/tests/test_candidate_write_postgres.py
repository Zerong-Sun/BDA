"""Real concurrent sessions: unique-key replay and row-lock version checks.

Use an isolated disposable schema so committed test data cannot mix with projects.
"""
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.audit.models import AuditLog
from backend_v2.app.candidates.models import Candidate
from backend_v2.app.candidates.repository import CandidateRepository
from backend_v2.app.candidates.schemas import CandidateCreate, CandidateUpdate
from backend_v2.app.candidates.service import create_candidate, update_candidate
from backend_v2.app.core.database import engine as configured_engine
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import User
from backend_v2.app.projects.models import Project
from backend_v2.tests.test_copilot_agent_loop import _project
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

pytestmark = pytest.mark.skipif(os.getenv("BDA_V2_RUN_DB_TESTS") != "1", reason="PostgreSQL integration test disabled")


@pytest.fixture
def database():
    schema = f"candidate_review_test_{uuid.uuid4().hex}"
    engine = create_engine(configured_engine.url, execution_options={"schema_translate_map": {None: schema}})
    try:
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        with factory.begin() as session:
            project, user = _project(session)
            ids = project.id, user.id
        yield factory, ids
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        engine.dispose()


def test_simultaneous_identical_creates_return_one_committed_candidate(database, monkeypatch):
    factory, (project_id, user_id) = database
    barrier = threading.Barrier(2)
    local = threading.local()
    real_lookup = CandidateRepository.get_by_key

    def lookup(repository, project_id, key):
        found = real_lookup(repository, project_id, key)
        if not getattr(local, "looked_up", False):
            local.looked_up = True
            barrier.wait(timeout=10)
        return found

    monkeypatch.setattr(CandidateRepository, "get_by_key", lookup)

    def create():
        with factory.begin() as session:
            result = create_candidate(session, session.get(Project, project_id),
                                      CandidateCreate(candidate_key="one-key", name="One proposal"),
                                      session.get(User, user_id))
            return result.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create) for _ in range(2)]
        ids = [future.result(timeout=20) for future in futures]
    assert ids[0] == ids[1]
    with factory() as session:
        assert len(session.scalars(select(Candidate)).all()) == 1
        assert len(session.scalars(select(AuditLog).where(AuditLog.action == "candidate.create")).all()) == 1


def test_simultaneous_edits_produce_one_commit_and_one_version_conflict(database):
    factory, (project_id, user_id) = database
    with factory.begin() as session:
        candidate = create_candidate(session, session.get(Project, project_id),
                                     CandidateCreate(candidate_key="edit", name="Before"), session.get(User, user_id))
        candidate_id = candidate.id
    barrier = threading.Barrier(2)

    def edit(name):
        try:
            with factory.begin() as session:
                candidate = session.get(Candidate, candidate_id)
                project, user = session.get(Project, project_id), session.get(User, user_id)
                assert candidate.version == 1
                barrier.wait(timeout=10)
                update_candidate(session, project, candidate, CandidateUpdate(name=name), user, 1)
            return 200, name
        except DomainError as error:
            return error.status_code, name

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(edit, name) for name in ("First reviewer", "Second reviewer")]
        results = [future.result(timeout=20) for future in futures]
    assert sorted(status for status, _ in results) == [200, 412]
    with factory() as session:
        saved = session.get(Candidate, candidate_id)
        assert saved.version == 2
        assert saved.name == next(name for status, name in results if status == 200)
        assert len(session.scalars(select(AuditLog).where(AuditLog.action == "candidate.update")).all()) == 1
