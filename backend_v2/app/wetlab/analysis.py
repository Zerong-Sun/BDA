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

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..artifacts.storage import ObjectStorage
from ..core.problem import DomainError
from ..experiments.models import ExperimentResult
from .kernels import akta, bli, calculators

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
#: The series is returned, never stored: `result_metadata` keeps the fitted
#: numbers, and the artifact remains the trace's one immutable copy.
TRACE_POINTS = 600


def _decimate(xs: Any, ys: Any, limit: int = TRACE_POINTS) -> list[list[float]]:
    """Every nth point of a series, as [x, y] pairs, with the last point kept.

    NaNs are dropped rather than sent: JSON has no NaN, and a gap the client can
    see as a gap is more honest than a zero.
    """
    import math

    pairs = [
        [float(x), float(y)]
        for x, y in zip(list(xs), list(ys), strict=False)
        if not (math.isnan(float(x)) or math.isnan(float(y)))
    ]
    if len(pairs) <= limit:
        return pairs
    stride = len(pairs) // limit + 1
    thinned = pairs[::stride]
    if thinned[-1] != pairs[-1]:
        thinned.append(pairs[-1])
    return thinned


def _load_artifact(session: Session, project_id: uuid.UUID, artifact_id: uuid.UUID) -> Artifact:
    artifact = session.scalar(
        select(Artifact).where(Artifact.id == artifact_id, Artifact.deleted_at.is_(None))
    )
    if artifact is None or artifact.project_id != project_id:
        raise DomainError(
            "artifact_not_found",
            "No such artifact in this project.",
            status_code=404,
        )
    return artifact


def _read(artifact: Artifact) -> bytes:
    try:
        return ObjectStorage().read_bytes(artifact.object_key, max_bytes=MAX_INSTRUMENT_BYTES)
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
        },
        created_by=user_id,
    )
    session.add(row)
    session.flush()
    record_measured_metric(session, row)
    return row


