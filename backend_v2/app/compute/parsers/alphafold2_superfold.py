"""Read AlphaFold2 (superfold) predictions into candidate metrics.

superfold writes one directory per folded sequence, holding the predicted structure and
a ``*_prediction_results.json`` carrying the confidence numbers. Those numbers are the
point of the run - they decide which designs survive - so they are reported as metrics
rather than being flattened into an opaque score blob.

Two details of the real output shape matter:

* The JSON contains bare ``NaN``. That is not valid JSON, and ``mean_pae_interaction``
  is ``NaN`` for every monomer fold, so a strict reader fails on ordinary output.
* The prediction filenames carry the model and seed, and superfold is normally run
  across several models per sequence. Each is kept as its own metric row rather than
  being averaged away, because disagreement between models is itself informative.

Candidate keys are the design name, so folding a sequence ProteinMPNN already
registered attaches confidence to that design instead of creating a second one.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import PurePosixPath

from .base import ParseContext, ParsedCandidate, ParsedMetric, ParsedOutputs, register_parser

METHOD = "alphafold2_superfold"
RESULTS_SUFFIX = "_prediction_results.json"

# "<design>_model_4_ptm_seed_0_prediction_results.json" -> design, variant.
_VARIANT = re.compile(r"^(?P<design>.+?)_(?P<variant>model_[^_]+_.*?_seed_\d+)" + re.escape(RESULTS_SUFFIX) + r"$")

# Reported under superfold's own names; stored under names shared across methods so a
# query can filter on "plddt" without knowing which tool produced it.
_METRICS = {
    "mean_plddt": ("plddt", ""),
    "pTMscore": ("ptm", ""),
    "mean_pae": ("pae", "angstrom"),
    "mean_pae_interaction": ("pae_interaction", "angstrom"),
    "mean_pae_intra_chain": ("pae_intra_chain", "angstrom"),
}


def _finite(value: object) -> float | None:
    """A usable number, or None for NaN/inf/non-numeric.

    ``mean_pae_interaction`` is NaN on every monomer fold; storing that would make the
    metric unqueryable and imply an interface score exists where none was computed.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


@register_parser(METHOD)
def parse(ctx: ParseContext) -> ParsedOutputs:
    results = [
        item
        for item in ctx.outputs
        if PurePosixPath(str(item.get("filename") or "")).name.endswith(RESULTS_SUFFIX)
    ]
    if not results:
        return ParsedOutputs(warnings=[f"no {RESULTS_SUFFIX} among the collected outputs; nothing scored"])

    structures = {
        PurePosixPath(str(item.get("filename") or "")).name: index
        for index, item in enumerate(ctx.outputs)
        if str(item.get("filename") or "").lower().endswith(".pdb")
    }

    by_design: dict[str, list[ParsedMetric]] = {}
    structure_for: dict[str, int] = {}
    warnings: list[str] = []

    for item in results:
        filename = PurePosixPath(str(item.get("filename") or "")).name
        match = _VARIANT.match(filename)
        if match is None:
            warnings.append(f"{filename}: unrecognised superfold result filename, skipped")
            continue
        design, variant = match.group("design"), match.group("variant")

        try:
            # NaN is accepted deliberately - see the module docstring - and filtered per
            # metric below rather than rejecting the whole file.
            payload = json.loads(ctx.read_bytes(str(item["object_key"])).decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError, KeyError, OSError) as exc:
            warnings.append(f"{filename}: unreadable ({type(exc).__name__})")
            continue
        if not isinstance(payload, dict):
            warnings.append(f"{filename}: expected a JSON object")
            continue

        context = {
            key: payload[key]
            for key in ("recycles", "tol", "model", "seed", "type", "elapsed_time")
            if key in payload
        }
        metrics = by_design.setdefault(design, [])
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
                    unit=unit,
                    context=context,
                )
            )

        # The unrelaxed prediction sits beside its results file under the same stem.
        index = structures.get(f"{design}_{variant}_unrelaxed.pdb")
        if index is not None:
            structure_for.setdefault(design, index)

    candidates: list[ParsedCandidate] = []
    for design, metrics in by_design.items():
        if not metrics:
            warnings.append(f"{design}: prediction produced no finite confidence values")
            continue
        plddt = [m.value for m in metrics if m.key == "plddt"]
        ptm = [m.value for m in metrics if m.key == "ptm"]
        # Rank on the worst model rather than the best: a design only one model likes is
        # not a design worth carrying forward.
        score = min(plddt) if plddt else None
        scores = {}
        if plddt:
            scores["plddt"] = max(plddt)
            scores["plddt_min"] = min(plddt)
        if ptm:
            scores["ptm"] = max(ptm)
        candidates.append(
            ParsedCandidate(
                candidate_key=design,
                name=design,
                status="generated",
                score=score,
                scores=scores,
                properties={"folded_by": METHOD, "model_count": len({m.model_variant for m in metrics})},
                structure_output_index=structure_for.get(design),
                metrics=metrics,
            )
        )

    ordered = sorted(range(len(candidates)), key=lambda i: -(candidates[i].score or 0.0))
    candidates = [
        ParsedCandidate(**{**candidates[position].__dict__, "rank": rank + 1})
        for rank, position in enumerate(ordered)
    ]
    return ParsedOutputs(candidates=candidates, warnings=warnings)
