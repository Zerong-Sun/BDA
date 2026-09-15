"""Applying declared thresholds, and the third outcome that makes it honest.

The route catalogue has carried `{"pae_interaction": "< 15", ...}` since it was
written, read by nobody. Automating that comparison is easy; automating it
*without* telling people to throw away work is the part these tests are about.

The central case is `missing`. A design with no Rosetta number has not failed a
Rosetta gate - nothing has run Rosetta on it - and a triage that reports those
alike is at its most confidently wrong exactly when a pipeline stage was
skipped, which is when somebody most needs to notice.
"""

from __future__ import annotations

import pytest
from backend_v2.app.candidates import triage

TIER_A = {
    "pae_interaction": "< 15",
    "binder_plddt": "> 70",
    "rosetta_ddg_reu": "< -20",
}
TIER_B = {
    "pae_interaction": "< 7",
    "binder_plddt": "> 85",
    "rosetta_ddg_reu": "< -40",
}
TIERS = {"tier_b": TIER_B, "tier_a": TIER_A}


def _metric(key: str, value: float, method: str = "alphafold3", assessor: str = "independent_model") -> dict:
    return {"key": key, "value": value, "method": method, "assessor": assessor}


# --- reading a threshold --------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value", "symbol"),
    [("< 15", 15.0, "<"), (">70", 70.0, ">"), ("<= 3.0", 3.0, "<="), (">= -40", -40.0, ">=")],
)
def test_a_threshold_is_read_as_a_comparison(text: str, value: float, symbol: str) -> None:
    _compare, limit, read_symbol = triage.parse_threshold(text)

    assert (limit, read_symbol) == (value, symbol)


@pytest.mark.parametrize("text", ["", "15", "about 15", "< fifteen", "<", "≤ 15"])
def test_a_threshold_nobody_can_read_is_refused_rather_than_skipped(text: str) -> None:
    """Skipping it would report a tier as met with one condition unchecked."""
    with pytest.raises(triage.ThresholdError):
        triage.parse_threshold(text)


# --- the three outcomes -----------------------------------------------------------


def test_a_recorded_metric_that_satisfies_its_threshold_passes() -> None:
    criteria = triage.evaluate([_metric("pae_interaction", 9.0)], {"pae_interaction": "< 15"})

    assert criteria[0].outcome == "pass"
    assert criteria[0].value == 9.0


def test_a_recorded_metric_that_does_not_says_why() -> None:
    criteria = triage.evaluate([_metric("pae_interaction", 22.0)], {"pae_interaction": "< 15"})

    assert criteria[0].outcome == "fail"
    assert criteria[0].note == "22 is not < 15"


def test_a_metric_nobody_recorded_is_missing_and_not_a_failure() -> None:
    criteria = triage.evaluate([], {"rosetta_ddg_reu": "< -20"})

    assert criteria[0].outcome == "missing"
    assert criteria[0].value is None
    assert "Not a failure" in criteria[0].note


def test_the_catalogues_name_is_mapped_to_the_stored_metric_key() -> None:
    """`binder_plddt` is stored as `plddt`, because keys are normalised across methods."""
    criteria = triage.evaluate([_metric("plddt", 88.0)], {"binder_plddt": "> 70"})

    assert criteria[0].outcome == "pass"
    assert criteria[0].metric_key == "plddt"


def test_the_row_that_decided_it_is_named() -> None:
    """Which method produced the number, and whether it was self-assessment."""
    criteria = triage.evaluate(
        [_metric("plddt", 88.0, method="alphafold2_superfold", assessor="design_model")],
        {"binder_plddt": "> 70"},
    )

    assert criteria[0].method == "alphafold2_superfold"
    assert criteria[0].assessor == "design_model"


# --- several values for one metric --------------------------------------------------


def test_a_passing_seed_is_preferred_when_one_exists() -> None:
    """Five seeds, one good: the charitable reading, with the row named."""
    metrics = [_metric("iptm", value) for value in (0.31, 0.44, 0.86)]

    criteria = triage.evaluate(metrics, {"iptm": "> 0.8"})

    assert criteria[0].outcome == "pass"
    assert criteria[0].value == 0.86


def test_when_none_passes_the_closest_is_reported() -> None:
    """The reader needs the best attempt, not an arbitrary one."""
    metrics = [_metric("pae_interaction", value) for value in (28.0, 19.0, 33.0)]

    criteria = triage.evaluate(metrics, {"pae_interaction": "< 15"})

    assert criteria[0].outcome == "fail"
    assert criteria[0].value == 19.0


# --- tiers ---------------------------------------------------------------------------


def test_the_best_tier_whose_every_criterion_passes_is_reported() -> None:
    metrics = [
        _metric("pae_interaction", 5.0),
        _metric("plddt", 90.0),
        _metric("rosetta_ddg_reu", -45.0),
    ]

    verdict = triage.triage(metrics, TIERS)

    assert verdict.tier == "tier_b"
    assert verdict.failed == 0 and verdict.missing == 0


def test_a_design_that_only_clears_the_lower_bar_gets_the_lower_bar() -> None:
    metrics = [
        _metric("pae_interaction", 12.0),
        _metric("plddt", 75.0),
        _metric("rosetta_ddg_reu", -25.0),
    ]

    assert triage.triage(metrics, TIERS).tier == "tier_a"


def test_a_missing_measurement_blocks_a_tier_without_condemning_the_design() -> None:
    """Every recorded number clears tier A; Rosetta was never run."""
    metrics = [_metric("pae_interaction", 5.0), _metric("plddt", 92.0)]

    verdict = triage.triage(metrics, TIERS)

    assert verdict.tier is None
    assert verdict.missing == 1
    assert verdict.failed == 0
    outcomes = {item.name: item.outcome for item in verdict.criteria}
    assert outcomes["rosetta_ddg_reu"] == "missing"
    assert outcomes["pae_interaction"] == "pass"


def test_a_design_that_reaches_nothing_is_explained_against_the_easiest_tier() -> None:
    """The list a person needs is what to fix, which is the lowest bar's list."""
    metrics = [_metric("pae_interaction", 40.0), _metric("plddt", 40.0), _metric("rosetta_ddg_reu", 5.0)]

    verdict = triage.triage(metrics, TIERS)

    assert verdict.tier is None
    assert verdict.failed == 3
    assert {item.threshold for item in verdict.criteria} == set(TIER_A.values())


def test_no_tiers_declared_is_not_a_verdict() -> None:
    assert triage.triage([_metric("iptm", 0.9)], {}).tier is None


def test_an_unreadable_threshold_stops_the_triage_rather_than_passing_it() -> None:
    with pytest.raises(triage.ThresholdError):
        triage.triage([_metric("iptm", 0.9)], {"tier_a": {"iptm": "high"}})
