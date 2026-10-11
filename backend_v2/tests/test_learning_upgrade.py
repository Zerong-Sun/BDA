"""Order-aware learning, honest validation and budgeted selection on synthetic data."""

from __future__ import annotations

import copy

import numpy as np
import pytest
from backend_v2.app.learning import engine, validation
from backend_v2.app.learning.calibration import GroupSplitConformal
from backend_v2.app.learning.features import COMPOSITION_VERSION, SEQUENCE_VERSION, validate_rows
from backend_v2.app.learning.predictors import RidgePredictor
from backend_v2.app.learning.recommenders import CostDiversityRecommender
from backend_v2.tests.test_learning import _post, _trained
from backend_v2.tests.test_learning import client as client  # noqa: F401


def _ordered_rows():
    return [
        {
            **engine.features("A" * n + "C" * (100 - n), SEQUENCE_VERSION),
            "value": float(n),
            "batch_key": f"batch-{i // 2}",
            "replicate_key": "bio1",
            "family_key": f"family-{i // 2}",
            "observed_at": f"2026-01-{i + 1:02d}T00:00:00+00:00",
        }
        for i, n in enumerate(range(10, 90, 10))
    ]


def test_order_features_distinguish_rearrangements_and_keep_legacy_vectors():
    left, right = "AACC", "ACAC"
    assert engine.features(left)["features"] == engine.features(right)["features"]
    a, b = engine.features(left, SEQUENCE_VERSION), engine.features(right, SEQUENCE_VERSION)
    assert len(a["features"]) == 461 and a["features"] != b["features"]
    assert sum(a["features"][21:421]) == pytest.approx(1)
    assert a["features"][:21] == engine.features(left)["features"]
    assert a == engine.features(" a a c c\n", SEQUENCE_VERSION)
    assert len(engine.features("A", SEQUENCE_VERSION)["features"]) == 461
    with pytest.raises(ValueError, match="Unsupported"):
        engine.features(left, "unreviewed-checkpoint")


@pytest.mark.parametrize("corruption", ["mixed", "nonfinite", "dimension", "duplicate_conflict"])
def test_frozen_feature_integrity_blocks_mixed_and_corrupt_inputs(corruption):
    rows = _ordered_rows()
    if corruption == "mixed":
        rows[0]["feature_version"] = COMPOSITION_VERSION
    elif corruption == "nonfinite":
        rows[0]["features"][0] = float("nan")
    elif corruption == "dimension":
        rows[0]["features"].pop()
    else:
        changed = copy.deepcopy(rows[0])
        changed["features"][0] += 0.1
        rows.append(changed)
    with pytest.raises(ValueError):
        validate_rows(rows)


def test_dual_ridge_matches_reference_primal_and_uses_train_only_scaling():
    points = validation.aggregate(_ordered_rows())
    result = RidgePredictor().fit(points)
    x = np.asarray([p["features"] for p in points])
    y = np.asarray([p["value"] for p in points])
    z = (x - result["center"]) / result["scale"]
    primal = np.linalg.solve(z.T @ z + np.eye(x.shape[1]), z.T @ (y - y.mean()))
    assert result["weights"] == pytest.approx(primal, abs=1e-9)
    rows = _ordered_rows()
    _, first = validation.train(rows, "ridge", "sequence")
    changed = [{**r, "value": r["value"] + 10000 if i == 0 else r["value"]} for i, r in enumerate(rows)]
    _, second = validation.train(changed, "ridge", "sequence")
    original_fold = next(f for f in first["folds"] if f["held_out_group"] == rows[0]["sequence_sha256"])
    changed_fold = next(f for f in second["folds"] if f["held_out_group"] == rows[0]["sequence_sha256"])
    assert original_fold["test_predictions"][0]["predicted"] == changed_fold["test_predictions"][0]["predicted"]


@pytest.mark.parametrize("split", ["sequence", "family", "batch", "time"])
def test_order_aware_splits_report_leakage_boundaries_and_reproduce(split):
    rows = _ordered_rows()
    parameters, evaluation = validation.train(rows, "ridge", split)
    assert parameters["feature_version"] == SEQUENCE_VERSION
    assert evaluation["feature_dimensions"] == 461
    assert evaluation["data_quality"]["homology_exclusion_verified"] is False
    for fold in evaluation["folds"]:
        assert set(fold["train_sequences"]).isdisjoint(p["sequence_sha256"] for p in fold["test_predictions"])
        if split == "family":
            assert not fold["family_overlap"]
        if split == "batch":
            assert not fold["batch_overlap"]
    assert validation.train(list(reversed(rows)), "ridge", split) == (parameters, evaluation)


