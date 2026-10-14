"""Kinetic triplet exports: measured traces, instrument fits and kinetics stay distinct."""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import least_squares  # type: ignore[import-untyped]

from ..diagnostics import check, finite_json, optimizer_diagnostics, quality, trace_arrays
from .bli import Curve, _r2_score, _simulate_1to1


def parse_kinetic_triplets(rows: list[list[str]]) -> list[Curve]:
    header_index = next((i for i, row in enumerate(rows[:30]) if row and row[0].strip() == "Time1"), None)
    if header_index is None or header_index < 2:
        raise ValueError("Kinetic export has no Time/Data/Fit header")
    header = list(rows[header_index])
    while header and not header[-1].strip():
        header.pop()
    if len(header) % 3:
        raise ValueError("Incomplete kinetic triplet header")
    count = len(header) // 3
    for i in range(count):
        if [item.strip() for item in header[3*i:3*i+3]] != [f"Time{i+1}", f"Data{i+1}", f"Fit{i+1}"]:
            raise ValueError("Expected matching Time/Data/Fit triplets in source order")
    metadata = {}
    for row in rows[:header_index-1]:
        if row:
            metadata[row[0].strip()] = row
    for required in ("Conc1", "Start1", "Stop1"):
        if required not in metadata:
            raise ValueError(f"Missing kinetic metadata: {required}")
    labels = rows[header_index-1]
    curves = []
    seen = set()
    for i in range(count):
        base = 3*i
        label = labels[base].strip() if base < len(labels) else ""
        if not label or label in seen or any(value.strip() != label for value in labels[base:base+3]):
            raise ValueError("Sensor labels must be unique and repeated consistently across each triplet")
        seen.add(label)
        meta = {}
        for key, row in metadata.items():
            if base+1 >= len(row) or row[base].strip() != key:
                raise ValueError("Kinetic metadata does not align with sensor columns")
            meta[key] = float(row[base+1].strip() or "nan")
        if not np.isfinite(meta["Conc1"]) or meta["Conc1"] < 0:
            raise ValueError("Concentrations must be finite non-negative molar values")
        if not np.isfinite(meta["Start1"]) or not np.isfinite(meta["Stop1"]) or meta["Start1"] >= meta["Stop1"]:
            raise ValueError("Invalid acquisition window")
        values = []
        for row in rows[header_index+1:]:
            if not any(item.strip() for item in row):
                continue
            if len(row) < len(header):
                raise ValueError("Truncated kinetic data row")
            try:
                triplet = [float(item.strip() or "nan") for item in row[base:base+3]]
            except ValueError as error:
                raise ValueError("Non-numeric kinetic trace value") from error
            # The instrument uses -99999 for unavailable fitted values only.
            if triplet[2] <= -99999:
                triplet[2] = float("nan")
            values.append(triplet)
        if not values:
            raise ValueError("Kinetic export has no observations")
        array = np.asarray(values, dtype=float)
        curves.append(Curve(label, label, meta["Conc1"]*1e9, array[:, 0], array[:, 1],
                            instrument_fit=array[:, 2], metadata=meta, source_format="kinetic_triplets"))
    return curves


