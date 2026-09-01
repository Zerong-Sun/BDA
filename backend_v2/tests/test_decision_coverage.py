"""The gate that keeps the decision record from quietly draining away.

`D101` in the sweet-protein decisions document is the reason this exists: twenty
decisions (D080-D099) were made on the cluster, cited by submission scripts, and never
written back - and nothing noticed, because the numbering lived only in prose.

These tests pin the three failures the checker has to catch, because a coverage gate
that passes on a broken tree is worse than none: it is a green tick over the same hole.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from backend_v2.scripts.check_decision_coverage import check_project, main

REPO = Path(__file__).resolve().parents[2]


def _write(tmp_path: Path, doc: str, seeder: str) -> dict:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/DECISIONS.md").write_text(doc, encoding="utf-8")
    (tmp_path / "scripts/seed.py").write_text(seeder, encoding="utf-8")
    return {
        "key": "t",
        "prefix": "D",
        "decisions_doc": "docs/DECISIONS.md",
        "seeders": ["scripts/seed.py"],
        "declared_gaps": [],
        "recorded_baseline": 0,
    }


DOC_123 = "| D001 | a | b |\n| D002 | a | b |\n| D003 | a | b |\n"


CONTRACT = REPO / "contracts/decision-records.yaml"


@pytest.mark.skipif(
    not CONTRACT.exists(),
    reason="no decision-record contract in this checkout; the sync policy keeps it private",
)
def test_the_repository_currently_passes_its_own_gate() -> None:
    """Not a tautology: the gate is a ratchet, so this fails the moment the committed
    baseline and the seeders disagree in either direction."""
    assert main([]) == 0


def test_a_missing_contract_is_reported_and_not_an_error(tmp_path: Path) -> None:
    """The public checkout holds the checker but not the records it checks."""
    assert main([str(tmp_path / "absent.yaml")]) == 0


def test_a_record_of_a_decision_that_was_never_written_is_an_error(tmp_path: Path) -> None:
    project = _write(tmp_path, DOC_123, 'dict(decision_ref="D009")\n')
    project["recorded_baseline"] = 0
    errors, _ = check_project(project, tmp_path)
    assert any("recorded but not defined" in e for e in errors)


def test_an_undeclared_hole_in_the_numbering_is_an_error(tmp_path: Path) -> None:
    """The D080-D099 failure, in miniature."""
    project = _write(tmp_path, "| D001 | a | b |\n| D004 | a | b |\n", "")
    errors, _ = check_project(project, tmp_path)
    assert any("undeclared gap" in e and "D002" in e and "D003" in e for e in errors)


def test_a_declared_hole_is_accepted_but_only_with_a_reason_and_an_author(tmp_path: Path) -> None:
    project = _write(tmp_path, "| D001 | a | b |\n| D004 | a | b |\n", "")
    project["declared_gaps"] = [{"first": 2, "last": 3, "declared_by": "D004", "reason": "on the cluster"}]
    errors, summary = check_project(project, tmp_path)
    assert errors == []
    assert "2 declared missing" in summary

    project["declared_gaps"] = [{"first": 2, "last": 3, "declared_by": "", "reason": ""}]
    errors, _ = check_project(project, tmp_path)
    assert any("declared_by" in e for e in errors)
    assert any("reason" in e for e in errors)


def test_coverage_is_a_ratchet_in_both_directions(tmp_path: Path) -> None:
    project = _write(tmp_path, DOC_123, 'dict(decision_ref="D002")\n')

    project["recorded_baseline"] = 2
    errors, _ = check_project(project, tmp_path)
    assert any("does not go down" in e for e in errors)

    project["recorded_baseline"] = 0
    errors, _ = check_project(project, tmp_path)
    # Improving coverage without raising the baseline leaves the baseline lying, which
    # is how a ratchet stops being one.
    assert any("raise `recorded_baseline`" in e for e in errors)

    project["recorded_baseline"] = 1
    assert check_project(project, tmp_path)[0] == []


def test_the_same_number_recorded_twice_is_caught_before_the_database_sees_it(tmp_path: Path) -> None:
    project = _write(tmp_path, DOC_123, 'dict(decision_ref="D001")\ndict(decision_ref="D001")\n')
    project["recorded_baseline"] = 1
    errors, _ = check_project(project, tmp_path)
    assert any("recorded twice" in e for e in errors)


def test_a_project_with_no_decisions_document_reports_that_instead_of_a_vacuous_pass(tmp_path: Path) -> None:
    """The cannabinoid project's actual state: reasoning in prose, no numbering."""
    project = _write(tmp_path, DOC_123, "")
    project["decisions_doc"] = None
    errors, summary = check_project(project, tmp_path)
    assert errors == []
    assert "coverage not measurable" in summary


def test_a_ref_recorded_against_a_project_with_no_document_is_still_an_error(tmp_path: Path) -> None:
    project = _write(tmp_path, DOC_123, 'dict(decision_ref="D001")\n')
    project["decisions_doc"] = None
    errors, _ = check_project(project, tmp_path)
    assert any("no decisions_doc" in e for e in errors)


def test_a_number_mentioned_inside_another_decisions_rationale_is_not_a_definition(tmp_path: Path) -> None:
    """`| D003 | ... | ... supersedes D002 ... |` defines D003, not D002.

    Without the line anchor the checker would count every cross-reference as a
    definition, and the coverage denominator would drift upward with every edit to the
    prose.
    """
    project = _write(tmp_path, "| D001 | a | b |\n| D002 | a | see D001 and D009 |\n", "")
    errors, summary = check_project(project, tmp_path)
    assert errors == []
    assert "0/2 decisions recorded" in summary


def test_the_prefix_keeps_two_projects_from_sharing_a_numbering_space(tmp_path: Path) -> None:
    project = _write(tmp_path, "| D001 | a | b |\n| C001 | a | b |\n", "")
    errors, _ = check_project(project, tmp_path)
    assert any("does not use this project's prefix" in e for e in errors)


@pytest.mark.parametrize("missing", ["docs/DECISIONS.md", "scripts/seed.py"])
def test_half_a_project_present_is_an_inconsistency_and_fails(tmp_path: Path, missing: str) -> None:
    """One of the pair present without the other is a broken contract, not a split."""
    project = _write(tmp_path, DOC_123, "")
    (tmp_path / missing).unlink()
    errors, _ = check_project(project, tmp_path)
    assert errors


def test_a_project_absent_from_this_checkout_is_skipped_not_failed(tmp_path: Path) -> None:
    """BDA is splitting into a public checkout and a private research overlay, and the
    sync policy puts research scripts and decisions documents on the private side.

    Failing there would break the public repository's CI over a record it is not
    supposed to hold. Skipping is only correct when *both* halves are gone - which is
    why the test above still fails when only one is.
    """
    project = _write(tmp_path, DOC_123, "")
    (tmp_path / "docs/DECISIONS.md").unlink()
    (tmp_path / "scripts/seed.py").unlink()
    errors, summary = check_project(project, tmp_path)
    assert errors == []
    assert "not present in this checkout" in summary
