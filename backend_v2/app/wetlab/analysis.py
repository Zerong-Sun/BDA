"""Turn an uploaded instrument file into an analysed, recorded experiment.

The shape of this module is dictated by how uploads work here: the API never
receives a file body. A client PUTs to a presigned URL, completes the upload,
and hands us an artifact id. So the flow is

    artifact id -> bytes from object storage -> kernel -> ExperimentResult

and the artifact stays as the raw snapshot the result points back at. That is
the same immutability protein-lab built its `experiment_raw` table for, except
artifacts are already write-once and checksummed, so no second table is needed.

Two rules carried over from the source workbench, both load-bearing:

* **The analysis version goes into the result.** Without it, a stored number
  cannot be told apart from one the same kernel would produce differently after
  a fix, and no archived result can be re-derived with confidence.
* **Raw data is never rewritten.** Re-analysing the same artifact produces a new
  result row, not an edit of the old one, so a superseded conclusion stays
  visible next to the one that replaced it.
"""

from __future__ import annotations

import hashlib
import math
import uuid
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..artifacts.storage import ObjectStorage
from ..core.problem import DomainError
from ..experiments.models import ExperimentResult
from .diagnostics import check, finite_json, quality, trace_arrays
from .kernels import akta, bli, bli_kinetic, calculators

#: Instrument files are small - a ForteBio CSV or a Unicorn export is a few MB.
#: The cap is a guard against a mis-typed artifact id pulling a genome into
#: memory, not a real limit on any instrument this supports.
MAX_INSTRUMENT_BYTES = 64 * 1024 * 1024

#: How many points of a trace the response carries per series.
#:
#: The plot belongs to the browser and the kernels return data, so the series
#: has to travel; a raw sensorgram is tens of thousands of points and a screen
#: is around a thousand pixels wide, so sending all of them costs bandwidth and
#: shows nothing more. Decimated by stride rather than averaged, because a
#: smoothed trace would no longer be the recorded measurement.
#:
#: A decimated plot snapshot is stored with each BLI analysis version so a
#: saved review preserves its overlays; the artifact retains the original bytes.
TRACE_POINTS = 600


def _decimate(xs: Any, ys: Any, limit: int = TRACE_POINTS) -> list[list[float]]:
    """Every nth point of a series, as [x, y] pairs, with the last point kept.

    NaNs are dropped rather than sent: JSON has no NaN, and a gap the client can
    see as a gap is more honest than a zero.
    """
    pairs = [
        [float(x), float(y)]
        for x, y in zip(list(xs), list(ys), strict=False)
        if math.isfinite(float(x)) and math.isfinite(float(y))
    ]
    if len(pairs) <= limit:
        return pairs
    stride = len(pairs) // limit + 1
    thinned = pairs[::stride]
    if thinned[-1] != pairs[-1]:
        thinned.append(pairs[-1])
    return thinned


def _load_artifact(session: Session, project_id: uuid.UUID, artifact_id: uuid.UUID) -> Artifact:
    artifact = session.scalar(select(Artifact).where(Artifact.id == artifact_id, Artifact.deleted_at.is_(None)))
    if artifact is None or artifact.project_id != project_id or artifact.status != "available":
        raise DomainError(
            "artifact_not_found",
            "No such artifact in this project.",
            status_code=404,
        )
    return artifact


def _read(artifact: Artifact) -> bytes:
    try:
        body = ObjectStorage().read_bytes(artifact.object_key, max_bytes=MAX_INSTRUMENT_BYTES)
        if len(body) != artifact.size_bytes or hashlib.sha256(body).hexdigest() != artifact.checksum_sha256:
            raise DomainError("instrument_source_integrity", "Raw instrument file does not match its completed artifact", status_code=409)
        return body
    except ValueError as error:
        raise DomainError(
            "instrument_file_too_large",
            f"That artifact is larger than {MAX_INSTRUMENT_BYTES // (1024 * 1024)} MB.",
            status_code=413,
        ) from error


