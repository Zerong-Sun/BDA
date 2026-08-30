from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from backend_v2.scripts import check_document_inventory as inventory


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def valid_index(manifest_hash: str, *, count: int = 1) -> dict[str, object]:
    return {
        "schema_version": 1,
        "logical_root": "BDA_DATA_ROOT",
        "snapshot": "analysis/2026-08-29",
        "manifest": "analysis/2026-08-29/SHA256SUMS",
        "manifest_sha256": manifest_hash,
        "payload_count": count,
        "source_index": "analysis/2026-08-29/SOURCES.json",
    }


def write_snapshot(tmp_path: Path, lines: list[str], files: dict[str, bytes]) -> tuple[Path, dict[str, object]]:
    snapshot = tmp_path / "analysis/2026-08-29"
    snapshot.mkdir(parents=True)
    for name, content in files.items():
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    manifest_content = ("\n".join(lines) + "\n").encode()
    (snapshot / "SHA256SUMS").write_bytes(manifest_content)
    return tmp_path, valid_index(digest(manifest_content), count=len(lines))


def test_markdown_parser_ignores_fenced_headings_and_links() -> None:
    text = "# Visible\n```md\n# Hidden\n[bad](missing.md)\n```\n[good](present.md)\n"

    assert inventory.markdown_lines_outside_fences(text) == ["# Visible", "[good](present.md)"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("<file name.md>", "file name.md"), ('file.md "title"', "file.md"), ("file.md", "file.md")],
)
def test_link_target_supports_markdown_target_forms(raw: str, expected: str) -> None:
    assert inventory.link_target(raw) == expected


def test_load_data_index_supports_catalog_only_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(inventory, "REPO_ROOT", tmp_path)
    path = tmp_path / "docs/data/index.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(valid_index("a" * 64)), encoding="utf-8")

    payload, errors = inventory.load_data_index(path)

    assert payload is not None
    assert errors == []


def test_verify_data_manifest_accepts_matching_payloads(tmp_path: Path) -> None:
    content = b"preserved evidence\n"
    store, index = write_snapshot(tmp_path, [f"{digest(content)}  nested/file.bin"], {"nested/file.bin": content})

    assert inventory.verify_data_manifest(store, index) == []


@pytest.mark.parametrize(
    ("line", "files", "expected"),
    [
        ("not-a-hash  file.bin", {"file.bin": b"x"}, "malformed SHA-256"),
        (f"{'0' * 64}  ../escape", {}, "unsafe payload path"),
        (f"{'0' * 64}  missing.bin", {}, "payload is missing"),
        (f"{'0' * 64}  file.bin", {"file.bin": b"x"}, "SHA-256 mismatch"),
    ],
)
def test_verify_data_manifest_reports_invalid_entries(
    tmp_path: Path, line: str, files: dict[str, bytes], expected: str
) -> None:
    store, index = write_snapshot(tmp_path, [line], files)

    assert any(expected in error for error in inventory.verify_data_manifest(store, index))


def test_verify_data_manifest_rejects_duplicate_paths(tmp_path: Path) -> None:
    content = b"x"
    line = f"{digest(content)}  file.bin"
    store, index = write_snapshot(tmp_path, [line, line], {"file.bin": content})

    assert any("duplicate payload path" in error for error in inventory.verify_data_manifest(store, index))
