"""Small executable predictor adapters, with no optional ML runtime required."""

from __future__ import annotations

import math
from typing import Protocol

import numpy as np


def distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


class Predictor(Protocol):
    version: str

    def fit(self, points: list[dict]) -> dict: ...

    def predict(self, parameters: dict, vector: list[float]) -> tuple[float, float]: ...


class KNearestPredictor:
    version = "distance-weighted-knn-v1"

    def fit(self, points: list[dict]) -> dict:
        return {"points": points, "predictor": "knn", "predictor_version": self.version}

    def predict(self, parameters: dict, vector: list[float]) -> tuple[float, float]:
        neighbors = sorted((distance(row["features"], vector), row["value"]) for row in parameters["points"])[:3]
        weights = [1 / (d + 0.01) for d, _ in neighbors]
        return sum(w * pair[1] for w, pair in zip(weights, neighbors, strict=True)) / sum(weights), neighbors[0][0]


class RidgePredictor:
    version = "train-scaled-ridge-alpha1-v1"

    @np.errstate(over="raise", invalid="raise", divide="raise")
    def fit(self, points: list[dict]) -> dict:
        x = np.asarray([p["features"] for p in points], dtype=float)
        y = np.asarray([p["value"] for p in points], dtype=float)
        center, scale = x.mean(axis=0), x.std(axis=0)
        scale[scale < 1e-12] = 1
        z = (x - center) / scale
        # Equivalent dual solution keeps small-data/high-dimensional folds cheap.
        # Alpha is fixed before validation; preprocessing uses training rows only.
        weights = (
            z.T @ np.linalg.solve(z @ z.T + np.eye(x.shape[0]), y - y.mean())
            if x.shape[1] > x.shape[0]
            else np.linalg.solve(z.T @ z + np.eye(x.shape[1]), z.T @ (y - y.mean()))
        )
        return {
            "points": points,
            "predictor": "ridge",
            "predictor_version": self.version,
            "center": center.tolist(),
            "scale": scale.tolist(),
            "weights": weights.tolist(),
            "intercept": float(y.mean()),
            "alpha": 1.0,
        }

    def predict(self, parameters: dict, vector: list[float]) -> tuple[float, float]:
        nearest = min(distance(p["features"], vector) for p in parameters["points"])
        z = [(v - c) / s for v, c, s in zip(vector, parameters["center"], parameters["scale"], strict=True)]
        return parameters["intercept"] + sum(w * v for w, v in zip(parameters["weights"], z, strict=True)), nearest


PREDICTORS: dict[str, Predictor] = {"knn": KNearestPredictor(), "ridge": RidgePredictor()}


def predictor(name: str) -> Predictor:
    if name not in PREDICTORS:
        raise ValueError("Unsupported predictor")
    return PREDICTORS[name]
