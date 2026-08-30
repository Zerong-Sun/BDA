"""Moving legacy candidate results out of JSON blobs must not distort them.

The blob mixes three methods' numbers with nothing saying which produced which, so the
backfill's whole value is that it attributes them correctly and refuses to invent what
was lost.
"""

from __future__ import annotations

from backend_v2.scripts.backfill_candidate_metrics import (
    ALPHAFOLD,
    PROTEINMPNN,
    ROSETTA,
    plan_for,
)

# A representative legacy score blob.
SCORES = {
    "total_score": 166.7,
    "score": 166.7,
    "rosetta_score": 166.7,
    "fa_atr": -527.46,
    "fa_rep": 240.605,
    "rosetta_score_per_residue": 1.7185567010309277,
    "proteinmpnn_score": 0.8149,
    "plddt": 70.59221649169922,
    "ptm": 0.5434974431991577,
    "mean_pae": 9.360278129577637,
    "mean_pae_intra_chain": 9.289594650268555,
    "alphafold_tol": 0.2615728974342346,
    "alphafold_elapsed_seconds": 112.1167631149292,
    "alphafold_recycles": 5,
}


def _by_key(scores: dict) -> dict:
    planned, _ = plan_for(scores)
    return {spec.metric_key: (spec, value, context) for spec, value, context in planned}


def test_every_number_is_attributed_to_the_method_that_produced_it() -> None:
    planned = _by_key(SCORES)
    assert planned["fa_atr"][0].method == ROSETTA
    assert planned["total_score"][0].method == ROSETTA
    assert planned["mpnn_score"][0].method == PROTEINMPNN
    assert planned["plddt"][0].method == ALPHAFOLD
    assert planned["pae"][0].method == ALPHAFOLD
    # Rosetta energies are in its own units and are not comparable across score
    # functions, which is why the score function is named in the method.
    assert planned["fa_atr"][0].unit == "REU"
    assert planned["pae"][0].unit == "angstrom"


def test_the_two_restatements_of_total_score_are_not_counted_three_times() -> None:
    """The scorefile prints total_score, score and rosetta_score for one quantity."""
    planned = _by_key(SCORES)
    assert "score" not in planned and "rosetta_score" not in planned
    assert planned["total_score"][1] == 166.7


def test_run_detail_becomes_context_rather_than_a_metric() -> None:
    planned = _by_key(SCORES)
    assert "recycles" not in planned and "tol" not in planned
    # ...and it qualifies the metrics of the run it came from.
    assert planned["plddt"][2]["recycles"] == 5
    assert planned["plddt"][2]["tol"] == SCORES["alphafold_tol"]
    # Rosetta's numbers are not annotated with AlphaFold2's run detail.
    assert "recycles" not in planned["fa_atr"][2]


def test_provenance_is_marked_as_backfilled_rather_than_invented() -> None:
    """The blob never recorded which run produced a number; a guess would outlive us."""
    planned = _by_key(SCORES)
    assert planned["plddt"][2]["backfilled_from"] == "candidates.scores"


def test_a_structural_comparison_is_recorded_as_derived_not_predicted() -> None:
    planned = _by_key({"alphafold_tmscore_to_input": 0.75, "alphafold_rmsd_to_input": 2.6})
    assert planned["tmscore_to_design"][0].evidence_kind == "derived"
    assert planned["rmsd_to_design"][0].evidence_kind == "derived"


def test_unknown_and_non_numeric_keys_are_reported_not_silently_dropped() -> None:
    planned, unmapped = plan_for({"total_score": 1.0, "some_new_metric": 2.0, "plddt": "n/a"})
    assert [spec.metric_key for spec, _, _ in planned] == ["total_score"]
    assert sorted(unmapped) == ["plddt", "some_new_metric"]


def test_the_backfill_is_a_no_op_for_a_candidate_with_no_scores() -> None:
    """200 RFdiffusion backbones carry no numbers yet."""
    assert plan_for({}) == ([], [])
