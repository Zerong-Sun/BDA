"""Deterministic budgeted batch selection with auditable acquisition components."""

from __future__ import annotations

import math
from typing import Protocol

from .predictors import distance


class Recommender(Protocol):
    version: str

    def select(
        self,
        scored: list[dict],
        *,
        budget: int,
        batch_size: int,
        exploration_fraction: float,
        direction: str,
        domain_radius: float,
        error_scale: float,
        observed_reference: float,
    ) -> list[dict]: ...


class CostDiversityRecommender:
    version = "cost-diversity-v2"

    def select(
        self,
        scored: list[dict],
        *,
        budget: int,
        batch_size: int,
        exploration_fraction: float,
        direction: str,
        domain_radius: float,
        error_scale: float,
        observed_reference: float,
    ) -> list[dict]:
        selected: list[dict] = []
        remaining = budget
        sign = 1 if direction == "maximize" else -1
        minimum_cost = min((r["cost_cents"] for r in scored), default=1)
        radius = max(domain_radius, 1e-12)
        error = max(error_scale, abs(observed_reference) * 1e-12, 1e-12)

        def components(row: dict, strategy: str) -> dict:
            novelty = min(row["distance"] / radius, 1.0)
            diversity = min((distance(row["features"], r["features"]) / radius for r in selected), default=1.0)
            diversity = min(diversity, 1.0)
            gain = sign * (row["prediction"] - observed_reference) / error
            quality = 0.5 + 0.5 * gain / (1 + abs(gain))
            penalty = math.sqrt(row["cost_cents"] / minimum_cost)
            utility = (
                (0.5 * novelty + 0.5 * diversity)
                if strategy == "exploration"
                else (0.65 * quality + 0.2 * novelty + 0.15 * diversity)
            )
            return {
                "normalized_predicted_value": quality,
                "training_novelty": novelty,
                "batch_diversity": diversity,
                "relative_cost_penalty": penalty,
                "acquisition_score": utility / penalty,
            }

        for strategy, quota in (
            ("retest", batch_size),
            ("exploration", math.floor(batch_size * exploration_fraction)),
            ("exploitation", batch_size),
        ):
            used = 0
            while used < quota and len(selected) < batch_size:
                chosen = {r["candidate_id"] for r in selected}
                feasible = [
                    r
                    for r in scored
                    if r["candidate_id"] not in chosen
                    and r["cost_cents"] <= remaining
                    and (strategy != "retest" or r["retest"])
                ]
                if not feasible:
                    break
                ranked = [{**r, "acquisition": components(r, strategy)} for r in feasible]
                if strategy == "retest":
                    row = min(ranked, key=lambda r: r["candidate_id"])
                else:
                    row = min(
                        ranked,
                        key=lambda r: (
                            strategy == "exploitation"
                            and (r["out_of_domain"] or r.get("secondary_out_of_domain", False)),
                            strategy == "exploitation" and not r.get("pareto_front", True),
                            -r["acquisition"]["acquisition_score"],
                            r["candidate_id"],
                        ),
                    )
                selected.append({**row, "selection_reason": strategy})
                remaining -= row["cost_cents"]
                used += 1
        return selected


class LegacyRecommender:
    version = "bounded-explore-exploit-v1"

    def select(
        self,
        scored: list[dict],
        *,
        budget: int,
        batch_size: int,
        exploration_fraction: float,
        direction: str,
        domain_radius: float,
        error_scale: float,
        observed_reference: float,
    ) -> list[dict]:
        sign = -1 if direction == "maximize" else 1
        exploitation = sorted(
            scored,
            key=lambda r: (
                r["out_of_domain"] or r.get("secondary_out_of_domain", False),
                not r.get("pareto_front", True),
                sign * r["prediction"],
                r["candidate_id"],
            ),
        )
        selected: list[dict] = []
        remaining = budget
        for strategy, ranked, quota in (
            ("retest", [r for r in scored if r["retest"]], batch_size),
            (
                "exploration",
                sorted(scored, key=lambda r: (-r["distance"], r["candidate_id"])),
                math.floor(batch_size * exploration_fraction),
            ),
            ("exploitation", exploitation, batch_size),
        ):
            used = 0
            for row in ranked:
                if len(selected) >= batch_size or used >= quota:
                    break
                if any(r["candidate_id"] == row["candidate_id"] for r in selected) or row["cost_cents"] > remaining:
                    continue
                selected.append({**row, "selection_reason": strategy})
                remaining -= row["cost_cents"]
                used += 1
        return selected


RECOMMENDERS: dict[str, Recommender] = {r.version: r for r in (CostDiversityRecommender(), LegacyRecommender())}
