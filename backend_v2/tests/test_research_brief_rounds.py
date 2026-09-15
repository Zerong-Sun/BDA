"""A review-round progress note must never become a project's review document."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.research import workspace
from backend_v2.app.research.models import PROGRESS_NOTE_STATUS, ResearchBrief
from backend_v2.app.research.schemas import BriefCreate
from backend_v2.app.research.service import create_brief
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _session(engine) -> Session:
    return sessionmaker(engine, expire_on_commit=False)()


def _engine():
    engine = enforce_foreign_keys(
        create_engine(
            "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    )
    Base.metadata.create_all(engine)
    return engine


def _project(session: Session, name: str) -> tuple[Project, User]:
    user = User(username=f"owner-{name}", display_name="Owner", role="admin", enabled=True)
    organization = Organization(name=f"Org {name}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=name, project_type="research"
    )
    session.add(project)
    session.flush()
    return project, user


def test_a_round_stamped_brief_is_recorded_as_a_progress_note() -> None:
    engine = _engine()
    try:
        with _session(engine) as session:
            project, user = _project(session, "rounds")

            round_note = create_brief(
                session,
                project,
                BriefCreate(
                    title="2026-09-14 结果验收与下一步｜rounds",
                    content="本轮状态：报告所列本步完成。",
                    scope={"portfolio_review_key": "review-round-1", "snapshot_at": "x"},
                ),
                user,
            )
            ordinary = create_brief(
                session,
                project,
                BriefCreate(title="rounds — Project Review", content="# Project Review", scope={}),
                user,
            )

            # The writer sets the scope key itself, so no title or length guessing is needed.
            assert round_note.status == PROGRESS_NOTE_STATUS
            # An ordinary brief keeps the column default and is untouched by the rule.
            assert ordinary.status == "draft"
    finally:
        drop_all(engine, Base.metadata)


def test_a_newer_progress_note_cannot_displace_the_review_document() -> None:
    engine = _engine()
    try:
        with _session(engine) as session:
            project, user = _project(session, "ranking")
            opened = datetime(2026, 9, 1, tzinfo=UTC)
            review = ResearchBrief(
                project_id=project.id, created_by=user.id, title="ranking — Project Review",
                content="# Project Review", status="draft", created_at=opened,
            )
            note = ResearchBrief(
                project_id=project.id, created_by=user.id, title="2026-09-14 结果验收与下一步",
                content="本轮状态：报告所列本步完成。", status=PROGRESS_NOTE_STATUS,
                created_at=opened + timedelta(days=13),
            )
            session.add_all([review, note])
            session.commit()

            # Newer, but a progress note ranks below an ordinary brief.
            chosen = workspace.preferred_review_brief(session, project.id)
            assert chosen is not None and chosen.title == "ranking — Project Review"

            # And an accepted review still outranks everything.
            accepted = ResearchBrief(
                project_id=project.id, created_by=user.id, title="ranking — accepted review",
                content="# Accepted", status="accepted", created_at=opened - timedelta(days=30),
            )
            session.add(accepted)
            session.commit()
            assert workspace.preferred_review_brief(session, project.id).status == "accepted"
    finally:
        drop_all(engine, Base.metadata)


def test_a_project_with_only_progress_notes_still_shows_one() -> None:
    """Several archived projects have nothing else; showing nothing would be a regression."""
    engine = _engine()
    try:
        with _session(engine) as session:
            project, user = _project(session, "notes-only")
            opened = datetime(2026, 9, 1, tzinfo=UTC)
            session.add_all([
                ResearchBrief(
                    project_id=project.id, created_by=user.id, title="older note",
                    content="first", status=PROGRESS_NOTE_STATUS, created_at=opened,
                ),
                ResearchBrief(
                    project_id=project.id, created_by=user.id, title="newer note",
                    content="second", status=PROGRESS_NOTE_STATUS,
                    created_at=opened + timedelta(days=2),
                ),
            ])
            session.commit()

            chosen = workspace.preferred_review_brief(session, project.id)
            assert chosen is not None and chosen.title == "newer note"
    finally:
        drop_all(engine, Base.metadata)