def instrument_kinetics(curves: list[Curve]) -> dict[str, Any]:
    """Regress exported KObs, without interpreting dependent fit parameters as replicates."""
    selected = [c for c in curves if c.conc_nM > 0 and np.isfinite(c.metadata.get("KObs", float("nan")))]
    checks = [check("instrument_parameter_covariance_unavailable",
                    "KObs and KOff are instrument-fitted parameters. Their covariance and independent replicate uncertainty are unavailable; regression residuals cannot establish KD precision.")]
    if len({c.conc_nM for c in selected}) < 2:
        return {"kd": None, "quality_control": quality(checks), "uncertainty": {"kd_standard_error_nM": None, "confidence_interval_nM": None}}
    # nM keeps the intercept and concentration columns numerically resolvable.
    x = np.asarray([c.conc_nM for c in selected])
    y = np.asarray([c.metadata["KObs"] for c in selected])
    slope, intercept = np.linalg.lstsq(np.column_stack((x, np.ones(len(x)))), y, rcond=None)[0]
    residual = y - (slope*x + intercept)
    exact = bool(np.max(np.abs(residual)) <= max(float(np.max(np.abs(y))), 1e-12)*1e-10)
    if exact:
        checks.append(check("deterministic_kobs_relationship", "Exported KObs values are collinear to numerical precision; they may be generated from a shared instrument kinetic fit. R²=1 is not independent validation."))
    if slope <= 0 or intercept <= 0:
        checks.append(check("nonphysical_instrument_regression", "Exported parameters do not yield positive association and dissociation rates."))
    return finite_json({"kd": float(intercept/slope) if slope > 0 and intercept > 0 else None,
                        "kon": float(slope), "kon_M_inv_s": float(slope*1e9), "koff": float(intercept),
                        "r2": _r2_score(y, slope*x+intercept), "n_concentrations": len(set(x)),
                        "residual_degrees_of_freedom": len(x)-2, "deterministic_relationship": exact,
                        "evidence_kind": "instrument_reported_kinetics",
                        "uncertainty": {"kd_standard_error_nM": None, "confidence_interval_nM": None,
                                        "reason": "Instrument parameter covariance and independent replicate information are unavailable."},
                        "quality_control": quality(checks),
                        "parameters": [{"label": c.label, "concentration_nM": c.conc_nM, **c.metadata} for c in selected]})


