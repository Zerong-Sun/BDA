"""Independent residual calibration; coverage is not a success probability."""

from __future__ import annotations

import math
from typing import Protocol


class Calibrator(Protocol):
    version: str

    def fit(self, group_scores: list[float]) -> dict: ...


class GroupSplitConformal:
    version = "split-conformal-group-max-v1"

    def fit(self, group_scores: list[float]) -> dict:
        coverage = 0.9
        rank = math.ceil((len(group_scores) + 1) * coverage)
        if rank > len(group_scores) or any(not math.isfinite(s) or s < 0 for s in group_scores):
            raise ValueError("Calibration needs at least nine finite independent group residuals")
        return {
            "method": self.version,
            "nominal_coverage": coverage,
            "group_absolute_errors": group_scores,
            "quantile_rank": rank,
            "half_width": sorted(group_scores)[rank - 1],
        }
