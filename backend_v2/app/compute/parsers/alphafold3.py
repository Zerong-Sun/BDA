"""Read AlphaFold 3 confidences into candidate metrics.

The platform has been collecting these files for as long as AF3 has been
registered - `0028_superfold_af3_real_runs` sets the output port glob to
``*summary_confidences.json`` - and nothing read them. The numbers that decide
whether a predicted complex is worth believing were sitting in object storage
as an artifact nobody could query, while `candidate_metrics` already had a
normalised vocabulary waiting for them.

The output shape is the one this repository already validates in
``scripts/validate_qm_acceptance_outputs.py``: each job directory holds one
``<job>_summary_confidences.json`` at the top level and one per seed in
``seed-<N>_sample-<M>/``, beside ``<job>_model.cif`` and a fuller
``<job>_confidences.json``.

Three decisions worth stating.

**Every seed is its own metric row.** AF3 is run across several seeds and
samples, and the spread between them is the informative part; averaging here
would destroy the only evidence that a prediction is unstable. The seed
directory becomes ``model_variant``, exactly as superfold's model/seed does.

**The top-level summary is skipped when seeds are present.** AF3 writes a copy
of the best sample's numbers at the job root. Counting it as well would record
one prediction twice and quietly bias any average taken downstream.

**`assessor="independent_model"`.** AF3 scoring an RFdiffusion or BindCraft
design is a separate model's opinion, which is what `0030_candidate_metric_assessor`
introduced the column to distinguish. A design model's own confidence is
self-assessment; this is not that, and the difference should survive into the
row rather than being reconstructed later from the method name.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import PurePosixPath
from typing import Any

from .base import ParseContext, ParsedCandidate, ParsedMetric, ParsedOutputs, register_parser

METHOD = "alphafold3"
SUMMARY_SUFFIX = "_summary_confidences.json"

#: ``seed-1_sample-0`` - AF3's own directory naming for one prediction.
_SEED_DIR = re.compile(r"^seed-(?P<seed>\d+)_sample-(?P<sample>\d+)$")

#: AF3's field names on the left, the platform's normalised metric keys on the
#: right. `iptm` and `ptm` are the two a person actually gates on; the rest are
#: kept because they explain a bad number - a high-ipTM prediction that also
#: reports a clash is not the same finding as a clean one.
_METRICS: dict[str, tuple[str, str]] = {
    "iptm": ("iptm", ""),
    "ptm": ("ptm", ""),
    "ranking_score": ("ranking_score", ""),
    "fraction_disordered": ("fraction_disordered", ""),
}


def _finite(value: object) -> float | None:
    """A usable number, or None. Booleans are not numbers here."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


#: Suffixes AF3 appends to the job name. Stripping one of these is how a file
#: is traced back to its prediction; the directory cannot be trusted for that,
#: because a per-seed file sits one level below the job.
_FILE_SUFFIXES = (SUMMARY_SUFFIX, "_confidences.json", "_model.cif.gz", "_model.cif", "_data.json")


def _job_name(path: PurePosixPath) -> str:
    """The prediction this file belongs to.

    Taken from the filename first, because every file AF3 writes is prefixed
    with the job name and only *some* of them sit in the job's own directory:
    a model inside ``seed-1_sample-0/`` has that seed directory as its parent,
    so falling back to the parent would name the candidate after the seed.

    AF3 lowercases the directory it writes, so the job name as submitted and
    the name on disk differ in case. The name on disk is what every file in the
    run agrees on, so that is what identifies the candidate.
    """
    name = path.name
    for suffix in _FILE_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    parent = path.parent
    # An unrecognised filename: use the job directory, stepping over a seed one.
    return parent.parent.name if _SEED_DIR.match(parent.name) else parent.name


def _variant(path: PurePosixPath) -> str:
    match = _SEED_DIR.match(path.parent.name)
    return match.group(0) if match else ""