def fit_measured(curves: list[Curve], *, t_assoc: float | None, t_dissoc: float | None,
                 reference: Curve | None = None, baseline_mode: str = "initial_point") -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Global 1:1 fit with shared rates, per-sensor Rmax and explicit baseline choice."""
    checks = [check("kinetic_assumptions", "A 1:1 fit does not validate concentration accuracy, immobilization, mass transport, rebinding or biological specificity.", warning=False),
              check("replicate_uncertainty_unavailable", "Time points are not independent assay replicates. No biological confidence interval is assigned; residual correlation and model sensitivity require review.")]
    if t_assoc is None:
        starts = {c.metadata.get("Start1") for c in curves}
        if len(starts) == 1 and None not in starts:
            start = next(iter(starts))
            if start is not None:
                t_assoc = float(start)
    if t_assoc is None or t_dissoc is None or not np.isfinite(t_assoc) or not np.isfinite(t_dissoc) or t_assoc >= t_dissoc:
        checks.append(check("phase_boundaries_required", "Supply the association/dissociation switch in absolute seconds. Start1/Stop1 specify acquisition bounds, not the phase switch."))
        return {"joint": None, "quality_control": quality(checks)}, {}
    entries = []
    traces = []
    for c in curves:
        t, y, metric = trace_arrays(c.time, c.response)
        traces.append({"label": c.label, **metric})
        if c.conc_nM == 0:
            continue
        if len(t) < 10 or not metric["strictly_increasing"]:
            checks.append(check("invalid_time_axis", "Sensor excluded because its measured time axis is incomplete or unordered.", label=c.label))
            continue
        if metric["excluded_nonfinite_points"]:
            checks.append(check("missing_points", "Non-finite measured points excluded without interpolation.", label=c.label, count=metric["excluded_nonfinite_points"]))
        mask = t >= t_assoc
        t, y = t[mask], y[mask]
        if np.sum(t <= t_dissoc) < 5 or np.sum(t > t_dissoc) < 5:
            checks.append(check("insufficient_phase_points", "Both phases require at least five measured points.", label=c.label))
            continue
        if reference is not None:
            rt, ry, rm = trace_arrays(reference.time, reference.response)
            if not rm["strictly_increasing"] or len(rt) < 2 or t[0] < rt[0] or t[-1] > rt[-1]:
                raise ValueError("Reference must have an ordered time axis covering every fitted measurement")
            y = y - np.interp(t, rt, ry)
        entries.append((c, t, y))
    if len({entry[0].conc_nM for entry in entries}) < 2:
        checks.append(check("sample_mapping_required", "At least two positive concentrations must be mapped to the same sample. Sensor labels alone do not establish sample identity."))
        return {"joint": None, "quality_control": quality(checks, traces=traces)}, {}
    n = len(entries)
    seed = instrument_kinetics([entry[0] for entry in entries])
    kon = max(min(seed.get("kon", 1e-4), 0.1), 1e-8)
    koff = max(min(seed.get("koff", 1e-3), 0.1), 1e-7)
    initial = [np.log(kon), np.log(koff)]
    initial += [np.log(max(float(np.ptp(y)), 0.01)) for _, _, y in entries]
    lower = [np.log(1e-10), np.log(1e-8)] + [np.log(1e-5)]*n
    upper = [np.log(1.0), np.log(1.0)] + [np.log(100.0)]*n
    if baseline_mode == "fitted_offset":
        initial += [float(y[0]) for _, _, y in entries]
        lower += [-20.0]*n
        upper += [20.0]*n
    else:
        checks.append(check("initial_point_baseline", "Each sensor baseline is fixed at its first observed point at or after association start; uncertainty in that point is not propagated.", warning=False))

    def offset(par: np.ndarray, index: int) -> float:
        return float(par[2+n+index]) if baseline_mode == "fitted_offset" else float(entries[index][2][0])

    def predict(par: np.ndarray, index: int, times: np.ndarray) -> np.ndarray:
        return _simulate_1to1(times, np.exp(par[0]), np.exp(par[1]), np.exp(par[2+index]),
                             entries[index][0].conc_nM, t_assoc, t_dissoc) + offset(par, index)

    def residual(par: np.ndarray) -> np.ndarray:
        return np.concatenate([predict(par, i, t)-y for i, (_, t, y) in enumerate(entries)])

    result = least_squares(residual, np.asarray(initial), bounds=(lower, upper), loss="linear", max_nfev=3000)
    kon, koff = np.exp(result.x[:2])
    names = ["log_kon", "log_koff"] + [f"log_rmax_{i}" for i in range(n)]
    if baseline_mode == "fitted_offset":
        names += [f"offset_{i}" for i in range(n)]
        for i, (c, _, y) in enumerate(entries):
            if abs(offset(result.x, i)-y[0]) > 0.1*float(np.ptp(y)):
                checks.append(check("baseline_displacement", "Fitted offset differs from the initial measured response by more than 10% of trace range; flexible baselines may absorb model mismatch.", label=c.label))
    diagnostics = optimizer_diagnostics(result, names)
    diagnostics["uncertainty"] = "No confidence interval: serially correlated trace residuals and assay replicate variation are not modeled."
    diagnostics["residual_lag1_correlation"] = [float(np.corrcoef((predict(result.x, i, t)-y)[:-1], (predict(result.x, i, t)-y)[1:])[0, 1]) for i, (_, t, y) in enumerate(entries)]
    if not result.success or diagnostics["active_bounds"]:
        checks.append(check("optimizer_review", "Review optimizer convergence and active bounds.", converged=bool(result.success), bounds=diagnostics["active_bounds"]))
    if any(abs(corr) > 0.5 for corr in diagnostics["residual_lag1_correlation"]):
        checks.append(check("serially_correlated_residuals", "Adjacent residuals are strongly correlated; an IID residual confidence interval would overstate precision."))
    observations = np.concatenate([y for _, _, y in entries])
    overlays = {c.label: predict(result.x, i, c.time) for i, (c, _, _) in enumerate(entries)}
    joint = {"kd": float(koff/kon) if result.success else None, "kon": float(kon), "kon_M_inv_s": float(kon*1e9), "koff": float(koff),
             "r2": _r2_score(observations, observations+result.fun), "diagnostics": diagnostics,
             "sensor_parameters": [{"label": c.label, "rmax": float(np.exp(result.x[2+i])), "offset": offset(result.x, i)} for i, (c, _, _) in enumerate(entries)]}
    return finite_json({"joint": joint, "phase": {"t_assoc": t_assoc, "t_dissoc": t_dissoc},
                        "quality_control": quality(checks, traces=traces, fitted_curve_count=n, phase_source="explicit_switch", reference_label=reference.label if reference else None)}), overlays
