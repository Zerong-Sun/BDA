"""Small, bounded baseline, not a foundation model or calibrated success probability.

Pure functions keep training and selection reproducible. Identical sequences are
one validation group. Uncertainty is a distance/error heuristic, not a confidence
interval. No sequence is copied into the learned payload.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from statistics import fmean

ALGORITHM = "composition-knn-v1"
AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def features(sequence: str) -> dict:
    sequence = "".join(sequence.split()).upper()
    if not sequence or len(sequence) > 10_000 or set(sequence) - set(AMINO_ACIDS):
        raise ValueError("A canonical protein sequence of 1–10000 residues is required")
    return {
        "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
        "feature_version": "aa-composition-length-v1",
        "features": [sequence.count(aa) / len(sequence) for aa in AMINO_ACIDS] + [math.log1p(len(sequence)) / 10],
    }


def distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def estimate(points: list[dict], vector: list[float]) -> tuple[float, float]:
    neighbors = sorted((distance(row["features"], vector), row["value"]) for row in points)[:3]
    weights = [1 / (d + 0.01) for d, _ in neighbors]
    return sum(w * pair[1] for w, pair in zip(weights, neighbors, strict=True)) / sum(weights), neighbors[0][0]


def train(rows: list[dict]) -> tuple[dict, dict]:
    # Average technical repeats within a biological replicate before averaging
    # replicates, then sequences. More technical repeats must not increase weight.
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["sequence_sha256"]].append(row)
    if len(groups) < 4:
        raise ValueError("At least four independent sequence groups are required")
    points = []
    for key, members in sorted(groups.items()):
        replicates: dict[tuple[str, str], list[float]] = defaultdict(list)
        for row in members:
            replicates[(row["batch_key"], row["replicate_key"])].append(row["value"])
        points.append(
            {
                "sequence_sha256": key,
                "features": members[0]["features"],
                "value": fmean(fmean(values) for values in replicates.values()),
            }
        )
    predictions, baselines, distances = [], [], []
    for row in points:
        remaining = [p for p in points if p["sequence_sha256"] != row["sequence_sha256"]]
        prediction, nearest = estimate(remaining, row["features"])
        predictions.append((prediction - row["value"]) ** 2)
        baselines.append((fmean(p["value"] for p in remaining) - row["value"]) ** 2)
        distances.append(nearest)
    rmse, baseline_rmse = math.sqrt(fmean(predictions)), math.sqrt(fmean(baselines))
    parameters = {
        "points": points,
        "domain_radius": max(distances),
        "error_scale": rmse,
        "feature_version": "aa-composition-length-v1",
    }
    evaluation = {
        "split": "leave-one-sequence-group-out",
        "groups": len(points),
        "rows": len(rows),
        "rmse": rmse,
        "mean_baseline_rmse": baseline_rmse,
        "eligible_for_promotion": baseline_rmse > 0 and rmse < baseline_rmse,
        "evidence_level": "retrospective_baseline_only",
        "limitations": [
            "Composition features ignore residue order and structure",
            "Uncertainty is a heuristic, not a calibrated interval",
            "Sequence identity grouping does not remove family or batch confounding",
            "No prospective experimental benefit has been established",
        ],
    }
    return parameters, evaluation


def propose(
    parameters: dict, pool: list[dict], *, direction: str, budget: int, batch_size: int, exploration_fraction: float
) -> dict:
    measured = {p["sequence_sha256"] for p in parameters["points"]}
    scored, excluded = [], []
    seen = set(measured)
    for row in sorted(pool, key=lambda x: x["candidate_id"]):
        key = row["sequence_sha256"]
        if key in seen:
            excluded.append({"candidate_id": row["candidate_id"], "reason": "measured_or_duplicate_sequence"})
            continue
        seen.add(key)
        value, nearest = estimate(parameters["points"], row["features"])
        # An out-of-domain candidate remains an exploration option, explicitly
        # marked so a speculative high prediction cannot masquerade as evidence.
        scored.append(
            {
                **row,
                "prediction": value,
                "distance": nearest,
                "uncertainty_heuristic": parameters["error_scale"] * (1 + nearest),
                "out_of_domain": nearest > parameters["domain_radius"],
            }
        )
    sign = -1 if direction == "maximize" else 1
    exploitation = sorted(scored, key=lambda x: (x["out_of_domain"], sign * x["prediction"], x["candidate_id"]))
    exploration = sorted(scored, key=lambda x: (-x["distance"], x["candidate_id"]))
    explore_slots = math.floor(batch_size * exploration_fraction)
    selected: list[dict] = []
    remaining_budget = budget
    for strategy, ranked, quota in (
        ("exploration", exploration, explore_slots),
        ("exploitation", exploitation, batch_size),
    ):
        used = 0
        for row in ranked:
            if len(selected) >= batch_size or used >= quota:
                break
            if any(r["candidate_id"] == row["candidate_id"] for r in selected) or row["cost_cents"] > remaining_budget:
                continue
            selected.append({**row, "selection_reason": strategy})
            remaining_budget -= row["cost_cents"]
            used += 1
    chosen = {r["candidate_id"] for r in selected}
    excluded.extend(
        {"candidate_id": r["candidate_id"], "reason": "budget_or_batch_priority"}
        for r in scored
        if r["candidate_id"] not in chosen
    )
    return {
        "selected": selected,
        "excluded": excluded,
        "considered": scored,
        "estimated_cost_cents": budget - remaining_budget,
        "remaining_batch_budget_cents": remaining_budget,
        "policy": "bounded-explore-exploit-v1",
        "exploration_fraction": exploration_fraction,
        "action": "review_batch" if selected else "stop_no_feasible_candidate",
        "execution_authorized": False,
        "budget_reserved": False,
        "limitations": [
            "Greedy batch heuristic; not a globally optimal budget allocation",
            "Single-assay baseline; no implied multi-property or functional success",
        ],
    }