@register_parser(METHOD)
def parse(ctx: ParseContext) -> ParsedOutputs:
    summaries = [
        item
        for item in ctx.outputs
        if str(item.get("filename") or "").endswith(SUMMARY_SUFFIX)
    ]
    if not summaries:
        return ParsedOutputs(
            warnings=[f"no {SUMMARY_SUFFIX} among the collected outputs; nothing scored"]
        )

    # A job that produced per-seed directories also writes a copy at its root.
    # Counting both would record one prediction twice.
    seeded = {
        _job_name(PurePosixPath(str(item.get("filename") or "")))
        for item in summaries
        if _variant(PurePosixPath(str(item.get("filename") or "")))
    }

    structures = {
        (
            _job_name(PurePosixPath(str(item.get("filename") or ""))),
            _variant(PurePosixPath(str(item.get("filename") or ""))),
        ): index
        for index, item in enumerate(ctx.outputs)
        if str(item.get("filename") or "").endswith((".cif", ".cif.gz"))
    }

    by_job: dict[str, list[ParsedMetric]] = {}
    structure_for: dict[str, int] = {}
    warnings: list[str] = []

    for item in summaries:
        path = PurePosixPath(str(item.get("filename") or ""))
        job, variant = _job_name(path), _variant(path)
        if not variant and job in seeded:
            continue
        try:
            payload: Any = json.loads(ctx.read_bytes(str(item["object_key"])).decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError, KeyError, OSError) as exc:
            warnings.append(f"{path.name}: unreadable ({type(exc).__name__})")
            continue
        if not isinstance(payload, dict):
            warnings.append(f"{path.name}: expected a JSON object")
            continue

        context: dict[str, Any] = {"source": path.name}
        match = _SEED_DIR.match(path.parent.name)
        if match:
            context["seed"] = int(match.group("seed"))
            context["sample"] = int(match.group("sample"))
        # Reported rather than folded into a score: a clash makes every other
        # number on this prediction mean something different.
        if isinstance(payload.get("has_clash"), (bool, int, float)):
            context["has_clash"] = bool(payload["has_clash"])

        metrics = by_job.setdefault(job, [])
        for source, (key, unit) in _METRICS.items():
            value = _finite(payload.get(source))
            if value is None:
                continue
            metrics.append(
                ParsedMetric(
                    key=key,
                    value=value,
                    method=METHOD,
                    model_variant=variant,
                    evidence_kind="predicted",
                    assessor="independent_model",
                    unit=unit,
                    context=context,
                )
            )
        index = structures.get((job, variant))
        if index is not None:
            structure_for.setdefault(job, index)

    candidates: list[ParsedCandidate] = []
    for job, metrics in sorted(by_job.items()):
        if not metrics:
            warnings.append(f"{job}: summary held no finite confidence values")
            continue
        iptm = [metric.value for metric in metrics if metric.key == "iptm"]
        ptm = [metric.value for metric in metrics if metric.key == "ptm"]
        scores: dict[str, float] = {}
        if iptm:
            scores["iptm"] = max(iptm)
            # The worst seed, kept beside the best: a complex only one seed
            # likes is a different finding from one every seed likes.
            scores["iptm_min"] = min(iptm)
        if ptm:
            scores["ptm"] = max(ptm)
        candidates.append(
            ParsedCandidate(
                candidate_key=job,
                name=job,
                status="generated",
                # Ranked on the worst seed, for the reason above.
                score=min(iptm) if iptm else None,
                scores=scores,
                properties={
                    "predicted_by": METHOD,
                    "seed_count": len({metric.model_variant for metric in metrics if metric.model_variant}),
                },
                complex_output_index=structure_for.get(job),
                metrics=metrics,
            )
        )

    ordered = sorted(range(len(candidates)), key=lambda i: -(candidates[i].score or 0.0))
    candidates = [
        ParsedCandidate(**{**candidates[position].__dict__, "rank": rank + 1})
        for rank, position in enumerate(ordered)
    ]
    return ParsedOutputs(candidates=candidates, warnings=warnings)
