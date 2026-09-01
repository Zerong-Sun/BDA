from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from backend_v2.scripts import _data_root


def clear_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BDA_DATA_ROOT", raising=False)
    monkeypatch.delenv("BDA_LOCAL_ROOT", raising=False)


def test_data_root_prefers_environment_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configured = tmp_path / "custom-data"
    monkeypatch.setenv("BDA_DATA_ROOT", str(configured))

    assert _data_root.data_root() == configured.resolve()


def test_data_root_finds_store_above_linked_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clear_overrides(monkeypatch)
    repo = tmp_path / "project/.codex/worktrees/abc/BDA"
    repo.mkdir(parents=True)
    store = tmp_path / "project/BDA-data"
    store.mkdir()
    monkeypatch.setattr(_data_root, "REPO_ROOT", repo)

    assert _data_root.data_root() == store


def test_data_root_uses_git_common_dir_when_store_is_not_an_ancestor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_overrides(monkeypatch)
    repo = tmp_path / "isolated/worktree/BDA"
    repo.mkdir(parents=True)
    primary = tmp_path / "project/BDA"
    (primary / ".git").mkdir(parents=True)
    store = tmp_path / "project/BDA-data"
    store.mkdir()
    monkeypatch.setattr(_data_root, "REPO_ROOT", repo)
    monkeypatch.setattr(
        _data_root.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout=f"{primary / '.git'}\n"),
    )

    assert _data_root.data_root() == store


def test_data_root_has_conventional_fallback_when_git_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_overrides(monkeypatch)
    repo = tmp_path / "checkout/BDA"
    repo.mkdir(parents=True)
    monkeypatch.setattr(_data_root, "REPO_ROOT", repo)
    monkeypatch.setattr(
        _data_root.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("git unavailable")),
    )

    assert _data_root.data_root() == repo.parent / "BDA-data"


def test_local_root_override_and_data_sibling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configured = tmp_path / "data"
    monkeypatch.setenv("BDA_DATA_ROOT", str(configured))
    monkeypatch.delenv("BDA_LOCAL_ROOT", raising=False)
    assert _data_root.local_root() == tmp_path / "BDA-local"

    local = tmp_path / "private"
    monkeypatch.setenv("BDA_LOCAL_ROOT", str(local))
    assert _data_root.local_root() == local.resolve()


@pytest.mark.parametrize("unsafe", ["", "/absolute/file", "../escape", "analysis/../../escape"])
def test_data_path_rejects_unsafe_paths(unsafe: str) -> None:
    with pytest.raises(ValueError, match="safe"):
        _data_root.data_path(unsafe)


def test_data_path_maps_legacy_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BDA_DATA_ROOT", str(tmp_path))

    assert _data_root.data_path("research projects/P/a.pdb") == tmp_path / "research-projects/P/a.pdb"
    assert _data_root.data_path("fig/plot.png") == tmp_path / "figures/plot.png"
    assert _data_root.data_path("analysis/report.json") == tmp_path / "analysis/report.json"


def test_resolve_recorded_keeps_repository_paths_and_rejects_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_data_root, "REPO_ROOT", tmp_path / "repo")
    monkeypatch.setenv("BDA_DATA_ROOT", str(tmp_path / "data"))

    assert _data_root.resolve_recorded("backend_v2/file.txt") == tmp_path / "repo/backend_v2/file.txt"
    assert _data_root.resolve_recorded("deliverables/file.txt") == tmp_path / "data/deliverables/file.txt"
    with pytest.raises(ValueError, match="safe"):
        _data_root.resolve_recorded("../secret")
def test_resolve_recorded_sends_the_local_label_to_the_local_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A recorded `BDA_LOCAL_ROOT/...` label reads back on a machine that stores it elsewhere.

    Cluster downloads are pinned by SHA-256 but never enter version control, so the
    result documents that cite them record a label instead of a home directory.
    """
    monkeypatch.setattr(_data_root, "REPO_ROOT", tmp_path / "repo")
    monkeypatch.setenv("BDA_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("BDA_LOCAL_ROOT", str(tmp_path / "elsewhere"))

    assert _data_root.resolve_recorded("BDA_LOCAL_ROOT/backups/run/model.cif") == (
        tmp_path / "elsewhere/backups/run/model.cif"
    )
    # The label is only special as the leading component.
    assert _data_root.resolve_recorded("backend_v2/BDA_LOCAL_ROOT/x") == (
        tmp_path / "repo/backend_v2/BDA_LOCAL_ROOT/x"
    )
