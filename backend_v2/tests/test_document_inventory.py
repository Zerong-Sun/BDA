from __future__ import annotations

from pathlib import Path

import pytest
from backend_v2.scripts import check_document_inventory as inventory


def test_markdown_parser_ignores_fenced_headings_and_links() -> None:
    text = "# Visible\n```md\n# Hidden\n[bad](missing.md)\n```\n[good](present.md)\n"

    assert inventory.markdown_lines_outside_fences(text) == ["# Visible", "[good](present.md)"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("<file name.md>", "file name.md"), ('file.md "title"', "file.md"), ("file.md", "file.md")],
)
def test_link_target_supports_markdown_target_forms(raw: str, expected: str) -> None:
    assert inventory.link_target(raw) == expected


def test_local_link_keeps_external_and_symbolic_data_targets_out_of_the_graph(tmp_path: Path) -> None:
    source = tmp_path / "docs/guide.md"

    assert inventory.local_link(source, "https://example.org") is None
    assert inventory.local_link(source, "BDA_DATA_ROOT/private/file.json") is None
    assert inventory.local_link(source, "other.md") == tmp_path / "docs/other.md"


def test_category_separates_active_history_and_drafts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(inventory, "REPO_ROOT", tmp_path)

    assert inventory.category(tmp_path / "docs/guide.md") == "active"
    assert inventory.category(tmp_path / "docs/archive/old.md") == "history"
    assert inventory.category(tmp_path / "docs/superpowers/specs/draft.md") == "draft"