def analyse_bli(
    session: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    artifact_id: uuid.UUID,
    *,
    sample_id: str | None = None,
    t_assoc: float | None = None,
    t_dissoc: float | None = None,
    candidate_id: uuid.UUID | None = None,
) -> tuple[ExperimentResult, dict[str, Any]]:
    """Fit KD from a ForteBio export.

    `t_assoc`/`t_dissoc` are worth passing whenever the run declares them: the
    kernel falls back to a heuristic that reads the phase boundary off the
    smoothed curve, which is fine for exploration and not what you want behind
    a recorded number.
    """
    artifact = _load_artifact(session, project_id, artifact_id)
    curves = bli.parse_fortebio_csv(_read(artifact))
    if not curves:
        raise DomainError("bli_no_curves", "That file contained no usable curves.", status_code=422)

    grouped = bli.group_by_sample(curves)
    if sample_id is not None and sample_id not in grouped:
        raise DomainError(
            "bli_sample_not_found",
            f"No sample {sample_id!r} in that file. Present: {', '.join(sorted(grouped))}.",
            status_code=422,
        )
    chosen = sample_id or max(grouped, key=lambda key: len(grouped[key]))
    fit = bli.fit_kd(grouped[chosen], t_assoc=t_assoc, t_dissoc=t_dissoc)

    # The five methods disagree on real data; `joint` is the global fit over all
    # concentrations at once, which is the one to record when it converged.
    primary = fit.get("joint") or fit.get("standard") or {}
    kd = primary.get("kd") if isinstance(primary, dict) else None

    row = _record(
        session,
        project_id=project_id,
        user_id=user_id,
        artifact=artifact,
        experiment_type="bli_affinity",
        params={
            "sample_id": chosen,
            "t_assoc": t_assoc,
            "t_dissoc": t_dissoc,
            "curve_count": len(grouped[chosen]),
        },
        results=fit,
        analysis_version=bli.BLI_ANALYSIS_VERSION,
        value=float(kd) if isinstance(kd, int | float) else None,
        unit="nM" if isinstance(kd, int | float) else None,
        candidate_id=candidate_id,
    )
    summary = {
        "sample_id": chosen,
        "samples_available": sorted(grouped),
        "kd_nM": kd,
        "methods": {name: fit.get(name) for name in ("standard", "split", "joint", "steady", "mixed")},
        "phase": fit.get("phase"),
        # The sensorgrams themselves, so the browser can draw what was fitted
        # rather than only the numbers that came out of it. A KD with no curve
        # behind it cannot be judged.
        "curves": [
            {
                "label": curve.label,
                "conc_nM": curve.conc_nM,
                "points": _decimate(curve.time, curve.response),
            }
            for curve in sorted(grouped[chosen], key=lambda item: item.conc_nM, reverse=True)
        ],
    }
    return row, summary


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
    parsed = akta.parse_akta_zip(_read(artifact))
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

    peaks = akta.detect_peaks(channels[chosen])
    rows = akta.peaks_to_rows(peaks)
    fractions = akta.fraction_ranges(akta.find_fraction_events(parsed["events"]))

    largest = max((peak.area for peak in peaks), default=None)
    row = _record(
        session,
        project_id=project_id,
        user_id=user_id,
        artifact=artifact,
        experiment_type="akta_purification",
        params={"channel": chosen, "channels_available": sorted(channels)},
        results={
            "peaks": rows,
            "fractions": [
                {"start": start, "end": end, "label": label} for start, end, label in fractions
            ],
            "meta": parsed.get("meta", {}),
        },
        analysis_version=akta.AKTA_ANALYSIS_VERSION,
        value=float(largest) if largest is not None else None,
        unit="mAU*mL" if largest is not None else None,
        candidate_id=candidate_id,
    )
    return row, {
        "channel": chosen,
        "channels_available": sorted(channels),
        "peak_count": len(rows),
        "peaks": rows,
        "unit": channels[chosen].unit,
        "trace": _decimate(channels[chosen].vols, channels[chosen].amps),
        "fractions": [
            {"start": start, "end": end, "label": label} for start, end, label in fractions
        ],
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
    plate = calculators.parse_tecan_xlsx(_read(artifact))
    wells = plate.get("wells") or {}
    if not wells:
        raise DomainError(
            "enzyme_no_wells", "That workbook contained no readable wells.", status_code=422
        )

    corrected, background = calculators.sub_blank(wells, enabled=subtract_background)
    fits = {
        name: calculators.fit_kinetics(data.get("times") or [], data.get("od") or [])
        for name, data in corrected.items()
    }
    slopes = [fit["slope"] for fit in fits.values() if fit.get("slope") is not None]

    row = _record(
        session,
        project_id=project_id,
        user_id=user_id,
        artifact=artifact,
        experiment_type="enzyme_activity",
        params={
            "subtract_background": subtract_background,
            "well_count": len(wells),
            "meta": plate.get("meta", {}),
        },
        results={
            "fits": fits,
            "background_subtracted": background is not None,
        },
        # Enzyme fitting lives in calculators, which has no version constant of
        # its own; the kernels were ported together, so BLI's stands for the set.
        analysis_version=f"calculators/{bli.BLI_ANALYSIS_VERSION}",
        value=max(slopes) if slopes else None,
        unit="dOD/min" if slopes else None,
        candidate_id=candidate_id,
    )
    return row, {
        "well_count": len(wells),
        "fits": fits,
        "background_subtracted": background is not None,
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
    from ..candidates.models import CandidateMetric

    if result.candidate_id is None or result.value is None:
        return None
    mapping = MEASURED_METRICS.get(result.experiment_type)
    if mapping is None:
        return None
    metric_key, unit = mapping

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
        context={"analysis_version": result.result_metadata.get("analysis_version", "")},
        source_experiment_result_id=result.id,
    )
    session.add(metric)
    session.flush()
    return metric
