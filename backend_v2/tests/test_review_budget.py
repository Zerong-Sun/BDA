"""Single-act approval limits: declared together, and actually enforced.

The rule was discovered on the decision-tree bootstrap - a reviewer who cannot read the
whole list stops reviewing and starts accepting - and it is not about decision trees. This
suite pins two things:

* every budget in the table is enforced somewhere, so a row cannot be added as decoration;
* the numbers the decision tree already used did not change when the rule moved.

The third thing it pins is the declared exception: `research_generations` import is a
single-act approval with no review budget, on purpose, and the reason is in the module
docstring. A test that silently tolerated it would be indistinguishable from a test that
had not noticed.
"""

from __future__ import annotations

import pytest
from backend_v2.app.core import review
from backend_v2.app.core.problem import DomainError
from backend_v2.app.research.schemas import (
    MAX_DRAFT_BRANCHES,
    MAX_DRAFT_DEPTH,
    MAX_DRAFT_GOALS,
    DecisionTreeProposal,
)


def test_every_declared_budget_is_reachable() -> None:
    """A name nothing enforces is a number nobody is bound by."""
    assert set(review.REVIEW_BUDGETS) == {
        "decision_tree.goals",
        "decision_tree.branches",
        "decision_tree.depth",
        "autopilot.stages",
    }
    for name in review.REVIEW_BUDGETS:
        assert review.budget(name) > 0


def test_an_undeclared_budget_is_a_programming_error() -> None:
    with pytest.raises(RuntimeError):
        review.budget("invented.thing")


def test_the_message_says_why_not_just_what() -> None:
    """"at most 12" on its own reads as arbitrary, and the next person raises it."""
    with pytest.raises(ValueError) as excinfo:
        review.check_review_budget("autopilot.stages", 99, unit="stages")
    assert "starts accepting" in str(excinfo.value)


def test_moving_the_rule_did_not_move_the_decision_tree_numbers() -> None:
    assert (MAX_DRAFT_GOALS, MAX_DRAFT_BRANCHES, MAX_DRAFT_DEPTH) == (12, 12, 3)


def test_a_goal_tree_nobody_could_read_is_refused() -> None:
    goals = [{"title": f"goal {n}", "detail": "", "children": []} for n in range(13)]
    with pytest.raises(ValueError) as excinfo:
        DecisionTreeProposal.model_validate({"goals": goals, "branches": []})
    assert "goals" in str(excinfo.value)


def test_a_branch_list_nobody_could_read_is_refused() -> None:
    branches = [
        {"title": f"branch {n}", "lane": "dry", "goal_title": "only"} for n in range(13)
    ]
    with pytest.raises(ValueError) as excinfo:
        DecisionTreeProposal.model_validate(
            {"goals": [{"title": "only", "detail": "", "children": []}], "branches": branches}
        )
    assert "open branches" in str(excinfo.value)


def test_an_autopilot_spec_with_too_many_stages_cannot_become_a_draft() -> None:
    """Rejected before it is something to confirm, not only at the confirm click."""
    from backend_v2.app.autopilot.service import _check_stage_budget

    with pytest.raises(DomainError) as excinfo:
        _check_stage_budget({"stages": [f"stage-{n}" for n in range(13)]})
    assert excinfo.value.error_code == "autopilot_stage_budget_exceeded"
    assert excinfo.value.status_code == 422


def test_the_default_stage_list_is_within_budget() -> None:
    from backend_v2.app.autopilot.service import DEFAULT_STAGE_KEYS, _check_stage_budget

    _check_stage_budget({})
    assert len(DEFAULT_STAGE_KEYS) <= review.budget("autopilot.stages")


def test_the_research_generation_exception_is_still_the_shape_it_was_excused_for() -> None:
    """The exception rests on checksum-pinning and validation, not on the count.

    If either of those defences disappeared, the exception recorded in
    `core/review.py` would no longer hold and this test should start failing.
    """
    from backend_v2.app.research.generation import import_research_generation
    from backend_v2.app.research.schemas import CopilotResearchResult

    names = set(import_research_generation.__code__.co_names)
    assert "checksum" in names, "import no longer pins the previewed draft"
    assert "validation" in names, "import no longer requires validation to have passed"
    # And the batch really is large - the quantity question the exception acknowledges has
    # not quietly gone away by someone shrinking the cap instead.
    nodes = CopilotResearchResult.model_fields["nodes"]
    assert any(getattr(rule, "max_length", 0) >= 100 for rule in nodes.metadata), nodes.metadata
