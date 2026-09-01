"""Turning a project's brief into the starting shape of its decision record.

`projects.prompt` has been required since the project chooser started demanding it, and
nothing downstream read it. This is the path that consumes it - and the property worth
pinning is not that it works, but that it cannot be short-circuited: a model proposes,
a person submits, and there is no third door.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.research import goals
from backend_v2.app.research.models import DecisionTreeDraft
from backend_v2.app.research.schemas import (
    DecisionTreeDraftCreate,
    DecisionTreeProposal,
)
from backend_v2.app.timeline.models import ProjectTimelineEntry
from backend_v2.tests._sqlite import enforce_foreign_keys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

PROMPT = "Design a sweet protein under 100 aa for beverage use."

PROPOSAL = {
    "goals": [
        {
            "title": "an expressible candidate",
            "detail": "",
            "children": [{"title": "disulfide integrity", "detail": "", "children": []}],
        },
        {"title": "safety", "detail": "", "children": []},
    ],
    "branches": [
        {
            "title": "does it fold as a monomer?",
            "summary": "",
            "lane": "dry",
            "goal_title": "disulfide integrity",
            "alternatives": [],
        },
        {
            "title": "does it activate the human receptor?",
            "summary": "",
            "lane": "wet",
            "goal_title": "safety",
            "alternatives": [{"option": "infer from docking score", "rejected_because": "not a functional claim"}],
        },
    ],
}


@pytest.fixture
def env() -> Iterator[dict]:
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://"))
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = User(username="dt", display_name="DT", role="admin", enabled=True)
        org = Organization(name="DT Org")
        session.add_all([user, org])
        session.flush()
        project = Project(
            organization_id=org.id, owner_id=user.id, name="DT", project_type="design", prompt=PROMPT
        )
        session.add(project)
        session.flush()
        yield {"session": session, "user": user, "project": project}
    engine.dispose()


def _import(env, payload=None):
    return goals.import_decision_tree(
        env["session"], env["project"], env["user"], DecisionTreeProposal.model_validate(payload or PROPOSAL)
    )


# --- the proposal shape ---------------------------------------------------------------


def test_a_branch_attaches_to_a_goal_by_a_title_that_must_exist() -> None:
    """An unmatched title would silently reparent the branch to the root, and a branch
    filed under the wrong question is worse than one that failed to file."""
    bad = {**PROPOSAL, "branches": [{**PROPOSAL["branches"][0], "goal_title": "nonexistent"}]}
    with pytest.raises(ValueError, match="no matching goal"):
        DecisionTreeProposal.model_validate(bad)


def test_duplicate_goal_titles_are_rejected_because_attachment_is_by_title() -> None:
    bad = {"goals": [{"title": "A"}, {"title": "A"}], "branches": []}
    with pytest.raises(ValueError, match="unique"):
        DecisionTreeProposal.model_validate(bad)


def test_the_proposal_is_bounded_so_it_stays_reviewable() -> None:
    """A reviewer facing forty items stops reviewing and starts accepting, which defeats
    the only safeguard in this whole path."""
    with pytest.raises(ValueError, match="at most"):
        DecisionTreeProposal.model_validate(
            {"goals": [{"title": f"g{n}"} for n in range(13)], "branches": []}
        )
    with pytest.raises(ValueError, match="deeper than"):
        DecisionTreeProposal.model_validate(
            {"goals": [{"title": "a", "children": [{"title": "b", "children": [{"title": "c", "children": [{"title": "d"}]}]}]}], "branches": []}
        )


def test_a_branch_lane_must_be_stated_and_real() -> None:
    with pytest.raises(ValueError):
        DecisionTreeProposal.model_validate(
            {"goals": [{"title": "A"}], "branches": [{"title": "q", "goal_title": "A", "lane": "maybe"}]}
        )
    with pytest.raises(ValueError):
        DecisionTreeProposal.model_validate(
            {"goals": [{"title": "A"}], "branches": [{"title": "q", "goal_title": "A"}]}
        )


# --- landing it -----------------------------------------------------------------------


def test_import_creates_the_nested_goals_and_hangs_the_branches_off_them(env) -> None:
    created, entries = _import(env)
    env["session"].flush()

    assert [goal.title for goal in created] == [
        "an expressible candidate",
        "disulfide integrity",
        "safety",
    ]
    # The child really is a child, not a second root.
    assert created[1].parent_id == created[0].id
    assert created[2].parent_id is None

    grouped = goals.links_for(env["session"], [goal.id for goal in created])
    assert [link.resource_type for link in grouped[created[1].id]] == ["timeline_entry"]
    assert grouped[created[1].id][0].resource_id == entries[0].id
    assert grouped[created[2].id][0].resource_id == entries[1].id
    assert grouped[created[0].id] == []


def test_every_imported_branch_is_a_question_not_a_conclusion(env) -> None:
    """The one property that keeps a bootstrapped tree honest.

    A branch nobody has answered must carry no outcome, no evidence and no decision
    number - the tree view then marks it "no evidence linked", which is the correct
    reading, and D-numbers stay the orchestrator's to allocate.
    """
    _, entries = _import(env)
    env["session"].flush()
    for entry in entries:
        assert entry.entry_type == "decision"
        assert entry.outcome == "unspecified"
        assert entry.provenance == {}
        assert entry.decision_ref is None
        assert "bootstrap" in entry.tags


def test_a_wet_branch_lands_without_bench_evidence_it_cannot_have_yet(env) -> None:
    """The lane rule keys on settledness, not on the lane alone.

    Otherwise writing down "does it activate the human receptor?" before running the
    assay would be impossible, and the question would stay in prose - which is where
    these questions were already being lost.
    """
    _, entries = _import(env)
    env["session"].flush()
    wet = [entry for entry in entries if entry.lane == "wet"]
    assert len(wet) == 1
    assert wet[0].provenance == {}


def test_rejected_options_survive_the_import(env) -> None:
    _, entries = _import(env)
    env["session"].flush()
    wet = next(entry for entry in entries if entry.lane == "wet")
    assert wet.alternatives == [
        {"option": "infer from docking score", "rejected_because": "not a functional claim"}
    ]


def test_importing_nothing_is_allowed_and_writes_nothing(env) -> None:
    """The reviewer rejecting every item is a legitimate outcome, not an error."""
    created, entries = _import(env, {"goals": [], "branches": []})
    env["session"].flush()
    assert created == [] and entries == []
    assert env["session"].scalars(select(ProjectTimelineEntry)).all() == []


# --- the draft, and the door that does not exist ---------------------------------------


def test_a_draft_needs_a_prompt_to_be_drafted_from(env) -> None:
    """A tree drafted from a project name is a guess wearing the shape of a plan."""
    env["project"].prompt = "   "
    env["session"].flush()
    with pytest.raises(DomainError) as excinfo:
        goals.create_decision_tree_draft(
            env["session"], env["project"], env["user"], DecisionTreeDraftCreate()
        )
    assert excinfo.value.error_code == "project_prompt_missing"


def test_the_draft_copies_the_prompt_rather_than_referencing_it(env) -> None:
    """The prompt can be rewritten - that is now a recorded decision precisely because it
    happens - and a draft has to stay interpretable afterwards."""
    goals.create_decision_tree_draft(
        env["session"], env["project"], env["user"], DecisionTreeDraftCreate()
    )
    env["session"].flush()
    draft = env["session"].scalars(select(DecisionTreeDraft)).one()
    assert draft.request["prompt"] == PROMPT
    assert draft.status == "pending"
    assert draft.draft == {}

    env["project"].prompt = "something else entirely"
    env["session"].flush()
    assert draft.request["prompt"] == PROMPT


def test_no_service_function_imports_a_stored_draft() -> None:
    """The per-item review is unskippable because nothing can skip it.

    If a `import_draft(draft_id)` ever appears, the safeguard is gone: a model would be
    deciding what a project's goals are. This test is the tripwire for that.
    """
    importers = [
        name
        for name in dir(goals)
        if "import" in name and callable(getattr(goals, name))
    ]
    assert importers == ["import_decision_tree"]
    import inspect

    signature = inspect.signature(goals.import_decision_tree)
    assert "draft_id" not in signature.parameters
    assert "proposal" in signature.parameters
