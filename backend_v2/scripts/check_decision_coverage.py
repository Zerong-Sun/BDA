"""Fail the build when a numbered decision has no record, or a record has no decision.

The failure this exists to prevent has already happened once. `D101` in
``docs/sweet_protein_project/DECISIONS.md`` records that cluster submission scripts cite
``D087`` and ``D099`` while ``grep -rE 'D0[89][0-9]'`` finds nothing in the repository:
twenty decisions were made on the cluster and never flowed back. Nothing detected that -
the numbering lived in prose, and prose cannot fail a build.

Three checks, per project, driven by ``contracts/decision-records.yaml`` (JSON content,
like its sibling ``v2-flow-matrix.yaml``):

1. **No dangling record.** A ``decision_ref`` written by a seeder must exist in that
   project's decisions document. A row claiming to be the record of D064 when D064 was
   never written is worse than no row, because a coverage number counts it.
2. **No undeclared gap.** Every hole in the numbering must be declared in the contract
   with the decision that declared it. A declared gap is a known debt; an undeclared one
   is a decision that went missing while nobody was looking.
3. **A ratchet, not a cliff.** Coverage today is 3 of 97, and a check that demanded 97
   would simply be turned off. ``recorded_baseline`` may never go down; when coverage
   improves the checker fails and tells you to raise it, so the number cannot quietly
   drift away from reality in either direction.

The seeders are the source of truth here rather than the database, because CI has no
database and the seeders are what is versioned. They are the thing that would be re-run.

A project whose seeders and document are both missing is skipped, not failed: the
public/private split puts research scripts and decisions documents on the private
side, and this gate must not break the public checkout over records it does not hold.

    PYTHONPATH=. backend_v2/.venv/bin/python backend_v2/scripts/check_decision_coverage.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

#: A row in a decisions table: `| D064 | ... | ... |`. Anchored to the line start so a
#: number mentioned inside another decision's rationale is not mistaken for a definition.
DOC_ID = re.compile(r"^\|\s*(?:\*\*)?([A-Z])(\d{3})(?:\*\*)?\s*\|", re.MULTILINE)

#: `decision_ref="D102"` in a seeder. Single- and double-quoted both, because a seeder is
#: ordinary Python and formatting is not something this check should have an opinion on.
SEEDER_REF = re.compile(r"""decision_ref\s*=\s*["']([A-Z]\d{3})["']""")


def _parse_doc(path: Path, prefix: str) -> tuple[set[int], list[str]]:
    """Decision numbers defined by a document, and anything malformed about them."""
    errors: list[str] = []
    numbers: list[int] = []
    for letter, digits in DOC_ID.findall(path.read_text(encoding="utf-8")):
        if letter != prefix:
            errors.append(f"{path}: row '{letter}{digits}' does not use this project's prefix {prefix!r}")
            continue
        numbers.append(int(digits))
    duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
    if duplicates:
        errors.append(f"{path}: duplicate decision rows for {', '.join(f'{prefix}{n:03d}' for n in duplicates)}")
    return set(numbers), errors


def _parse_seeders(paths: list[Path], prefix: str) -> tuple[set[int], list[str]]:
    errors: list[str] = []
    seen: dict[int, Path] = {}
    for path in paths:
        if not path.exists():
            errors.append(f"{path}: seeder listed in the contract does not exist")
            continue
        for ref in SEEDER_REF.findall(path.read_text(encoding="utf-8")):
            letter, number = ref[0], int(ref[1:])
            if letter != prefix:
                errors.append(f"{path}: decision_ref {ref!r} does not use this project's prefix {prefix!r}")
                continue
            if number in seen:
                # The database constraint catches this too, but only once someone runs
                # the seeder against a real database - which is exactly when it is most
                # expensive to find out.
                errors.append(f"{path}: {ref} is recorded twice (also in {seen[number]})")
                continue
            seen[number] = path
    return set(seen), errors


def _declared_gap_numbers(project: dict) -> tuple[set[int], list[str]]:
    errors: list[str] = []
    numbers: set[int] = set()
    for gap in project.get("declared_gaps") or []:
        first, last = int(gap["first"]), int(gap["last"])
        if last < first:
            errors.append(f"{project['key']}: declared gap {first}-{last} runs backwards")
            continue
        if not str(gap.get("declared_by", "")).strip():
            errors.append(f"{project['key']}: gap {first}-{last} has no `declared_by`")
        if not str(gap.get("reason", "")).strip():
            # A gap with no stated reason is indistinguishable from a gap nobody noticed,
            # which is the thing this whole check is about.
            errors.append(f"{project['key']}: gap {first}-{last} has no `reason`")
        numbers.update(range(first, last + 1))
    return numbers, errors


def check_project(project: dict, root: Path) -> tuple[list[str], str]:
    """Errors, and one human-readable line about this project's coverage."""
    key, prefix = project["key"], project["prefix"]
    errors: list[str] = []

    seeders = [root / p for p in project.get("seeders") or []]

    # BDA is being split into a public checkout and a private research overlay, and the
    # sync policy puts research scripts and the decisions documents on the private side.
    # A project whose seeders AND document are both absent is simply not in this
    # checkout - failing there would break the public repository's CI over a record it
    # is not supposed to hold. One present without the other is a real inconsistency and
    # still fails, which is what keeps this from becoming a way to silence the gate.
    doc = project.get("decisions_doc")
    doc_path = (root / doc) if doc else None
    if not any(path.exists() for path in seeders) and (doc_path is None or not doc_path.exists()):
        return [], f"{key}: not present in this checkout; skipped"

    recorded, seeder_errors = _parse_seeders(seeders, prefix)
    errors += seeder_errors

    declared_gaps, gap_errors = _declared_gap_numbers(project)
    errors += gap_errors

    if doc is None:
        # Not a pass and not a failure: there is nothing to measure against yet. Saying
        # so beats reporting a vacuous 0/0 that reads like coverage.
        if recorded:
            errors.append(
                f"{key}: seeders record {len(recorded)} decision(s) but the project has no "
                f"decisions_doc to check them against"
            )
        return errors, f"{key}: no decisions document; {len(recorded)} recorded ref(s), coverage not measurable"

    assert doc_path is not None
    if not doc_path.exists():
        return [f"{key}: decisions_doc {doc} does not exist"], f"{key}: unreadable"
    defined, doc_errors = _parse_doc(doc_path, prefix)
    errors += doc_errors

    dangling = sorted(recorded - defined)
    if dangling:
        errors.append(
            f"{key}: recorded but not defined in {doc}: "
            + ", ".join(f"{prefix}{n:03d}" for n in dangling)
            + " - a row cannot be the record of a decision that was never written"
        )

    if defined:
        undeclared = sorted(set(range(min(defined), max(defined) + 1)) - defined - declared_gaps)
        if undeclared:
            errors.append(
                f"{key}: undeclared gap(s) in the numbering: "
                + ", ".join(f"{prefix}{n:03d}" for n in undeclared)
                + f" - declare them in the contract with the decision that declared them, "
                f"or write them into {doc}"
            )

    baseline = int(project.get("recorded_baseline", 0))
    covered = len(recorded & defined)
    if covered < baseline:
        errors.append(
            f"{key}: coverage fell from {baseline} to {covered} recorded decision(s); "
            f"the baseline is a ratchet and does not go down"
        )
    elif covered > baseline:
        errors.append(
            f"{key}: coverage rose from {baseline} to {covered}; raise `recorded_baseline` "
            f"to {covered} in contracts/decision-records.yaml so it keeps meaning something"
        )

    return errors, (
        f"{key}: {covered}/{len(defined)} decisions recorded"
        + (f", {len(declared_gaps)} declared missing" if declared_gaps else "")
    )


def main(argv: list[str] | None = None) -> int:
    # argv is a parameter rather than read straight off sys.argv so the tests can call
    # this the way CI does; under pytest sys.argv[1] is the test path, and reading it
    # would have the check quietly validate the wrong file.
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0] if args else "contracts/decision-records.yaml")
    if not path.is_absolute():
        path = REPOSITORY_ROOT / path
    # JSON, in a .yaml file, exactly as contracts/v2-flow-matrix.yaml is: the checker
    # then needs no YAML parser, and so depends on nothing that backend_v2/pyproject.toml
    # does not declare. PyYAML is present in this environment only transitively.
    if not path.exists():
        # The contract names projects by their decisions documents, which the sync policy
        # keeps under `private/`. In the public checkout there is no contract and no
        # record to check, and failing there would break a build over something that
        # repository is deliberately not holding. An explicit line beats a silent pass.
        shown = path.relative_to(REPOSITORY_ROOT) if path.is_relative_to(REPOSITORY_ROOT) else path
        print(f"no decision-record contract at {shown}; nothing to check")
        return 0
    contract = json.loads(path.read_text(encoding="utf-8"))

    errors: list[str] = []
    lines: list[str] = []
    for project in contract.get("projects") or []:
        project_errors, summary = check_project(project, REPOSITORY_ROOT)
        errors += project_errors
        lines.append(summary)

    for line in lines:
        print(line)
    if errors:
        print("\ndecision coverage check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
