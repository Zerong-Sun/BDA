"""Read ProteinHunter (Boltz) run summaries into candidates.

ProteinHunter writes a CSV summarising every design it produced — one row per run and
cycle — alongside the complex PDB and the Boltz YAML that generated it. This parser turns
those rows into candidates carrying their confidence metrics, so the platform reads the
model's native output instead of requiring the wrapper to emit BDA-shaped JSON.

ipTM, pLDDT and ipLDDT are computational predictions, never experimental evidence. They
are recorded as scores so that downstream review weighs them as such.
"""

from __future__ import annotations

import csv
import io
from pathlib import PurePosixPath

from .base import ParseContext, ParsedCandidate, ParsedMetric, ParsedOutputs, register_parser

# The high-confidence summary is the one that decides what becomes a candidate; the
# all-runs summary is kept as an artifact but does not promote anything.
HIGH_CONFIDENCE_SUMMARY = "summary_high_iptm.csv"
ALL_RUNS_SUMMARY = "summary_all_runs.csv"

REQUIRED_COLUMNS = frozenset({"run_id", "cycle", "pdb_filename", "iptm"})


def _number(row: dict, key: str) -> float | None:
    raw = (row.get(key) or "").strip()
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _integer(row: dict, key: str) -> int | None:
    value = _number(row, key)
    return int(value) if value is not None else None


def _condition(parameters: dict) -> str:
    """The target these confidences are about.

    Recorded on every metric because the same design is legitimately scored against
    several ligands - a target and its negative controls - and those numbers only mean
    something next to each other. Without it they overwrite one another.
    """
    ccd = str(parameters.get("ligand_ccd") or "").strip()
    if ccd:
        return f"ligand:{ccd}"
    smiles = str(parameters.get("ligand_smiles") or "").strip()
    if smiles:
        return f"ligand_smiles:{smiles[:100]}"
    proteins = str(parameters.get("protein_seqs") or "").strip()
    if proteins:
        return "protein_target"
    return ""


@register_parser("proteinhunter_boltz")
def parse(ctx: ParseContext) -> ParsedOutputs:
    summaries = [
        item
        for item in ctx.outputs
        if PurePosixPath(str(item.get("filename") or "")).name == HIGH_CONFIDENCE_SUMMARY
    ]
    if not summaries:
        return ParsedOutputs(
            warnings=[f"no {HIGH_CONFIDENCE_SUMMARY} among the collected outputs; no candidates promoted"]
        )

    # Index the collected PDBs so a candidate can point at its own structure artifact.
    structure_index = {
        PurePosixPath(str(item.get("filename") or "")).name: index
        for index, item in enumerate(ctx.outputs)
        if str(item.get("filename") or "").lower().endswith(".pdb")
    }

    candidates: list[ParsedCandidate] = []
    warnings: list[str] = []
    seen: set[str] = set()

    for summary in summaries:
        try:
            text = ctx.read_bytes(str(summary["object_key"])).decode("utf-8-sig")
        except (UnicodeDecodeError, KeyError, OSError) as exc:
            warnings.append(f"{summary.get('filename')}: unreadable ({type(exc).__name__})")
            continue

        reader = csv.DictReader(io.StringIO(text))
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            warnings.append(f"{summary.get('filename')}: missing column(s) {sorted(missing)}")
            continue

        for position, row in enumerate(reader, start=2):  # row 1 is the header
            pdb_name = PurePosixPath((row.get("pdb_filename") or "").strip()).name
            run_id, cycle = _integer(row, "run_id"), _integer(row, "cycle")
            iptm = _number(row, "iptm")
            if not pdb_name or run_id is None or cycle is None:
                warnings.append(f"{summary.get('filename')} row {position}: incomplete, skipped")
                continue

            # Stable across retries of the same job, so a re-collection updates rather
            # than duplicating.
            candidate_key = f"proteinhunter-{ctx.job_id}-run{run_id}-cycle{cycle}"
            if candidate_key in seen:
                continue
            seen.add(candidate_key)

            scores = {
                name: value
                for name, value in (
                    ("iptm", iptm),
                    ("plddt", _number(row, "plddt")),
                    ("iplddt", _number(row, "iplddt")),
                )
                if value is not None
            }
            properties: dict = {"run_id": run_id, "cycle": cycle, "pdb_filename": pdb_name}
            sequence = (row.get("sequence") or "").strip()
            if sequence:
                properties["sequence"] = sequence
                properties["length"] = len(sequence)
            alanine = _integer(row, "alanine_count")
            if alanine is not None:
                properties["alanine_count"] = alanine
            yaml_name = PurePosixPath((row.get("yaml_filename") or "").strip()).name
            if yaml_name:
                properties["yaml_filename"] = yaml_name
            if pdb_name not in structure_index:
                warnings.append(f"{pdb_name} is listed in the summary but was not collected")

            # The same numbers as queryable rows. Every one is marked as coming from the
            # design model, because Boltz both produced this structure and scored it -
            # that is self-assessment, and reading it as corroboration is how the wrong
            # candidate gets promoted. An independent re-prediction records its own rows
            # with assessor="independent_model" and the comparison becomes possible.
            condition = _condition(ctx.parameters)
            metrics = [
                ParsedMetric(
                    key=name,
                    value=value,
                    method="boltz2",
                    evidence_kind="predicted",
                    assessor="design_model",
                    condition=condition,
                    context={"run_id": run_id, "cycle": cycle},
                )
                for name, value in scores.items()
            ]

            candidates.append(
                ParsedCandidate(
                    candidate_key=candidate_key,
                    name=f"ProteinHunter run {run_id} cycle {cycle}",
                    status="generated",
                    score=iptm,
                    scores=scores,
                    properties=properties,
                    complex_output_index=structure_index.get(pdb_name),
                    metrics=metrics,
                )
            )

    # Best ipTM first, so rank reflects predicted interface quality.
    ordered = sorted(range(len(candidates)), key=lambda i: -(candidates[i].score or 0.0))
    candidates = [
        ParsedCandidate(**{**candidates[position].__dict__, "rank": rank + 1})
        for rank, position in enumerate(ordered)
    ]
    if not candidates:
        warnings.append("summary contained no usable rows; no candidates promoted")
    return ParsedOutputs(candidates=candidates, warnings=warnings)
