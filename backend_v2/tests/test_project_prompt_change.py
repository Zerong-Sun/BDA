"""Rewriting the design prompt is a decision, not a silent overwrite.

The prompt is the project's brief: the goal tree and the open branches are derived from
it. Before this, `updateProjectPrompt` overwrote the text in place, so a rewrite left
everything downstream pointing at wording that no longer existed and gave no way to see
what the change had done. The rule here is that a real change costs one sentence of
justification, and buys a timeline entry carrying that sentence and the previous text.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.projects.schemas import ProjectUpdate
from backend_v2.app.projects.service import update_project
from backend_v2.app.timeline.models import ProjectTimelineEntry
from backend_v2.tests._sqlite import enforce_foreign_keys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

ORIGINAL = "design a sweet protein under 100 aa"
REWRITTEN = "design a sweet protein under 100 aa, single chain only"


@pytest.fixture
def env() -> Generator[dict]:
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://"))
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = User(username="pc", display_name="PC", role="admin", enabled=True)
        org = Organization(name="PC Org")
        session.add_all([user, org])
        session.flush()
        project = Project(
            organization_id=org.id,
            owner_id=user.id,
            name="PC",
            project_type="design",
            prompt=ORIGINAL,
        )
        session.add(project)
        session.flush()
        yield {"session": session, "user": user, "project": project}
    engine.dispose()


def _entries(session: Session) -> list[ProjectTimelineEntry]:
    return list(session.scalars(select(ProjectTimelineEntry)))


def test_changing_the_prompt_without_a_reason_is_refused(env) -> None:
    with pytest.raises(DomainError) as excinfo:
        update_project(
            env["session"],
            env["project"],
            ProjectUpdate(prompt=REWRITTEN),
            env["user"],
            env["project"].version,
        )
    assert excinfo.value.error_code == "project_prompt_change_reason_required"
    assert env["project"].prompt == ORIGINAL
    assert _entries(env["session"]) == []


def test_the_reason_and_the_previous_wording_both_land_on_the_timeline(env) -> None:
    update_project(
        env["session"],
        env["project"],
        ProjectUpdate(prompt=REWRITTEN, prompt_change_reason="mabinlin-2 is two chains; the brief has to say so"),
        env["user"],
        env["project"].version,
    )
    env["session"].flush()

    entries = _entries(env["session"])
    assert len(entries) == 1
    entry = entries[0]
    assert entry.entry_type == "decision"
    assert "mabinlin-2" in entry.summary
    # The old text is the only way to see what the change actually did.
    assert ORIGINAL in entry.body
    assert entry.project_id == env["project"].id
    assert env["project"].prompt == REWRITTEN


def test_re_saving_the_same_text_is_not_a_change(env) -> None:
    """A form that round-trips the whole object must not demand a justification."""
    update_project(
        env["session"],
        env["project"],
        ProjectUpdate(prompt=ORIGINAL, name="renamed"),
        env["user"],
        env["project"].version,
    )
    env["session"].flush()
    assert _entries(env["session"]) == []
    assert env["project"].name == "renamed"


def test_setting_the_first_prompt_is_not_a_change_either(env) -> None:
    """Nothing was superseded, so there is nothing to justify or to preserve."""
    project = env["project"]
    project.prompt = None
    env["session"].flush()

    update_project(env["session"], project, ProjectUpdate(prompt=ORIGINAL), env["user"], project.version)
    env["session"].flush()
    assert _entries(env["session"]) == []
    assert project.prompt == ORIGINAL


def test_the_reason_is_not_stored_on_the_project(env) -> None:
    """It belongs to the change, not to the current state - the project carries the
    prompt, and the timeline carries why it is that prompt."""
    update_project(
        env["session"],
        env["project"],
        ProjectUpdate(prompt=REWRITTEN, prompt_change_reason="narrowing to single chain"),
        env["user"],
        env["project"].version,
    )
    env["session"].flush()
    assert not hasattr(env["project"], "prompt_change_reason")


def test_updating_other_fields_still_needs_no_reason(env) -> None:
    update_project(
        env["session"],
        env["project"],
        ProjectUpdate(summary="s", status="active"),
        env["user"],
        env["project"].version,
    )
    env["session"].flush()
    assert _entries(env["session"]) == []
    assert env["project"].status == "active"
