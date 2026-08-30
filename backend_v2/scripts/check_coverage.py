"""Enforce the total and core-package coverage gates.

One caveat is worth stating rather than rediscovering: several of the covering tests are
gated on ``BDA_V2_RUN_DB_TESTS=1`` and a live PostgreSQL, and they skip by default. CI
sets both, so CI's numbers are the real ones. On a developer machine without a database
the same command reports a *lower* figure and can fail a gate that is green in CI -
``research/package_import.py`` is the usual victim, since ``test_database_flow.py``
covers it. That is a false alarm, so it is labelled as one instead of being silently
absorbed or silently trusted.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

CORE_THRESHOLDS = {
    "backend_v2/app/identity/service.py": 95.0,
    "backend_v2/app/identity/deps.py": 95.0,
    "backend_v2/app/compute/service.py": 95.0,
    "backend_v2/app/artifacts/service.py": 95.0,
    "backend_v2/app/research/package_import.py": 95.0,
    "backend_v2/app/research/package_validation.py": 95.0,
    "backend_v2/app/migration/": 95.0,
}


def combined_percentage(files: dict, prefix: str) -> float:
    selected = [summary["summary"] for name, summary in files.items() if name.startswith(prefix)]
    statements = sum(item["num_statements"] for item in selected)
    covered = sum(item["covered_lines"] for item in selected)
    return 100.0 if statements == 0 else covered * 100.0 / statements


def db_tests_ran() -> bool:
    """Whether the PostgreSQL-gated tests were part of this run."""
    return os.environ.get("BDA_V2_RUN_DB_TESTS") == "1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce BDA v2 total and core-package coverage gates")
    parser.add_argument("coverage_json", type=Path)
    args = parser.parse_args()
    data = json.loads(args.coverage_json.read_text())
    failures: list[str] = []
    total = float(data["totals"]["percent_covered"])
    if total < 85.0:
        failures.append(f"overall coverage {total:.2f}% is below 85.00%")
    for prefix, threshold in CORE_THRESHOLDS.items():
        actual = combined_percentage(data["files"], prefix)
        if actual < threshold:
            failures.append(f"{prefix} coverage {actual:.2f}% is below {threshold:.2f}%")
    if failures:
        print("\n".join(failures))
        if not db_tests_ran():
            print(
                "\nNote: BDA_V2_RUN_DB_TESTS is not 1, so the PostgreSQL-gated tests were "
                "skipped and these percentages are lower than CI's. Before treating this "
                "as a real regression, re-run with a database:\n"
                "    BDA_V2_RUN_DB_TESTS=1 BDA_V2_DATABASE_URL=... pytest backend_v2/tests --cov=backend_v2/app ..."
            )
        return 1
    scope = "" if db_tests_ran() else " (database-gated tests skipped; CI's figure is higher)"
    print(f"coverage gates passed: overall={total:.2f}%{scope}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
