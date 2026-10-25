from backend_v2.scripts.check_coverage import combined_percentage


def test_missing_core_coverage_fails_closed() -> None:
    assert combined_percentage({}, "backend_v2/app/identity/service.py") == 0
    files = {"backend_v2/app/identity/service.py.old": {
        "summary": {"num_statements": 10, "covered_lines": 10},
    }}
    assert combined_percentage(files, "backend_v2/app/identity/service.py") == 0


def test_package_coverage_is_weighted_by_statements() -> None:
    files = {
        "package/a.py": {"summary": {"num_statements": 9, "covered_lines": 9}},
        "package/b.py": {"summary": {"num_statements": 1, "covered_lines": 0}},
    }
    assert combined_percentage(files, "package/") == 90
    assert combined_percentage(files, "package/b.py") == 0


def _branch_report(covered=96, total=104):
    from backend_v2.scripts.check_coverage import RESEARCH_BRANCH_FILE

    return {"meta": {"branch_coverage": True}, "totals": {"percent_covered": 99.9},
            "files": {RESEARCH_BRANCH_FILE: {"summary": {
                "percent_covered": 99.9, "num_branches": total, "covered_branches": covered,
            }}}}


def test_high_combined_percentage_cannot_hide_uncovered_branches(capsys) -> None:
    from backend_v2.scripts.check_coverage import research_branch_gate

    assert research_branch_gate(_branch_report()) == 1
    assert "92.31% (96/104 branches) is below 95.00%" in capsys.readouterr().out


def test_branch_gate_accepts_exact_threshold(capsys) -> None:
    from backend_v2.scripts.check_coverage import research_branch_gate

    assert research_branch_gate(_branch_report(95, 100)) == 0
    assert "95.00% (95/100 branches)" in capsys.readouterr().out


def test_branch_gate_requires_enabled_measurement_and_the_exact_file() -> None:
    from backend_v2.scripts.check_coverage import RESEARCH_BRANCH_FILE, research_branch_gate

    for report in [{}, {"meta": {"branch_coverage": False}},
                   {"meta": {"branch_coverage": True}, "files": {}},
                   {"meta": {"branch_coverage": True}, "files": {RESEARCH_BRANCH_FILE + ".old": {"summary": {}}}}]:
        assert research_branch_gate(report) == 1


def test_branch_gate_rejects_missing_zero_or_impossible_denominators() -> None:
    from backend_v2.scripts.check_coverage import research_branch_gate

    for covered, total in [(0, 0), (1, -1), (-1, 104), (105, 104), (True, 1), ("96", 104), (96, None)]:
        assert research_branch_gate(_branch_report(covered, total)) == 1


def test_branch_cli_checks_an_isolated_json_without_overall_package_data(tmp_path, monkeypatch) -> None:
    import json

    from backend_v2.scripts.check_coverage import main

    report = tmp_path / "research-only.json"
    report.write_text(json.dumps(_branch_report(99, 100)))
    monkeypatch.setattr("sys.argv", ["check_coverage.py", str(report), "--research-branch"])
    assert main() == 0


def test_default_cli_preserves_overall_line_coverage_mode(tmp_path, monkeypatch) -> None:
    import json

    from backend_v2.scripts.check_coverage import CORE_THRESHOLDS, main

    report = tmp_path / "overall.json"
    report.write_text(json.dumps({"totals": {"percent_covered": 99}, "files": {
        (prefix + "example.py" if prefix.endswith("/") else prefix): {
            "summary": {"num_statements": 100, "covered_lines": 99},
        } for prefix in CORE_THRESHOLDS
    }}))
    monkeypatch.setattr("sys.argv", ["check_coverage.py", str(report)])
    monkeypatch.setenv("BDA_V2_RUN_DB_TESTS", "1")
    assert main() == 0
