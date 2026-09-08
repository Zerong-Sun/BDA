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
