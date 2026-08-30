from __future__ import annotations

from pathlib import Path

import pytest

from scripts import check_public_data as public_data


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (Path("README.md"), True),
        (Path("CLAUDE.md"), True),
        (Path("docs/guide.md"), True),
        (Path("backend_v2/app/service.py"), False),
    ],
)
def test_publication_text_scope(path: Path, expected: bool) -> None:
    assert public_data.is_publication_text(path) is expected


@pytest.mark.parametrize(
    "marker",
    [
        b"docs/refactor/CURRENT_STATE_2026-08-29.md",
        b"/work/" + b"bme-" + b"sunzr/private-run",
    ],
)
def test_publication_text_rejects_private_or_stale_markers(marker: bytes) -> None:
    errors: list[str] = []

    public_data.validate_publication_text(Path("docs/guide.md"), marker, errors)

    assert len(errors) == 1
    assert "forbidden in public documentation" in errors[0]


def test_publication_text_allows_generic_private_data_policy() -> None:
    errors: list[str] = []

    public_data.validate_publication_text(
        Path("docs/DATA_CATALOG.md"),
        b"Private packages use a manifest, checksum, and object URI.",
        errors,
    )

    assert errors == []


@pytest.mark.parametrize("marker", public_data.FORBIDDEN_REPOSITORY_MARKERS.values())
def test_repository_text_rejects_private_identifiers(marker: bytes) -> None:
    errors: list[str] = []

    public_data.validate_repository_text(Path("backend_v2/app/example.py"), marker, errors)

    assert len(errors) == 1
    assert "forbidden in the public repository" in errors[0]


def test_repository_text_allows_generic_research_capabilities() -> None:
    errors: list[str] = []

    public_data.validate_repository_text(
        Path("frontend/src/features/projects/ProjectChooser.tsx"),
        b"sweet_protein_design and binder_design remain supported software capabilities",
        errors,
    )

    assert errors == []


def test_publication_markers_do_not_block_implementation_compatibility_code() -> None:
    errors: list[str] = []

    public_data.validate_publication_text(
        Path("backend_v2/scripts/migration.py"),
        b"legacy migration may resolve worktree-recovery/ records",
        errors,
    )

    assert errors == []