def _record(
    session: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    artifact: Artifact,
    experiment_type: str,
    params: dict[str, Any],
    results: dict[str, Any],
    analysis_version: str,
    value: float | None,
    unit: str | None,
    candidate_id: uuid.UUID | None,
) -> ExperimentResult:
    if candidate_id is not None:
        from ..candidates.models import Candidate

        candidate = session.get(Candidate, candidate_id)
        if candidate is None or candidate.project_id != project_id:
            raise DomainError("candidate_not_found", "Project candidate was not found", status_code=404)
    row = ExperimentResult(
        project_id=project_id,
        candidate_id=candidate_id,
        source_artifact_id=artifact.id,
        experiment_type=experiment_type,
        pass_status="unknown",
        value=value,
        unit=unit,
        result_metadata={
            # params and results are kept apart: one is what was asked for, the
            # other what came back, and a re-run compares them separately.
            "params": params,
            "results": results,
            "analysis_version": analysis_version,
            "source_filename": artifact.filename,
            "instrument_qc_review": {"status": "pending"},
        },
        created_by=user_id,
    )
    session.add(row)
    session.flush()
    return row


def analyse_bli(
    session: Session, project_id: uuid.UUID, user_id: uuid.UUID, artifact_id: uuid.UUID, *,
    sample_id: str | None = None, t_assoc: float | None = None, t_dissoc: float | None = None,
    candidate_id: uuid.UUID | None = None, sample_mapping: dict[str, str] | None = None,
    excluded_labels: list[str] | None = None, reference_label: str | None = None,
    analysis_method: str = "measured_global", correction_note: str | None = None, baseline_mode: str = "initial_point",
    supersedes_result_id: uuid.UUID | None = None,
) -> tuple[ExperimentResult, dict[str, Any]]:
    """Append an analysis and its plot snapshot; never update the source or prior fit."""
    artifact = _load_artifact(session, project_id, artifact_id)
    if supersedes_result_id is not None:
        prior = session.get(ExperimentResult, supersedes_result_id)
        if (prior is None or prior.project_id != project_id or prior.source_artifact_id != artifact.id
                or prior.experiment_type != "bli_affinity"):
            raise DomainError("bli_lineage_invalid", "Previous analysis must belong to this project and raw artifact.", status_code=422)
        if not correction_note or not correction_note.strip():
            raise DomainError("bli_correction_note_required", "Explain the correction when superseding an analysis.", status_code=422)
    measurement, summary = analyse_bli_bytes(
        _read(artifact), sample_id=sample_id, t_assoc=t_assoc, t_dissoc=t_dissoc,
        sample_mapping=sample_mapping, excluded_labels=excluded_labels, reference_label=reference_label,
        analysis_method=analysis_method, correction_note=correction_note, baseline_mode=baseline_mode,
    )
    summary["source_artifact_id"] = str(artifact.id)
    summary["supersedes_result_id"] = str(supersedes_result_id) if supersedes_result_id else None
    row = _record(session, project_id=project_id, user_id=user_id, artifact=artifact,
                  candidate_id=candidate_id, **measurement)
    row.result_metadata = {**row.result_metadata, "source_checksum_sha256": artifact.checksum_sha256,
                           "source_artifact_id": str(artifact.id), "summary": summary,
                           "supersedes_result_id": summary["supersedes_result_id"],
                           "evidence_kind": summary["evidence_kind"]}
    session.flush()
    return row, summary


