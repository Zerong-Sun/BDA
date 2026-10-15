"""Opt-in PostgreSQL JSON-tag search, isolated in a disposable random schema."""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.config import get_settings
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.knowledge.models import KnowledgeEntry
from backend_v2.app.knowledge.repository import KnowledgeRepository
from backend_v2.app.projects.models import Project
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DATABASE_URL = os.getenv("BDA_GATE_TEST_DATABASE_URL") or (
    get_settings().database_url if os.getenv("BDA_V2_RUN_DB_TESTS") == "1" else None
)
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="Disposable PostgreSQL not configured")


def test_postgres_json_tag_search_filters_before_limits():
    assert DATABASE_URL is not None
    admin = create_engine(DATABASE_URL)
    schema = "knowledge_search_" + uuid.uuid4().hex
    engine = create_engine(DATABASE_URL, connect_args={"options": f"-csearch_path={schema}"})
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            user = User(username="knowledge-test", display_name="Test", role="researcher")
            org = Organization(name="Synthetic knowledge search")
            session.add_all([user, org])
            session.flush()
            project = Project(organization_id=org.id, owner_id=user.id, name="Search test", project_type="design")
            other = Project(organization_id=org.id, owner_id=user.id, name="Other test", project_type="design")
            session.add_all([project, other])
            session.flush()
            moment = datetime(2025, 1, 1, tzinfo=UTC)
            old = KnowledgeEntry(id=uuid.UUID(int=1), project_id=project.id, created_by=user.id, title="Historical assay",
                                 content="Observation", entry_type="note", source={}, tags=["抗体_100%", "CaseFold"],
                                 created_at=moment, updated_at=moment)
            newer = KnowledgeEntry(id=uuid.UUID(int=3), project_id=project.id, created_by=user.id, title="New assay",
                                   content="Observation", entry_type="note", source={}, tags=["抗体_100%"])
            foreign = KnowledgeEntry(project_id=other.id, created_by=user.id, title="Foreign assay", content="Private",
                                     entry_type="note", source={}, tags=["抗体_100%"])
            session.add_all([old, newer, foreign])
            session.add_all([KnowledgeEntry(project_id=project.id, created_by=user.id, title=f"Unrelated {index}", content="Observation",
                                           entry_type="note", source={}, tags=["抗体Z1000"],
                                           created_at=moment + timedelta(days=1), updated_at=moment + timedelta(days=1)) for index in range(520)])
            session.flush()
            repository = KnowledgeRepository(session)
            assert [row.id for row in repository.search(project.id, "casefold")] == [old.id]
            assert {row.id for row in repository.search(project.id, "抗体_100%")} == {old.id, newer.id}
            assert repository.search(project.id, "Foreign") == []
            assert repository.list_project(project.id, None, 1, query="抗体_100%", entry_type="draft") == []
            rows = repository.list_project(project.id, None, 1, query="抗体_100%", entry_type="note")
            assert [row.id for row in rows] == [old.id, newer.id]  # limit + 1 for keyset continuation
            assert [row.id for row in repository.list_project(project.id, old.id, 1, query="抗体_100%")] == [newer.id]
            session.rollback()
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()
