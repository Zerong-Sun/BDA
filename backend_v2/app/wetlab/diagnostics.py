"""Named diagnostic observations, never a biological pass/fail classifier."""

from __future__ import annotations

from typing import Any

import numpy as np

QC_VERSION = "instrument-qc-v1"


def check(code: str, message: str, *, warning: bool = True, **details: Any) -> dict:
    return {"code": code, "status": "review" if warning else "information", "message": message, "details": details}


def quality(checks: list[dict], **metrics: Any) -> dict:
    return finite_json(
        {
            "version": QC_VERSION,
            "review_required": True,
            "checks": checks,
            "metrics": metrics,
            "interpretation": "Diagnostics describe measurement and model assumptions; human QC acceptance does not establish binding, activity or assay validation.",
        }
    )


def trace_arrays(xs: Any, ys: Any) -> tuple[np.ndarray, np.ndarray, dict]:
    x, y = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y):
        raise ValueError("Trace coordinates and responses must be equally sized one-dimensional arrays")
    finite = np.isfinite(x) & np.isfinite(y)
    usable_x, usable_y = x[finite], y[finite]
    return (
        usable_x,
        usable_y,
        {
            "input_points": len(x),
            "finite_points": int(finite.sum()),
            "excluded_nonfinite_points": int((~finite).sum()),
            "strictly_increasing": bool(len(usable_x) > 1 and np.all(np.diff(usable_x) > 0)),
            "response_range": float(np.ptp(usable_y)) if len(usable_y) else None,
        },
    )


def optimizer_diagnostics(result: Any, names: list[str]) -> dict:
    residual = np.asarray(result.fun, dtype=float)
    jac = np.asarray(result.jac, dtype=float)
    scale = np.linalg.norm(jac, axis=0)
    normalized = jac / np.where(scale > 0, scale, 1)
    singular = np.linalg.svd(normalized, compute_uv=False)
    rank = int(np.linalg.matrix_rank(normalized))
    condition = float(singular[0] / singular[-1]) if len(singular) and singular[-1] > 0 else None
    return {
        "converged": bool(result.success),
        "optimizer_status": int(result.status),
        "residual_points": len(residual),
        "parameter_count": len(names),
        "residual_degrees_of_freedom": len(residual) - len(names),
        "residual_rmse": float(np.sqrt(np.mean(residual**2))) if len(residual) else None,
        "active_bounds": [name for name, active in zip(names, result.active_mask, strict=True) if active],
        "scaled_jacobian_rank": rank,
        "scaled_jacobian_condition": condition,
        "identifiability": "numerically_rank_deficient" if rank < len(names) else "full_numerical_rank_only",
        "uncertainty": "No parameter confidence interval: robust-loss Jacobian diagnostics do not establish independent residuals or biological identifiability.",
    }


def finite_json(value: Any) -> Any:
    """Unidentifiable/non-finite fits are unavailable, never JSON NaN or zero."""
    if isinstance(value, dict):
        return {key: finite_json(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [finite_json(item) for item in value]
    if isinstance(value, float | np.floating):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value
