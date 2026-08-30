"""The project decision record: storage, chronological paging, and link integrity.

The behaviours worth pinning are the ones that make the table usable by a *later*
project, not just by the one that motivated it:

- ordering is by when things happened, not by insertion order or id;
- the keyset cursor survives entries that share a timestamp (otherwise a long timeline
  silently drops or repeats rows at page boundaries);
- links cannot cross projects or point at themselves;
- the vocabulary is closed, so a typo'd entry_type fails at the edge instead of becoming
  a category nobody ever queries again.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.models import Base
from backend_v2.app.core.pagination import decode_time_cursor, encode_time_cursor
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.app.timeline.models import ENTRY_TYPES, OUTCOMES, ProjectTimelineEntry
from backend_v2.app.timeline.repository import TimelineRepository
from backend_v2.app.timeline.schemas import TimelineEntryCreate, TimelineEntryUpdate
from backend_v2.app.timeline.service import create_entry, update_entry
from backend_v2.tests._sqlite import enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BASE = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


@pytest.fixture
def env() -> Generator[dict]:
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://"))
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = User(username="tl", display_name="TL", role="admin", enabled=True)
        org = Organization(name="TL Org")
        session.add_all([user, org])
        session.flush()
        project = Project(organization_id=org.id, owner_id=user.id, name="TL", project_type="design")
        other = Project(organization_id=org.id, owner_id=user.id, name="Other", project_type="design")
        session.add_all([project, other])
        session.flush()
        session.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
        session.flush()
        yield {"session": session, "user": user, "project": project, "other": other}
    engine.dispose()


def _add(env, *, title: str, occurred_at: datetime, **kwargs) -> ProjectTimelineEntry:
    payload = TimelineEntryCreate(title=title, occurred_at=occurred_at, **kwargs)
    return create_entry(env["session"], env["project"], payload, env["user"])


def test_timeline_reads_in_time_order_not_insertion_order(env) -> None:
    """Entries are usually written up after the fact, often out of order."""
    _add(env, title="written second, happened later", occurred_at=BASE + timedelta(days=2))
    _add(env, title="written first, happened earlier", occurred_at=BASE)
    env["session"].flush()

    rows = TimelineRepository(env["session"]).list_project(env["project"].id, None, 50)
    assert [r.title for r in rows] == [
        "written first, happened earlier",
        "written second, happened later",
    ]


def test_keyset_paging_does_not_lose_entries_sharing_a_timestamp(env) -> None:
    """Two entries can share an instant; a timestamp-only cursor would skip one."""
    same = BASE
    for n in range(4):
        _add(env, title=f"same-instant-{n}", occurred_at=same)
    _add(env, title="later", occurred_at=same + timedelta(hours=1))
    env["session"].flush()

    repo = TimelineRepository(env["session"])
    seen: list[str] = []
    cursor = None
    for _ in range(10):  # bounded so a paging bug fails instead of hanging
        rows = repo.list_project(env["project"].id, cursor, 2)
        page = rows[:2]
        seen.extend(r.title for r in page)
        if len(rows) <= 2:
            break
        cursor = decode_time_cursor(encode_time_cursor(page[-1].occurred_at, page[-1].id))

    assert sorted(seen) == sorted([f"same-instant-{n}" for n in range(4)] + ["later"])
    assert len(seen) == len(set(seen)), "an entry was returned on two pages"


def test_filters_answer_the_questions_the_table_exists_for(env) -> None:
    _add(env, title="a plan", occurred_at=BASE, entry_type="plan", phase="phase-1")
    _add(env, title="a dead end", occurred_at=BASE + timedelta(days=1), entry_type="result",
         phase="phase-1", outcome="refuted")
    _add(env, title="phase 2 decision", occurred_at=BASE + timedelta(days=2),
         entry_type="decision", phase="phase-2")
    env["session"].flush()
    repo = TimelineRepository(env["session"])

    assert [r.title for r in repo.list_project(env["project"].id, None, 50, outcome="refuted")] == ["a dead end"]
    assert [r.title for r in repo.list_project(env["project"].id, None, 50, phase="phase-2")] == ["phase 2 decision"]
    assert [r.title for r in repo.list_project(env["project"].id, None, 50, entry_type="plan")] == ["a plan"]


def test_unknown_entry_type_and_outcome_are_rejected_at_the_edge() -> None:
    with pytest.raises(ValueError):
        TimelineEntryCreate(title="x", occurred_at=BASE, entry_type="brainstorm")
    with pytest.raises(ValueError):
        TimelineEntryCreate(title="x", occurred_at=BASE, outcome="probably")
    # every declared value is actually accepted
    for value in ENTRY_TYPES:
        TimelineEntryCreate(title="x", occurred_at=BASE, entry_type=value)
    for value in OUTCOMES:
        TimelineEntryCreate(title="x", occurred_at=BASE, outcome=value)


def test_provenance_keys_are_closed_and_must_hold_lists() -> None:
    """A fifth spelling of 'job_ids' is a key nobody will ever query."""
    with pytest.raises(ValueError):
        TimelineEntryCreate(title="x", occurred_at=BASE, provenance={"jobIds": ["a"]})
    with pytest.raises(ValueError):
        TimelineEntryCreate(title="x", occurred_at=BASE, provenance={"job_ids": "not-a-list"})
    ok = TimelineEntryCreate(
        title="x", occurred_at=BASE, provenance={"job_ids": ["4103824"], "external_refs": ["lsf:4103824"]}
    )
    assert ok.provenance["job_ids"] == ["4103824"]


def test_links_cannot_cross_projects(env) -> None:
    """Otherwise one project's reasoning leaks into another's record."""
    foreign = create_entry(
        env["session"], env["other"], TimelineEntryCreate(title="elsewhere", occurred_at=BASE), env["user"]
    )
    env["session"].flush()
    with pytest.raises(DomainError) as excinfo:
        _add(env, title="links out", occurred_at=BASE, caused_by_id=foreign.id)
    assert excinfo.value.error_code == "timeline_link_not_found"


def test_entry_cannot_supersede_itself(env) -> None:
    entry = _add(env, title="self", occurred_at=BASE)
    env["session"].flush()
    with pytest.raises(DomainError) as excinfo:
        update_entry(
            env["session"], env["project"], entry,
            TimelineEntryUpdate(supersedes_id=entry.id), entry.version,
        )
    assert excinfo.value.error_code == "timeline_self_link"


def test_superseded_entry_survives_and_stays_linked(env) -> None:
    """Overturned reasoning is evidence about how the project went - not garbage."""
    original = _add(env, title="believed X", occurred_at=BASE, outcome="supported")
    env["session"].flush()
    replacement = _add(
        env, title="X was wrong", occurred_at=BASE + timedelta(days=1),
        outcome="refuted", supersedes_id=original.id,
    )
    env["session"].flush()

    rows = TimelineRepository(env["session"]).list_project(env["project"].id, None, 50)
    assert [r.title for r in rows] == ["believed X", "X was wrong"]
    assert replacement.supersedes_id == original.id


def test_code_refs_round_trip_as_dicts(env) -> None:
    """The 'which script produced this' question has to survive storage."""
    entry = _add(
        env, title="ran the parser", occurred_at=BASE,
        code_refs=[{"path": "scripts/collect_af3_iptm.py", "role": "parse AF3 ipTM"}],
    )
    env["session"].flush()
    stored = TimelineRepository(env["session"]).get(entry.id)
    assert stored.code_refs == [{"path": "scripts/collect_af3_iptm.py", "role": "parse AF3 ipTM"}]


def test_version_conflict_is_refused(env) -> None:
    entry = _add(env, title="x", occurred_at=BASE)
    env["session"].flush()
    with pytest.raises(DomainError) as excinfo:
        update_entry(
            env["session"], env["project"], entry, TimelineEntryUpdate(title="y"), entry.version + 1
        )
    assert excinfo.value.error_code == "version_conflict"


def test_model_and_migration_declare_the_same_indexes() -> None:
    """A migration that drifts from the model is a production-only failure."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0035_project_timeline.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    migration_source = path.read_text()
    for index in ProjectTimelineEntry.__table__.indexes:
        assert index.name in migration_source, f"index {index.name} is in the model but not the migration"
    assert module.TABLE == ProjectTimelineEntry.__tablename__
