#!/usr/bin/env python3
"""Fail-closed completeness guard for the accepted 2026-08-29 Qiming snapshot."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

CONDITIONS = {
    "output_with_templates": "native_with_templates",
    "output_msa_only": "native_msa_only",
}
LIGANDS = {"thc", "cbd", "chol", "stearate"}
SEEDS = {1, 333, 55555}
SEED_DIR_RE = re.compile(r"^seed-(?P<seed>[0-9]+)_sample-0$")


def sidecars(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("._*"))


def exact_files(root: Path, suffix: str) -> list[Path]:
    return sorted(path for path in root.rglob(f"*{suffix}") if not path.name.startswith("._"))


def validate_af3(root: Path) -> dict[str, Any]:
    found: set[tuple[str, str, int]] = set()
    errors: list[str] = []
    extra_parent_summaries = 0
    for directory, prefix in CONDITIONS.items():
        condition_root = root / directory
        if not condition_root.is_dir():
            errors.append(f"missing condition directory: {directory}")
            continue
        for ligand in sorted(LIGANDS):
            ligand_root = condition_root / f"{prefix}__{ligand}"
            if not ligand_root.is_dir():
                errors.append(f"missing ligand directory: {ligand_root.name}")
                continue
            parent_summaries = list(ligand_root.glob("*_summary_confidences.json"))
            extra_parent_summaries += len(parent_summaries)
            for seed_dir in sorted(path for path in ligand_root.iterdir() if path.is_dir()):
                match = SEED_DIR_RE.match(seed_dir.name)
                if not match:
                    errors.append(f"unexpected AF3 subdirectory: {seed_dir}")
                    continue
                seed = int(match.group("seed"))
                key = (directory, ligand, seed)
                summaries = list(seed_dir.glob("*_summary_confidences.json"))
                models = list(seed_dir.glob("*_model.cif"))
                confidences = [
                    path
                    for path in seed_dir.glob("*_confidences.json")
                    if not path.name.endswith("_summary_confidences.json")
                ]
                if len(summaries) != 1 or len(models) != 1 or len(confidences) != 1:
                    errors.append(
                        f"{seed_dir}: expected one summary/model/confidences file; got "
                        f"{len(summaries)}/{len(models)}/{len(confidences)}"
                    )
                if key in found:
                    errors.append(f"duplicate AF3 key: {key}")
                found.add(key)
    expected = {
        (condition, ligand, seed)
        for condition in CONDITIONS
        for ligand in LIGANDS
        for seed in SEEDS
    }
    missing = sorted(expected - found)
    unexpected = sorted(found - expected)
    if missing:
        errors.append(f"missing AF3 keys: {missing}")
    if unexpected:
        errors.append(f"unexpected AF3 keys: {unexpected}")
    if len(found) != 24:
        errors.append(f"expected exactly 24 seed predictions, found {len(found)}")
    return {
        "expected_seed_predictions": 24,
        "found_seed_predictions": len(found),
        "parent_aggregate_summaries_ignored": extra_parent_summaries,
        "errors": errors,
    }


def report_keys(path: Path) -> list[str]:
    keys = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        parts = line.split()
        if not parts:
            raise ValueError(f"blank reports line {line_number}")
        keys.append(parts[0])
    return keys


def validate_superfold(root: Path) -> dict[str, Any]:
    out = root / "out"
    errors: list[str] = []
    reports = out / "reports.txt"
    if not reports.is_file():
        return {"errors": ["missing superfold reports.txt"]}
    keys = report_keys(reports)
    key_set = set(keys)
    if len(keys) != 768 or len(key_set) != 768:
        errors.append(f"expected 768 unique report keys; got {len(keys)}/{len(key_set)}")
    pdb_keys = {
        path.name.removesuffix("_model_1_ptm_seed_0_unrelaxed.pdb")
        for path in out.glob("*_model_1_ptm_seed_0_unrelaxed.pdb")
    }
    json_keys = {
        path.name.removesuffix("_model_1_ptm_seed_0_prediction_results.json")
        for path in out.glob("*_model_1_ptm_seed_0_prediction_results.json")
    }
    if pdb_keys != key_set:
        errors.append(f"SuperFold PDB keys do not match reports: missing={len(key_set-pdb_keys)} extra={len(pdb_keys-key_set)}")
    if json_keys != key_set:
        errors.append(f"SuperFold JSON keys do not match reports: missing={len(key_set-json_keys)} extra={len(json_keys-key_set)}")
    return {
        "report_rows": len(keys),
        "unique_report_keys": len(key_set),
        "pdb_files": len(pdb_keys),
        "prediction_json_files": len(json_keys),
        "errors": errors,
    }


def validate_boltz_job(root: Path, expected_models: int) -> dict[str, Any]:
    errors: list[str] = []
    output = root / "output"
    predictions = output / "boltz_results_input" / "predictions"
    pdbs = exact_files(predictions, ".pdb") if predictions.is_dir() else []
    confidences = exact_files(predictions, ".json") if predictions.is_dir() else []
    if len(pdbs) != expected_models:
        errors.append(f"expected {expected_models} PDB files, found {len(pdbs)}")
    if len(confidences) != expected_models:
        errors.append(f"expected {expected_models} confidence JSON files, found {len(confidences)}")
    if not (output / "run_complete").is_file():
        errors.append("missing run_complete")
    return {
        "expected_models": expected_models,
        "pdb_files": len(pdbs),
        "confidence_json_files": len(confidences),
        "run_complete": (output / "run_complete").is_file(),
        "errors": errors,
    }


def validate(snapshot: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": "qm-acceptance-output-guard.v1",
        "snapshot": str(snapshot),
        "macos_sidecars": sidecars(snapshot),
        "af3": validate_af3(snapshot / "af3_native_fabp1_msa"),
        "superfold": validate_superfold(snapshot / "superfold_scale"),
        "sweet_family": validate_boltz_job(snapshot / "fold_r2", 9),
        "neoculin_per_chain": validate_boltz_job(snapshot / "neoculin", 9),
        "neoculin_fused": validate_boltz_job(snapshot / "neoculin_fused", 3),
    }
    errors = []
    if result["macos_sidecars"]:
        errors.append(f"found {len(result['macos_sidecars'])} macOS ._* sidecars")
    for section in ("af3", "superfold", "sweet_family", "neoculin_per_chain", "neoculin_fused"):
        errors.extend(f"{section}: {error}" for error in result[section]["errors"])
    result["errors"] = errors
    result["pass"] = not errors
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = validate(args.snapshot)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered)
    print(rendered, end="")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
