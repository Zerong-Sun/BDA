"""Deterministic, side-effect-free result screening and bundle subsetting."""

from __future__ import annotations

import csv
import io
import json
import math
import operator
import re
import zipfile
from pathlib import PurePosixPath

from .gate_schemas import GatePolicy

OPS = {
    "gt": operator.gt,
    "gte": operator.ge,
    "lt": operator.lt,
    "lte": operator.le,
    "eq": operator.eq,
    "ne": operator.ne,
}


def evaluate(records: list[dict], policy: GatePolicy) -> list[dict]:
    decisions = []
    for row in sorted(records, key=lambda r: r["id"]):
        metrics = row.get("metrics", {})
        reasons, outcomes = [], []
        missing = False
        for rule in policy.rules.conditions:
            value = metrics.get(rule.metric)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                reasons.append(f"missing_metric:{rule.metric}")
                missing = True
                outcomes.append(False)
            else:
                passed = OPS[rule.op](value, rule.value)
                outcomes.append(passed)
                if not passed:
                    reasons.append(f"{rule.metric}={value} {rule.op} {rule.value}: rejected")
        passed = (all(outcomes) if policy.rules.operator == "and" else any(outcomes)) if outcomes else True
        if policy.structure:
            metric, minimum = {
                "multi_helix": ("helix_count", policy.structure.min_helices),
                "structured": ("structured_residue_count", 1),
                "beta_sheet": ("strand_count", policy.structure.min_strands),
            }[policy.structure.preset]
            count = metrics.get(metric)
            if count is None:
                missing = True
                reasons.append(f"missing_metric:{metric}")
            elif count < minimum:
                passed = False
                reasons.append(f"{metric}={count} < {minimum}")
        sort_key = policy.rules.sort_metric
        if sort_key and (
            not isinstance(metrics.get(sort_key), (int, float))
            or isinstance(metrics.get(sort_key), bool)
            or not math.isfinite(metrics[sort_key])
        ):
            missing = True
            reasons.append(f"missing_metric:{sort_key}")
        if row.get("error"):
            missing = True
            reasons.append(row["error"])
        decisions.append(
            {
                "id": row["id"],
                "passed": passed and not missing,
                "reasons": reasons if not passed or missing else [],
                "metrics": metrics,
                "needs_attention": bool(row.get("needs_attention")),
            }
        )
    eligible = [r for r in decisions if r["passed"]]
    if policy.rules.sort_metric:
        key = policy.rules.sort_metric
        eligible.sort(key=lambda r: ((-1 if policy.rules.descending else 1) * r["metrics"][key], r["id"]))
    if policy.rules.top_n is not None:
        keep = {r["id"] for r in eligible[: policy.rules.top_n]}
        for row in eligible:
            if row["id"] not in keep:
                row.update(passed=False, reasons=["outside_top_n"])
    return decisions