def analyse_bli_bytes(
    data: bytes, *, sample_id: str | None = None, t_assoc: float | None = None, t_dissoc: float | None = None,
    sample_mapping: dict[str, str] | None = None, excluded_labels: list[str] | None = None,
    reference_label: str | None = None, analysis_method: str = "measured_global", correction_note: str | None = None, baseline_mode: str = "initial_point",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if any(value is not None and not math.isfinite(value) for value in (t_assoc, t_dissoc)):
        raise DomainError("bli_phase_invalid", "Supplied phase times must be finite seconds.", status_code=422)
    try:
        curves = bli.parse_bli_csv(data)
    except (UnicodeError, ValueError) as error:
        raise DomainError("bli_format_invalid", str(error), status_code=422) from error
    if not curves:
        raise DomainError("bli_no_curves", "That file contained no usable curves.", status_code=422)
    if analysis_method not in {"measured_global", "instrument_kobs"}:
        raise DomainError("bli_method_invalid", "Unknown BLI analysis method.", status_code=422)
    if baseline_mode not in {"initial_point", "fitted_offset"}:
        raise DomainError("bli_baseline_invalid", "Unknown baseline mode.", status_code=422)
    labels = {curve.label for curve in curves}
    mapping, excluded = sample_mapping or {}, set(excluded_labels or [])
    if set(mapping)-labels or excluded-labels or (reference_label is not None and reference_label not in labels):
        raise DomainError("bli_sensor_not_found", "Sample mapping, exclusions and reference must name source sensor labels.", status_code=422)
    if any(not name.strip() for name in mapping.values()):
        raise DomainError("bli_sample_mapping_invalid", "Mapped sample identities cannot be blank.", status_code=422)
    for curve in curves:
        curve.sample_id = mapping.get(curve.label, curve.sample_id)
    grouped = bli.group_by_sample(curves)
    if sample_id is not None and sample_id not in grouped:
        raise DomainError("bli_sample_not_found", f"No sample {sample_id!r} in that file. Present: {', '.join(sorted(grouped))}.", status_code=422)
    chosen = sample_id or max(grouped, key=lambda key: len(grouped[key]))
    selected = [curve for curve in grouped[chosen] if curve.label not in excluded]
    reference = next((c for c in curves if c.label == reference_label), None)
    if reference is not None and (reference.conc_nM != 0 or reference.label in excluded):
        raise DomainError("bli_reference_invalid", "Reference must be a non-excluded zero-concentration sensor.", status_code=422)
    source_format = curves[0].source_format
    instrument = bli_kinetic.instrument_kinetics(selected) if source_format == "kinetic_triplets" else None
    overlays: dict[str, Any] = {}
    fit: dict[str, Any]
    if source_format == "kinetic_triplets" and analysis_method == "instrument_kobs":
        # Independent evidence path: invalid measured windows or optimizer inputs
        # must not prevent reading exported instrument kinetics.
        fit = {"joint": None, "phase": None}
    elif source_format == "kinetic_triplets":
        try:
            fit, overlays = bli_kinetic.fit_measured(selected, t_assoc=t_assoc, t_dissoc=t_dissoc, reference=reference, baseline_mode=baseline_mode)
        except ValueError as error:
            raise DomainError("bli_processing_invalid", str(error), status_code=422) from error
    else:
        if analysis_method == "instrument_kobs":
            raise DomainError("bli_instrument_kinetics_unavailable", "This format does not contain instrument kinetic parameters.", status_code=422)
        if reference is not None:
            raise DomainError("bli_reference_unsupported", "Explicit reference subtraction is supported for kinetic triplet exports.", status_code=422)
        if baseline_mode != "initial_point":
            raise DomainError("bli_baseline_unsupported", "Explicit fitted offsets are supported for kinetic triplet exports.", status_code=422)
        fit = bli.fit_kd(selected, t_assoc=t_assoc, t_dissoc=t_dissoc)
    primary = instrument if analysis_method == "instrument_kobs" else (fit.get("joint") or fit.get("standard") or {})
    primary = primary or {}
    kd = primary.get("kd")
    evidence_kind = "instrument_reported_kinetics" if analysis_method == "instrument_kobs" else "measured_trace_fit"
    qc = primary.get("quality_control") if analysis_method == "instrument_kobs" else fit.get("quality_control")
    if analysis_method == "measured_global" and isinstance(kd, int | float) and instrument and instrument.get("kd"):
        ratio = kd / instrument["kd"]
        if (ratio > 2 or ratio < 0.5) and isinstance(qc, dict):
            qc["checks"].append(check("instrument_refit_disagreement", "Measured-trace refit and instrument-derived KD differ by more than two-fold. Investigate model, phase, baseline and reference settings before accepting a quantitative conclusion.", ratio=ratio))
    uncertainty = primary.get("uncertainty") or {
        "kd_standard_error_nM": None, "confidence_interval_nM": None,
        "reason": "Independent assay replicates and a validated residual/covariance model are unavailable.",
    }
    processing = {"sample_mapping": mapping, "excluded_labels": sorted(excluded), "reference_label": reference_label,
                  "correction_note": correction_note, "analysis_method": analysis_method,
                  "baseline": ("instrument_parameters_no_trace_preprocessing" if analysis_method == "instrument_kobs" else
                               baseline_mode if source_format == "kinetic_triplets" else "legacy_kernel"),
                  "baseline_mode": baseline_mode, "reference_applied": reference is not None and analysis_method == "measured_global",
                  "concentration_input_unit": "M" if source_format == "kinetic_triplets" else "nM",
                  "concentration_analysis_unit": "nM", "time_unit": "s", "response_unit": "nm"}
    fit = {**fit, "instrument_kobs": instrument, "quality_control": qc, "uncertainty": uncertainty,
           "evidence_kind": evidence_kind, "selected_method": analysis_method}
    measurement = dict(experiment_type="bli_affinity",
                       params={"sample_id": chosen, "t_assoc": t_assoc, "t_dissoc": t_dissoc,
                               "curve_count": len(selected), **processing},
                       results=fit, analysis_version=bli.BLI_ANALYSIS_VERSION,
                       value=float(kd) if isinstance(kd, int | float) and math.isfinite(kd) else None,
                       unit="nM" if isinstance(kd, int | float) and math.isfinite(kd) else None)
    # Without a mapping, discovery returns every sensor so users can name groups.
    display = curves if source_format == "kinetic_triplets" and not mapping and sample_id is None else grouped[chosen]
    summary = {"sample_id": chosen, "samples_available": sorted(grouped), "kd_nM": measurement["value"],
               "source_format": source_format, "source_checksum_sha256": hashlib.sha256(data).hexdigest(),
               "evidence_kind": evidence_kind, "selected_method": analysis_method, "processing": processing,
               "uncertainty": uncertainty, "instrument_kinetics": instrument,
               "methods": {name: fit.get(name) for name in ("standard", "split", "joint", "steady", "mixed", "instrument_kobs")},
               "phase": fit.get("phase"), "quality_control": qc,
               "curves": [{"label": c.label, "sample_id": c.sample_id, "conc_nM": c.conc_nM,
                           "points": _decimate(c.time, c.response), "evidence_kind": "measured",
                           "excluded": c.label in excluded, "acquisition": c.metadata,
                           "instrument_fit_points": _decimate(c.time, c.instrument_fit) if c.instrument_fit is not None else [],
                           "instrument_fit_r2": _instrument_fit_r2(c),
                           "analysis_fit_points": _decimate(c.time, overlays[c.label]) if c.label in overlays else [],
                           "analysis_fit_basis": "reference_subtracted" if reference_label else "measured",
                           "processed_points": _decimate(c.time, c.response - np.interp(c.time, reference.time, reference.response)) if reference is not None and analysis_method == "measured_global" else [],
                           } for c in sorted(display, key=lambda item: item.conc_nM, reverse=True)]}
    return measurement, finite_json(summary)


def _instrument_fit_r2(curve: bli.Curve) -> float | None:
    if curve.instrument_fit is None:
        return None
    valid = np.isfinite(curve.response) & np.isfinite(curve.instrument_fit)
    if np.sum(valid) < 2 or np.ptp(curve.response[valid]) == 0:
        return None
    return float(bli._r2_score(curve.response[valid], curve.instrument_fit[valid]))


def analyse_akta(
    session: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    artifact_id: uuid.UUID,
    *,
    channel: str | None = None,
    candidate_id: uuid.UUID | None = None,
) -> tuple[ExperimentResult, dict[str, Any]]:
    """Detect peaks in an AKTA Unicorn export and record the peak table."""
    artifact = _load_artifact(session, project_id, artifact_id)
    measurement, summary = analyse_akta_bytes(_read(artifact), channel=channel)
    row = _record(
        session, project_id=project_id, user_id=user_id, artifact=artifact, candidate_id=candidate_id, **measurement
    )
    return row, summary


def analyse_akta_bytes(data: bytes, *, channel: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    parsed = akta.parse_akta_zip(data)
    channels = parsed["channels"]
    if not channels:
        raise DomainError(
            "akta_no_channels",
            "That export contained no decodable channels.",
            status_code=422,
        )

    if channel is not None and channel not in channels:
        raise DomainError(
            "akta_channel_not_found",
            f"No channel {channel!r}. Present: {', '.join(sorted(channels))}.",
            status_code=422,
        )
    # Default to a UV trace: it is what a purification is read off, and the
    # export also carries conductivity and pressure nobody picks peaks from.
    uv = akta.find_uv_channels(channels)
    chosen = channel or (uv[0] if uv else sorted(channels)[0])

    trace = channels[chosen]
    volumes, amplitudes, trace_metric = trace_arrays(trace.vols, trace.amps)
    checks = []
    if trace_metric["excluded_nonfinite_points"]:
        checks.append(check("missing_points", "Non-finite chromatogram points were excluded; inspect gaps before accepting peak areas.", count=trace_metric["excluded_nonfinite_points"]))
    valid_trace = len(volumes) >= 5 and trace_metric["strictly_increasing"]
    if not valid_trace:
        checks.append(check("invalid_volume_axis", "Peak integration requires at least five finite, strictly increasing volume points."))
    clean_trace = akta.Channel(trace.name, trace.data_type, trace.unit, volumes, amplitudes)
    peaks = akta.detect_peaks(clean_trace) if valid_trace else []
    rows = akta.peaks_to_rows(peaks)
    fractions = akta.fraction_ranges(akta.find_fraction_events(parsed["events"]))

    if chosen not in uv:
        checks.append(check("non_uv_channel", "Selected channel is not identified as UV; its area is not recorded as a protein UV peak-area measurement."))
    if not trace.unit:
        checks.append(check("unknown_amplitude_unit", "Amplitude units are unavailable; quantitative peak-area units cannot be established."))
    for index, peak in enumerate(peaks):
        if peak.start_vol <= volumes[0] or peak.end_vol >= volumes[-1]:
            checks.append(check("boundary_truncated_peak", "Integration reaches a trace boundary; the complete peak area may not have been observed.", peak=index))
        if any(peak.start_vol < other.end_vol and other.start_vol < peak.end_vol for other in peaks[index + 1:]):
            checks.append(check("overlapping_peak_windows", "Detected peak integration windows overlap; their areas must not be summed as independent components.", peak=index))
    checks.append(check("peak_identity_unverified", "A UV peak and baseline-corrected area do not establish protein identity, purity or yield. Baseline is the 5th percentile after smoothing.", warning=False))
    qc = quality(checks, trace=trace_metric, detected_peaks=len(peaks), min_height=5.0, smoothing_window=11,
                 area_definition="smoothed amplitude minus 5th-percentile baseline integrated over volume")
    largest = max((peak.area for peak in peaks), default=None) if chosen in uv and trace.unit else None
    measurement = dict(
        experiment_type="akta_purification",
        params={"channel": chosen, "channels_available": sorted(channels)},
        results={
            "peaks": rows,
            "fractions": [{"start": start, "end": end, "label": label} for start, end, label in fractions],
            "meta": parsed.get("meta", {}),
            "quality_control": qc,
        },
        analysis_version=f"{akta.AKTA_ANALYSIS_VERSION}-qc1",
        value=float(largest) if largest is not None else None,
        unit=f"{trace.unit}*mL" if largest is not None else None,
    )
    return measurement, {
        "channel": chosen,
        "channels_available": sorted(channels),
        "peak_count": len(rows),
        "quality_control": qc,
        "peaks": rows,
        "unit": channels[chosen].unit,
        "trace": _decimate(channels[chosen].vols, channels[chosen].amps),
        "fractions": [{"start": start, "end": end, "label": label} for start, end, label in fractions],
    }


def analyse_enzyme(
    session: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    artifact_id: uuid.UUID,
    *,
    subtract_background: bool = True,
    candidate_id: uuid.UUID | None = None,
) -> tuple[ExperimentResult, dict[str, Any]]:
    """Fit per-well rates from a TECAN plate reader export.

    Background is subtracted from the negative control only. A correction that
    also shifted the samples would be counted twice once rates are corrected.
    """
    artifact = _load_artifact(session, project_id, artifact_id)
    measurement, summary = analyse_enzyme_bytes(_read(artifact), subtract_background=subtract_background)
    row = _record(
        session, project_id=project_id, user_id=user_id, artifact=artifact, candidate_id=candidate_id, **measurement
    )
    return row, summary


def analyse_enzyme_bytes(data: bytes, *, subtract_background: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    plate = calculators.parse_tecan_xlsx(data)
    wells = plate.get("wells") or {}
    if not wells:
        raise DomainError("enzyme_no_wells", "That workbook contained no readable wells.", status_code=422)

    corrected, background = calculators.sub_blank(wells, enabled=subtract_background)
    fits = finite_json({
        name: calculators.fit_kinetics(data.get("times") or [], data.get("od") or [])
        for name, data in corrected.items()
    })
    slopes = [fit["slope"] for fit in fits.values() if fit.get("slope") is not None]
    checks = [check("initial_rate_window_unverified", "Fits use the entire observed time window. A linear trend is not automatically an initial enzymatic rate.", warning=False),
              check("well_mapping_unverified", "The summary takes the maximum well slope. Confirm sample/control roles and the candidate-to-well mapping before accepting it.")]
    if subtract_background and background is None:
        checks.append(check("background_unavailable", "Background subtraction was requested but no annotated negative or blank control was available."))
    for name, fit in fits.items():
        diagnostics = fit["diagnostics"]
        if diagnostics["status"] != "fitted":
            checks.append(check("well_not_fitted", "Well lacks enough ordered finite time points; no numeric rate was assigned.", well=name))
        if diagnostics["residual_degrees_of_freedom"] <= 0:
            checks.append(check("insufficient_residual_dof", "A line through two points cannot estimate residual variance or a slope confidence interval.", well=name))
        if diagnostics["excluded_nonfinite_points"]:
            checks.append(check("missing_points", "Non-finite well observations were excluded; review measurement gaps.", well=name, count=diagnostics["excluded_nonfinite_points"]))
        if diagnostics["response_range"] == 0:
            checks.append(check("constant_response", "No response variation was observed. This does not distinguish inactivity, detection limits or instrument failure.", well=name))
    qc = quality(checks, fitted_wells=len(slopes), total_wells=len(wells), summary_rule="maximum_finite_well_slope")

    measurement = dict(
        experiment_type="enzyme_activity",
        params={
            "subtract_background": subtract_background,
            "well_count": len(wells),
            "meta": plate.get("meta", {}),
        },
        results={
            "fits": fits,
            "background_subtracted": background is not None,
            "quality_control": qc,
        },
        # Enzyme fitting lives in calculators, which has no version constant of
        # its own; the kernels were ported together, so BLI's stands for the set.
        analysis_version=f"calculators/{bli.BLI_ANALYSIS_VERSION}",
        value=max(slopes) if slopes else None,
        unit="dOD/min" if slopes else None,
    )
    return measurement, {
        "well_count": len(wells),
        "fits": fits,
        "background_subtracted": background is not None,
        "quality_control": qc,
        # Background-corrected, because that is what was fitted; plotting the
        # raw wells beside a corrected slope would invite reading one off the
        # other.
        "wells": [
            {"well": name, "points": _decimate(data.get("times") or [], data.get("od") or [])}
            for name, data in sorted(corrected.items())
        ],
    }


#: What each wet-lab experiment type measures, as a normalised metric key and
#: unit. Normalised so a filter does not need to know which instrument produced
#: the number - the same reason computed metrics share "plddt" across tools.
MEASURED_METRICS: dict[str, tuple[str, str]] = {
    "bli_affinity": ("kd", "nM"),
    "enzyme_activity": ("activity_rate", "dOD/min"),
    "akta_purification": ("peak_area", "mAU*mL"),
}


def record_measured_metric(session: Session, result: ExperimentResult) -> Any | None:
    """Write a bench measurement onto the candidate it tested.

    This is the return half of the loop. A candidate already accumulates
    computed metrics from folding and scoring; a measured one lands in the same
    table with `evidence_kind="measured"`, so "predicted 12 nM, measured 40 nM"
    is one query rather than two systems and a spreadsheet.

    `evidence_kind` is what keeps the two apart. The column exists precisely so a
    predicted number is never read as a measurement, and this is the first code
    to write the other side of that distinction.

    Returns None when there is nothing to record: no candidate to attach to, no
    value fitted, or an experiment type with no agreed metric key.
    """
    from ..candidates.models import Candidate, CandidateMetric

    if result.candidate_id is not None:
        candidate = session.scalar(select(Candidate).where(Candidate.id == result.candidate_id,
                                   Candidate.project_id == result.project_id).with_for_update())
        if candidate is None:
            raise DomainError("candidate_not_found", "Project candidate was not found", status_code=404)
    review = result.result_metadata.get("instrument_qc_review", {})
    if review.get("status") != "accepted":
        # Projection is disposable; preserve the original result and audit history.
        session.query(CandidateMetric).filter(CandidateMetric.source_experiment_result_id == result.id).delete(synchronize_session="fetch")
        session.flush()
        return None
    if result.candidate_id is None or result.value is None or not math.isfinite(result.value):
        return None
    mapping = MEASURED_METRICS.get(result.experiment_type)
    if mapping is None:
        return None
    metric_key, unit = mapping
    summary = result.result_metadata.get("summary", {})
    metric_context = {
        "analysis_version": result.result_metadata.get("analysis_version", ""), "qc_review": review,
        "source_evidence_kind": result.result_metadata.get("evidence_kind", "measured"),
        "selected_method": summary.get("selected_method"), "processing": summary.get("processing"),
        "source_artifact_id": str(result.source_artifact_id) if result.source_artifact_id else None,
        "source_checksum_sha256": result.result_metadata.get("source_checksum_sha256"),
    }

    # The unique key is (candidate, metric, method, variant, condition). Method
    # is the experiment type so a KD from BLI and one from another assay do not
    # overwrite each other, and re-analysing the same run updates in place
    # rather than accumulating a row per attempt.
    existing = session.scalar(
        select(CandidateMetric).where(
            CandidateMetric.candidate_id == result.candidate_id,
            CandidateMetric.metric_key == metric_key,
            CandidateMetric.method == result.experiment_type,
            CandidateMetric.model_variant == "",
            CandidateMetric.condition == "",
        )
    )
    if existing is not None:
        existing.value = float(result.value)
        existing.unit = result.unit or unit
        existing.source_experiment_result_id = result.id
        existing.context = {**existing.context, **metric_context}
        existing.version += 1
        session.flush()
        return existing

    metric = CandidateMetric(
        candidate_id=result.candidate_id,
        metric_key=metric_key,
        value=float(result.value),
        method=result.experiment_type,
        model_variant="",
        # Not a prediction. This is the distinction the column was added for.
        evidence_kind="measured",
        # A bench instrument is as independent as an assessor gets: it has no
        # stake in the design model's ranking.
        assessor="instrument",
        condition="",
        unit=result.unit or unit,
        context=metric_context,
        source_experiment_result_id=result.id,
    )
    session.add(metric)
    session.flush()
    return metric
