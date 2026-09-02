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


#: Assembled rather than written whole: this file is scanned by the gate it tests, and a
#: contiguous account path here would be exactly the thing the gate exists to reject.
SAMPLE_ACCOUNT = b"/work/" + b"bme-" + b"someone"


def test_repository_text_rejects_any_personal_cluster_account() -> None:
    """Not just the owner's. The rule was written as one literal name for a year, and
    three other people's accounts shipped in two releases because of it."""
    errors: list[str] = []

    public_data.validate_repository_text(
        Path("backend_v2/app/example.py"), b"conda " + SAMPLE_ACCOUNT + b"/envs/tool", errors
    )

    assert len(errors) == 1
    assert "personal cluster account is forbidden" in errors[0]


def test_repository_text_allows_a_frozen_file_at_its_recorded_count() -> None:
    path, allowed = next(iter(public_data.CLUSTER_ACCOUNT_EXEMPT.items()))
    errors: list[str] = []

    public_data.validate_repository_text(Path(path), (SAMPLE_ACCOUNT + b" ") * allowed, errors)

    assert errors == []


def test_repository_text_rejects_growth_in_a_frozen_file() -> None:
    """The exemption is a ratchet: a recorded count may fall, never rise."""
    path, allowed = next(iter(public_data.CLUSTER_ACCOUNT_EXEMPT.items()))
    errors: list[str] = []

    public_data.validate_repository_text(
        Path(path), (SAMPLE_ACCOUNT + b" ") * (allowed + 1), errors
    )

    assert len(errors) == 1
    assert "frozen and may only shrink" in errors[0]


def test_the_gate_does_not_name_the_accounts_it_forbids() -> None:
    """This file is scanned like any other, so spelling them out would publish them."""
    source = Path(public_data.__file__).read_bytes()
    assert not public_data.CLUSTER_ACCOUNT.search(source)


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
