"""Priced budget reservations with synthetic rates, never provider billing."""
from __future__ import annotations

import pytest
from backend_v2.app.copilot import agent_runs
from backend_v2.app.copilot.task_budget import reserve_model_call
from backend_v2.app.core.problem import DomainError
from backend_v2.tests.test_copilot_agent_loop import _project, _provider, _run
from backend_v2.tests.test_copilot_agent_loop import session as session  # noqa: F401


def priced_provider(session):
    configured = _provider(session)
    configured.config = {"bda_pricing": {"input_usd_per_million": 0, "output_usd_per_million": 1}, "max_tokens": 1}
    return configured


def test_parent_and_siblings_share_the_same_priced_ceiling(session):
    project, user = _project(session)
    root = _run(session, project, user, max_cost_usd_cents=2)
    children = [_run(session, project, user, parent_run_id=root.id) for _ in range(2)]
    configured = priced_provider(session)
    reserve_model_call(session, root, configured, [])
    reserve_model_call(session, children[0], configured, [])
    with pytest.raises(DomainError) as error:
        reserve_model_call(session, children[1], configured, [])
    assert error.value.error_code == "copilot_budget_insufficient"
    assert [root.cost_usd_cents, *(child.cost_usd_cents for child in children)] == [1, 1, 0]
    assert agent_runs.tree_cost_usd_cents(session, root) == 2
    assert root.task_contract["cost_mode"] == "conservative_estimate"


@pytest.mark.parametrize("rate", [-1, "NaN", "Infinity", "not-a-rate"])
def test_invalid_prices_fail_before_spending_a_bounded_budget(session, rate):
    project, user = _project(session)
    run = _run(session, project, user, max_cost_usd_cents=10)
    configured = priced_provider(session)
    configured.config = {"bda_pricing": {"input_usd_per_million": rate, "output_usd_per_million": 1}}
    with pytest.raises(DomainError) as error:
        reserve_model_call(session, run, configured, [])
    assert error.value.error_code == "copilot_budget_pricing_required"
    assert run.cost_usd_cents == 0
    assert run.task_contract["cost_mode"] == "unavailable"


@pytest.mark.parametrize("limit", [0, -1, "4096"])
def test_invalid_output_limit_fails_without_reserving_cost(session, limit):
    project, user = _project(session)
    run = _run(session, project, user, max_cost_usd_cents=10)
    configured = priced_provider(session)
    configured.config = {**configured.config, "max_tokens": limit}
    with pytest.raises(DomainError) as error:
        reserve_model_call(session, run, configured, [])
    assert error.value.error_code == "copilot_output_limit_invalid"
    assert run.cost_usd_cents == 0


def test_unpriced_unbounded_call_is_explicitly_unavailable_not_priced_free(session):
    project, user = _project(session)
    run = _run(session, project, user)
    reserve_model_call(session, run, _provider(session), [])
    assert run.cost_usd_cents == 0
    assert run.task_contract["cost_mode"] == "unavailable"
