from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast


class RehearsalMismatch(ValueError):
    pass


def _stable_projection(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_fingerprint": report.get("source_fingerprint"),
        "tables": report.get("tables"),
        "id_map_digest": report.get("id_map_digest"),
        "file_checksums_digest": report.get("file_checksums_digest"),
        "file_checksums": report.get("file_checksums"),
        "rejections": report.get("rejections"),
        "rejection_summary": report.get("rejection_summary"),
        "files_verified": report.get("files", {}).get("verified"),
        "files_missing": report.get("files", {}).get("missing"),
    }


def validate_reports(
    reports: list[dict[str, Any]],
    *,
    expected_tables: dict[str, int] | None = None,
    expected_verified: int | None = None,
) -> dict[str, Any]:
    if len(reports) != 3:
        raise RehearsalMismatch("exactly three migration rehearsal reports are required")
    rehearsal_values = [report.get("rehearsal") for report in reports]
    if not all(isinstance(value, int) for value in rehearsal_values):
        raise RehearsalMismatch("every report must contain an integer rehearsal number")
    rehearsals = sorted(cast(int, value) for value in rehearsal_values)
    if rehearsals != [1, 2, 3]:
        raise RehearsalMismatch(f"expected rehearsal numbers 1, 2, 3; got {rehearsals}")
    baseline = _stable_projection(reports[0])
    if not baseline["source_fingerprint"] or not baseline["id_map_digest"]:
        raise RehearsalMismatch("source fingerprint and ID-map digest are required")
    if not baseline["file_checksums_digest"]:
        raise RehearsalMismatch("file checksum digest is required")
    for report in reports[1:]:
        if _stable_projection(report) != baseline:
            raise RehearsalMismatch(
                f"rehearsal {report.get('rehearsal')} differs from the baseline row, ID, or checksum map"
            )
    if baseline["rejections"]:
        raise RehearsalMismatch("migration contains rejected source records")
    if baseline["files_missing"] != 0:
        raise RehearsalMismatch("migration contains missing files")
    for table, counts in (baseline["tables"] or {}).items():
        explained = counts.get("migrated", 0) + counts.get("deferred", 0) + counts.get("rejected", 0)
        if counts.get("source", 0) != explained:
            raise RehearsalMismatch(f"source rows are unexplained for table {table}")
    for table, expected in (expected_tables or {}).items():
        actual = (baseline["tables"] or {}).get(table, {}).get("source")
        if actual != expected:
            raise RehearsalMismatch(f"expected {table} source count {expected}, got {actual}")
    if expected_verified is not None and baseline["files_verified"] != expected_verified:
        raise RehearsalMismatch(
            f"expected {expected_verified} verified files, got {baseline['files_verified']}"
        )
    return {
        "status": "passed",
        "source_fingerprint": baseline["source_fingerprint"],
        "id_map_digest": baseline["id_map_digest"],
        "file_checksums_digest": baseline["file_checksums_digest"],
        "verified_files": baseline["files_verified"],
        "id_map_entries": len(reports[0].get("id_map", {})),
        "rejections": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate three deterministic BDA v2 migration rehearsals")
    parser.add_argument("reports", type=Path, nargs=3)
    parser.add_argument(
        "--expect-table",
        action="append",
        default=[],
        metavar="TABLE=COUNT",
        help="Require a source row count; repeat for multiple tables",
    )
    parser.add_argument("--expect-verified", type=int)
    args = parser.parse_args()
    expected_tables: dict[str, int] = {}
    for raw in args.expect_table:
        table, separator, count = raw.partition("=")
        if not separator or not table:
            parser.error(f"invalid --expect-table value: {raw}")
        expected_tables[table] = int(count)
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in args.reports]
    result = validate_reports(
        reports,
        expected_tables=expected_tables,
        expected_verified=args.expect_verified,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
