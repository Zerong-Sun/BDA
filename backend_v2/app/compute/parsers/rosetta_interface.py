"""Associate BDA Rosetta interface scores with the exact scored coordinates.

Only checksum-linked interface rows are routable. A filename or a primary Relax
score alone cannot stand in for interface evidence. Original files are retained.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
from pathlib import PurePosixPath

from .base import ParseContext, ParsedCandidate, ParsedMetric, ParsedOutputs, register_parser

METRICS = {"dG_separated", "dSASA_int", "sc_value", "packstat", "total_score"}


@register_parser("rosetta_interface")
def parse(ctx: ParseContext) -> ParsedOutputs:
    structures: dict[str, list[int]] = {}
    warnings: list[str] = []
    for index, output in enumerate(ctx.outputs):
        if str(output.get("filename", "")).lower().endswith(".pdb"):
            checksum = hashlib.sha256(ctx.read_bytes(output["object_key"])).hexdigest()
            structures.setdefault(checksum, []).append(index)
    rows: dict[str, list[dict]] = {}
    for output in ctx.outputs:
        if PurePosixPath(output.get("filename", "")).name != "scores.csv":
            continue
        for row in csv.DictReader(io.StringIO(ctx.read_bytes(output["object_key"]).decode("utf-8-sig"))):
            if row.get("stage") == "interface" and row.get("scored_structure_sha256"):
                rows.setdefault(row["scored_structure_sha256"], []).append(row)
    candidates = []
    for checksum, indices in structures.items():
        matches = rows.get(checksum, [])
        if len(indices) != 1 or len(matches) != 1:
            warnings.append(f"{checksum}: interface_structure_match_not_unique")
            continue
        scores = {}
        for key in METRICS:
            try:
                value = float(matches[0].get(key, ""))
                if math.isfinite(value):
                    scores[key] = value
            except (ValueError, TypeError):
                pass
        if "dG_separated" not in scores:
            warnings.append(f"{checksum}: interface_energy_missing")
            continue
        condition = f"{ctx.parameters.get('interface', '')}:{ctx.parameters.get('score_weights', '')}"
        candidates.append(
            ParsedCandidate(
                candidate_key=f"rosetta_{checksum}",
                name=PurePosixPath(ctx.outputs[indices[0]]["filename"]).name,
                scores=scores,
                score=scores["dG_separated"],
                structure_output_index=indices[0],
                properties={"structure_sha256": checksum, "scoring_condition": condition},
                metrics=[
                    ParsedMetric(
                        key=k,
                        value=v,
                        method="rosetta_interface",
                        condition=condition,
                        unit="REU" if k in {"dG_separated", "total_score"} else "",
                        context={"scored_structure_sha256": checksum, "stage": "interface"},
                    )
                    for k, v in scores.items()
                ],
            )
        )
    return ParsedOutputs(candidates=candidates, warnings=warnings)