def records_in_file(filename: str, data: bytes) -> list[dict]:
    """Each selector is later applied to the original bytes, never an approximate match."""
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix in {".pdb", ".cif", ".mmcif"}:
        return [{"key": PurePosixPath(filename).stem, "format": "whole"}]
    if suffix in {".fa", ".fasta", ".faa", ".fas"}:
        rows = []
        for block in data.decode().split(">"):
            if not block.strip():
                continue
            lines = block.splitlines()
            key = fasta_key(filename, lines[0])
            scores = {}
            for metric, raw in re.findall(r"(?:^|,)\s*([A-Za-z_]+)=([^,\s]+)", lines[0]):
                try:
                    number = float(raw)
                    if math.isfinite(number):
                        scores[metric] = number
                except ValueError:
                    pass
            rows.append(
                {
                    "key": key,
                    "format": "fasta",
                    "metrics": scores,
                    "sequence": "".join(lines[1:]).replace(" ", ""),
                    "native": "sample" not in scores and "sample=" in data.decode(),
                }
            )
        _unique(rows)
        return rows
    if suffix in {".csv", ".tsv", ".jsonl"}:
        source = (
            [json.loads(line) for line in data.decode().splitlines() if line.strip()]
            if suffix == ".jsonl"
            else list(csv.DictReader(io.StringIO(data.decode()), delimiter="\t" if suffix == ".tsv" else ","))
        )
        rows = []
        for row in source:
            key_field = next(
                (k for k in ("result_id", "candidate_key", "candidate_id", "id", "name") if row.get(k) is not None),
                None,
            )
            if key_field is None:
                raise ValueError("tabular_result_id_missing")
            metrics = {}
            for k, v in row.items():
                if k != key_field:
                    try:
                        number = float(v)
                        if math.isfinite(number):
                            metrics[k] = number
                    except (TypeError, ValueError):
                        pass
            rows.append(
                {
                    "key": str(row[key_field]),
                    "key_field": key_field,
                    "format": suffix[1:],
                    "metrics": metrics,
                    "sequence": row.get("sequence"),
                }
            )
        _unique(rows)
        return rows
    if suffix == ".zip":
        rows = []
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(i.file_size for i in archive.infolist()) > 64 * 1024 * 1024 or len(archive.infolist()) > 100000:
                raise ValueError("archive_too_large")
            for info in archive.infolist():
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in info.filename:
                    raise ValueError("archive_path_invalid")
                if info.is_dir():
                    continue
                if path.suffix.lower() == ".zip":
                    raise ValueError("nested_archive_unsupported")
                for item in records_in_file(info.filename, archive.read(info)):
                    rows.append(
                        {
                            **item,
                            "member": info.filename,
                            "member_key": item["key"],
                            "key": f"{info.filename}:{item['key']}",
                        }
                    )
        _unique(rows)
        return rows
    raise ValueError(f"result_format_not_splittable:{suffix}")


def _unique(rows):
    if len({r["key"] for r in rows}) != len(rows):
        raise ValueError("duplicate_result_id_in_file")


def subset_file(filename: str, data: bytes, selectors: list[dict]) -> bytes:
    """Create a physical subset, including when selected records share one source file."""
    if not selectors:
        raise ValueError("empty_subset")
    original = records_in_file(filename, data)
    available = {r["key"] for r in original}
    keys = {r["key"] for r in selectors}
    if not keys <= available:
        raise ValueError("selected_result_missing")
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix == ".zip":
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
            for member in sorted({s["member"] for s in selectors}):
                chosen = [{**s, "key": s["member_key"]} for s in selectors if s["member"] == member]
                target.writestr(member, subset_file(member, source.read(member), chosen))
        return output.getvalue()
    if suffix in {".pdb", ".cif", ".mmcif"}:
        return data
    if suffix in {".fa", ".fasta", ".faa", ".fas"}:
        return "".join(
            ">" + block.rstrip() + "\n"
            for block in data.decode().split(">")
            if block.strip() and fasta_key(filename, block.splitlines()[0]) in keys
        ).encode()
    key_field = selectors[0]["key_field"]
    if suffix == ".jsonl":
        return "".join(
            line + "\n"
            for line in data.decode().splitlines()
            if line.strip() and str(json.loads(line).get(key_field)) in keys
        ).encode()
    delimiter = "\t" if suffix == ".tsv" else ","
    reader = csv.DictReader(io.StringIO(data.decode()), delimiter=delimiter)
    table_output = io.StringIO()
    writer = csv.DictWriter(table_output, fieldnames=reader.fieldnames or [], delimiter=delimiter)
    writer.writeheader()
    writer.writerows(row for row in reader if str(row.get(key_field)) in keys)
    return table_output.getvalue().encode()


def fasta_key(filename: str, header: str) -> str:
    sample = re.search(r"(?:^|,)\s*sample=(\d+)(?:,|\s|$)", header)
    return f"{PurePosixPath(filename).stem}_sample{sample.group(1)}" if sample else header.split()[0]
