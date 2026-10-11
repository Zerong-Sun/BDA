"""Declared, reproducible validation with train-only preprocessing and sequence purging.

The caller chooses algorithm and split before evaluation. These small baselines do
not establish prospective benefit or calibrated probabilities.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from statistics import fmean

from . import engine
from .calibration import GroupSplitConformal
from .features import COMPOSITION_VERSION, validate_rows
from .predictors import predictor


def aggregate(rows: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["sequence_sha256"]].append(row)
    points = []
    for key, members in sorted(groups.items()):
        repeats: dict[tuple[str, str], list[float]] = defaultdict(list)
        for row in members:
            repeats[(row["batch_key"], row["replicate_key"])].append(row["value"])
        points.append(
            {
                "sequence_sha256": key,
                "features": members[0]["features"],
                "value": fmean(fmean(v) for v in repeats.values()),
            }
        )
    return points


def _fit(points: list[dict], algorithm: str) -> dict:
    return predictor(algorithm).fit(points)


def predict(parameters: dict, vector: list[float]) -> tuple[float, float]:
    return predictor(parameters.get("predictor", "knn")).predict(parameters, vector)


def _folds(rows: list[dict], strategy: str) -> list[tuple[str, list[dict], list[dict]]]:
    if strategy == "time":
        # All occurrences of a sequence must lie entirely before the cutoff for
        # training. A sequence tested later is purged, including earlier repeats.
        if any(not r.get("observed_at") for r in rows):
            raise ValueError("Time validation requires a timezone-aware observed_at for every included result")
        times = [datetime.fromisoformat(r["observed_at"]) for r in rows]
        if any(time.utcoffset() is None for time in times):
            raise ValueError("Time validation requires timezone-aware observation times")
        times = sorted(set(times))
        if len(times) < 5:
            raise ValueError("Time validation requires at least five distinct observation times")
        cutoff = times[max(1, math.floor(len(times) * 0.8))]
        test = [r for r in rows if datetime.fromisoformat(r["observed_at"]) >= cutoff]
        keys = {r["sequence_sha256"] for r in test}
        train = [
            r for r in rows if datetime.fromisoformat(r["observed_at"]) < cutoff and r["sequence_sha256"] not in keys
        ]
        return [(cutoff.isoformat(), train, test)]
    column = {"sequence": "sequence_sha256", "family": "family_key", "batch": "batch_key"}[strategy]
    if any(not r.get(column) for r in rows):
        raise ValueError(f"Every included result needs {column} for this validation strategy")
    # A supplied family label is a scientific assertion, never inferred from a name.
    if strategy == "family":
        labels: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            labels[row["sequence_sha256"]].add(row[column])
        if any(len(values) != 1 for values in labels.values()):
            raise ValueError("Identical sequences have conflicting family labels")
    groups = sorted({r[column] for r in rows})
    if len(groups) < (4 if strategy == "sequence" else 3):
        raise ValueError("Validation requires at least four sequence groups or three family/batch groups")
    folds = []
    for group in groups:
        test = [r for r in rows if r[column] == group]
        keys = {r["sequence_sha256"] for r in test}
        train = [r for r in rows if r[column] != group and r["sequence_sha256"] not in keys]
        folds.append((group, train, test))
    return folds


def train(rows: list[dict], algorithm: str, strategy: str, calibrate: bool = False) -> tuple[dict, dict]:
    feature_version = validate_rows(rows)
    predictor(algorithm)
    if strategy not in {"sequence", "family", "batch", "time"}:
        raise ValueError("Unsupported validation strategy")
    original_rows = list(rows)
    observed_sequences = sorted({r["sequence_sha256"] for r in rows})
    calibration_rows: list[dict] = []
    calibration_groups: list[str] = []
    column = "family_key" if strategy == "family" else "sequence_sha256"
    if calibrate:
        if strategy not in {"sequence", "family"}:
            raise ValueError(
                "Conformal intervals require sequence/family groups; temporal or batch extrapolation is not exchangeable by default"
            )
        # Validate the entire grouping before splitting, including any conflicting
        # labels that would otherwise hide across training and calibration.
        _folds(rows, strategy)
        groups = sorted({r[column] for r in rows}, key=lambda value: engine.digest(["calibration-v1", value]))
        if len(groups) < 20:
            raise ValueError("Interval calibration requires at least 20 independent sequence/family groups")
        calibration_groups = groups[: max(9, math.ceil(len(groups) / 4))]
        calibration_rows = [r for r in rows if r[column] in calibration_groups]
        held_sequences = {r["sequence_sha256"] for r in calibration_rows}
        rows = [r for r in rows if r[column] not in calibration_groups and r["sequence_sha256"] not in held_sequences]
    folds, errors, baseline_errors, distances = [], [], [], []
    for group, training, held_out in _folds(rows, strategy):
        train_points, test_points = aggregate(training), aggregate(held_out)
        if len(train_points) < 3 or not test_points:
            raise ValueError("Every validation fold needs at least three training sequences after leakage purging")
        parameters = _fit(train_points, algorithm)
        predictions = []
        for row in test_points:
            value, nearest = predict(parameters, row["features"])
            error = value - row["value"]
            errors.append(error)
            baseline_errors.append(fmean(p["value"] for p in train_points) - row["value"])
            distances.append(nearest)
            predictions.append(
                {"sequence_sha256": row["sequence_sha256"], "observed": row["value"], "predicted": value}
            )
        folds.append(
            {
                "held_out_group": group,
                "train_sequences": [r["sequence_sha256"] for r in train_points],
                "test_predictions": predictions,
                "sequence_overlap": 0,
                "family_overlap": sorted({r["family_key"] for r in training if r.get("family_key")} &
                                         {r["family_key"] for r in held_out if r.get("family_key")}),
                "batch_overlap": sorted({r["batch_key"] for r in training} & {r["batch_key"] for r in held_out}),
                "train_rows": len(training),
                "test_rows": len(held_out),
            }
        )
    if len(errors) < 2:
        raise ValueError("At least two held-out sequence predictions are required")
    rmse = math.sqrt(fmean(e * e for e in errors))
    baseline_rmse = math.sqrt(fmean(e * e for e in baseline_errors))
    parameters = {
        **_fit(aggregate(rows), algorithm),
        "domain_radius": max(distances),
        "error_scale": rmse,
        "feature_version": feature_version,
        "observed_sequences": observed_sequences,
    }
    evaluation: dict = {
        "split": f"purged-{strategy}-v2",
        "algorithm_declared_before_validation": algorithm,
        "feature_version": feature_version,
        "feature_dimensions": len(rows[0]["features"]),
        "predictor_version": parameters["predictor_version"],
        "data_quality": {
            "total_included_rows": len(original_rows),
            "technical_repeat_rows": len(original_rows) - len({
                (r["sequence_sha256"], r["batch_key"], r["replicate_key"]) for r in original_rows
            }),
            "family_labels_complete": all(r.get("family_key") for r in original_rows),
            "family_overlap_fold_count": sum(bool(f["family_overlap"]) for f in folds),
            "batch_overlap_fold_count": sum(bool(f["batch_overlap"]) for f in folds),
            "identical_sequence_leakage": False,
            "homology_exclusion_verified": False,
        },
        "groups": len(parameters["points"]),
        "rows": len(rows),
        "folds": folds,
        "rmse": rmse,
        "mae": fmean(abs(e) for e in errors),
        "mean_baseline_rmse": baseline_rmse,
        "eligible_for_promotion": baseline_rmse > 0 and rmse < baseline_rmse,
        "evidence_level": "retrospective_baseline_only",
        "limitations": [
            ("Composition features ignore residue order and structure" if feature_version == COMPOSITION_VERSION else
             "Local pair and terminal features do not model long-range interactions, homology or structure"),
            "Uncertainty is a distance/error heuristic, not a calibrated interval",
            "Family labels and timestamps are supplied by the experiment owner",
            "Identical-sequence purging does not establish homology-independent validation",
            "Repeated model selection on these folds needs a separate external test set",
            "No prospective experimental benefit has been established",
        ],
    }
    if calibrate:
        # Calibration labels never participate in fitting, preprocessing or the
        # retrospective model-versus-mean gate. Max residual per family gives a
        # group score, avoiding a large family counting as many independent draws.
        scores = []
        for group in calibration_groups:
            points = aggregate([r for r in calibration_rows if r[column] == group])
            scores.append(max(abs(predict(parameters, p["features"])[0] - p["value"]) for p in points))
        calibration = GroupSplitConformal().fit(scores)
        parameters["interval_half_width"] = calibration["half_width"]
        parameters["nominal_coverage"] = calibration["nominal_coverage"]
        evaluation["calibration"] = {
            **calibration,
            "calibration_groups": calibration_groups,
            "calibration_sequences": sorted({r["sequence_sha256"] for r in calibration_rows}),
            "assumptions": "Coverage requires exchangeable independent groups and a fixed predictor; distribution shift and adaptive selection can invalidate it",
        }
        evaluation["limitations"] = [item for item in evaluation["limitations"] if "heuristic" not in item]
        evaluation["limitations"].append(
            "Nominal intervals are conditional on exchangeability; no interval is provided outside the fitted domain"
        )
    return parameters, evaluation
