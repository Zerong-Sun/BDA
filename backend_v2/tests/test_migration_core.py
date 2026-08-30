import re
from datetime import UTC
from pathlib import Path

import pytest
from backend_v2.app.migration.core import file_sha256, local_artifact_path, parse_time, stable_id
from backend_v2.scripts.check_migration_rehearsals import RehearsalMismatch, validate_reports


def test_stable_ids_and_utc_parsing_are_deterministic() -> None:
    assert stable_id("projects", "legacy") == stable_id("projects", "legacy")
    assert stable_id("projects", "legacy") != stable_id("targets", "legacy")
    assert parse_time(None) is None
    assert parse_time("2026-07-15 10:00:00").tzinfo == UTC
    assert parse_time("2026-07-15T01:00:00Z").hour == 1


def test_artifact_resolution_is_allowlisted_and_supports_prefixed_roots(tmp_path) -> None:
    artifacts = tmp_path / "artifacts"
    deliverables = tmp_path / "deliverables"
    artifacts.mkdir()
    deliverables.mkdir()
    backend_file = artifacts / "a.pdb"
    delivery_file = deliverables / "package.zip"
    backend_file.write_bytes(b"ATOM")
    delivery_file.write_bytes(b"zip")
    roots = [artifacts, deliverables]

    assert local_artifact_path("artifact://a.pdb", roots) == backend_file
    assert local_artifact_path("artifact://deliverables/package.zip", roots) == delivery_file
    assert local_artifact_path(f"file://{backend_file}", roots) == backend_file
    assert local_artifact_path("artifact://../secret", roots) is None
    assert local_artifact_path(f"file://{tmp_path / 'outside'}", roots) is None
    assert local_artifact_path("https://example.test/a.pdb", roots) is None
    assert file_sha256(backend_file) == "939f34238170826d249f0103a04e8d7406da30abd2dad9a8dc92702e31165ff5"


def test_three_migration_rehearsals_must_have_identical_stable_results() -> None:
    baseline = {
        "source_fingerprint": "a" * 64,
        "tables": {"projects": {"source": 7, "migrated": 7, "deferred": 0, "rejected": 0}},
        "id_map": {"projects:1": "uuid"},
        "id_map_digest": "b" * 64,
        "file_checksums": {"artifact:1": "c" * 64},
        "file_checksums_digest": "d" * 64,
        "files": {"verified": 1, "missing": 0},
        "rejections": [],
        "rejection_summary": {},
    }
    reports = [{**baseline, "rehearsal": number} for number in (1, 2, 3)]
    result = validate_reports(reports, expected_tables={"projects": 7}, expected_verified=1)
    assert result["status"] == "passed"
    assert result["id_map_entries"] == 1

    reports[2] = {**reports[2], "id_map_digest": "changed"}
    with pytest.raises(RehearsalMismatch, match="differs"):
        validate_reports(reports)


def test_every_revision_id_fits_the_alembic_version_column() -> None:
    """``alembic_version.version_num`` is VARCHAR(32) and Alembic does not check.

    A longer id runs the whole migration, prints its own success messages, and then dies
    at the version stamp with `value too long for type character varying(32)` - so the
    upgrade rolls back while looking like it worked. Caught once at 33 characters.
    """
    versions = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    # Older revisions declare `revision = "..."` without the annotation.
    pattern = re.compile(r'^revision(?:: str)? = "([^"]+)"', re.MULTILINE)

    offenders = {}
    for path in sorted(versions.glob("[0-9]*.py")):
        match = pattern.search(path.read_text())
        assert match, f"{path.name} declares no revision id"
        revision = match.group(1)
        if len(revision) > 32:
            offenders[path.name] = f"{revision} ({len(revision)} chars)"

    assert not offenders, offenders