def test_time_validation_rejects_mixed_naive_timestamps_and_unknown_predictor():
    rows = _ordered_rows()
    rows[0]["observed_at"] = "2026-01-01T00:00:00"
    with pytest.raises(ValueError, match="timezone"):
        validation.train(rows, "knn", "time")
    with pytest.raises(ValueError, match="Unsupported predictor"):
        validation.train(_ordered_rows(), "unavailable-model", "sequence")


def test_calibration_requires_enough_groups_and_uses_conservative_order_statistic():
    with pytest.raises(ValueError, match="nine"):
        GroupSplitConformal().fit([1] * 8)
    assert GroupSplitConformal().fit(list(range(9)))["half_width"] == 8


def _scored(key, vector, cost=10):
    return {
        "candidate_id": key,
        "features": vector,
        "cost_cents": cost,
        "prediction": 3.0,
        "distance": 1.0,
        "out_of_domain": False,
        "retest": False,
    }


def test_batch_diversity_changes_second_selection_and_cost_is_scored():
    recommender = CostDiversityRecommender()
    options = {
        "budget": 100,
        "batch_size": 2,
        "exploration_fraction": 1.0,
        "direction": "maximize",
        "domain_radius": 1.0,
        "error_scale": 1.0,
        "observed_reference": 2.0,
    }
    selected = recommender.select(
        [
            _scored("a", [0]),
            _scored("b-close", [0.001]),
            _scored("c-diverse", [1]),
        ],
        **options,
    )
    assert [r["candidate_id"] for r in selected] == ["a", "c-diverse"]
    assert selected[1]["acquisition"]["batch_diversity"] == 1
    selected = recommender.select([_scored("a-expensive", [0], 100), _scored("b-cheap", [1], 10)], **options)
    assert selected[0]["candidate_id"] == "b-cheap"
    assert sum(r["cost_cents"] for r in selected) <= 100


def test_http_new_and_old_representations_coexist_and_secondary_uses_its_own_features(client):
    _, study, results, dataset, model = _trained(client)
    assert dataset["manifest"]["feature_version"] == SEQUENCE_VERSION
    assert model["algorithm"] == "sequence-order-knn-sequence-v3"
    legacy = _post(
        client,
        "datasets",
        {"study_id": study["id"], "result_ids": [r["id"] for r in results], "feature_version": COMPOSITION_VERSION},
    )
    assert legacy["digest"] != dataset["digest"]
    old_model = _post(client, "models", {"dataset_id": legacy["id"]})
    assert old_model["algorithm"] == "composition-knn-sequence-v2"
    _, other_study, other_results, _, _ = _trained(client)
    secondary_dataset = _post(
        client,
        "datasets",
        {
            "study_id": other_study["id"],
            "result_ids": [r["id"] for r in other_results],
            "feature_version": COMPOSITION_VERSION,
        },
    )
    secondary = _post(client, "models", {"dataset_id": secondary_dataset["id"]})
    decision = _post(
        client,
        "decisions",
        {
            "study_id": study["id"],
            "model_id": model["id"],
            "secondary_model_id": secondary["id"],
            "candidates": [{"candidate_id": str(client[1]["candidates"][6]), "cost_cents": 50}],
        },
    )
    proposal = decision["proposal"]
    assert proposal["policy"] == "cost-diversity-v2" and proposal["selected"]
    assert len(proposal["selected"][0]["secondary_features"]) == 21
    assert len(proposal["selected"][0]["features"]) == 461
    assert proposal["prediction_evidence"] == "model_prediction_not_experimental_observation"
    assert proposal["selected"][0]["acquisition"]["relative_cost_penalty"] == 1
    assert not proposal["execution_authorized"] and not proposal["budget_reserved"]
    old_decision = _post(
        client,
        "decisions",
        {
            "study_id": study["id"],
            "model_id": old_model["id"],
            "selection_policy": "bounded-explore-exploit-v1",
            "candidates": [{"candidate_id": str(client[1]["candidates"][6]), "cost_cents": 50}],
        },
    )
    assert old_decision["proposal"]["policy"] == "bounded-explore-exploit-v1"
