#!/usr/bin/env python3
"""Resolve the research-data store that used to live inside this repository.

`research projects/`, `deliverables/` and `fig/` were moved out of the platform
repository so it holds code only. They now live in a sibling data store, by
default `../BDA-data` relative to the repo root:

    BDA/            <- this repository (code only)
    BDA-data/
        research-projects/
        deliverables/
        figures/

Point `BDA_DATA_ROOT` at another location to override. Scripts that read this
data must resolve paths through `data_path()` rather than hardcoding a
repo-relative path, so the store stays relocatable.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Directory names as they were before the split, mapped to their new homes.
_MOVED = {
    "research projects": "research-projects",
    "deliverables": "deliverables",
    "fig": "figures",
    "analysis": "analysis",
}


#: Conventional directory name of the store, as a sibling of the repository.
STORE_NAME = "BDA-data"
LOCAL_STORE_NAME = "BDA-local"

#: Prefix used in recorded paths to name a file in the machine-local store.
LOCAL_ROOT_LABEL = "BDA_LOCAL_ROOT"


def _primary_checkout_data_root() -> Path | None:
    """Return the data-store sibling of Git's primary checkout, if available.

    Codex worktrees can live outside the primary checkout's directory tree, so
    walking filesystem parents is insufficient.  Git's common directory still
    points at the primary checkout (``<primary>/.git``) from every linked
    worktree and gives us a stable way to find its sibling data store.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    common_dir = Path(result.stdout.strip())
    if not common_dir.name:
        return None
    primary_checkout = common_dir.parent if common_dir.name == ".git" else None
    if primary_checkout is None:
        return None
    return primary_checkout.parent / STORE_NAME


def data_root() -> Path:
    """The research-data store. Override with `BDA_DATA_ROOT`.

    Found by walking up from the repository looking for a `BDA-data` directory,
    rather than assuming `REPO_ROOT.parent`. A git worktree lives several levels
    below the checkout it belongs to (`.claude/worktrees/<name>`), so the naive
    parent is `.claude/worktrees/` there and resolves to a path that does not
    exist. Walking up finds the same store from the main checkout and from any
    worktree.
    """
    override = os.environ.get("BDA_DATA_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    for ancestor in [REPO_ROOT, *REPO_ROOT.parents]:
        candidate = ancestor / STORE_NAME
        if candidate.is_dir():
            return candidate
    primary_candidate = _primary_checkout_data_root()
    if primary_candidate is not None and primary_candidate.is_dir():
        return primary_candidate
    # Nothing found: name the conventional location so the error says where to look.
    return primary_candidate or REPO_ROOT.parent / STORE_NAME


def local_root() -> Path:
    """The machine-local evidence store. Override with ``BDA_LOCAL_ROOT``.

    By convention it is a sibling of the resolved data store. This keeps scripts
    portable across primary checkouts and linked worktrees without baking a user
    home directory into source code.
    """
    override = os.environ.get("BDA_LOCAL_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return data_root().parent / LOCAL_STORE_NAME


def data_path(legacy_relative: str) -> Path:
    """Translate a pre-split repo-relative path into the data store.

    `data_path("deliverables/foo/bar.json")` resolves to
    `<data root>/deliverables/foo/bar.json`. Paths that were not part of the
    move are resolved against the data root unchanged.
    """
    logical = Path(legacy_relative)
    parts = logical.parts
    if not parts or logical.is_absolute() or ".." in parts:
        raise ValueError("expected a safe, non-empty relative path")
    head, *rest = parts
    return data_root().joinpath(_MOVED.get(head, head), *rest)


def resolve_recorded(recorded: str) -> Path:
    """Locate a path recorded in a manifest, wherever it lives now.

    The inverse of `display_path`. Recorded paths are repo-relative strings from
    before the split; the ones naming moved directories now resolve into the data
    store, and everything else stays repo-relative. Use this to *read* a recorded
    path — `data_path` assumes the store and would send `backend_v2/...` there too.

    A recorded path may also start with ``BDA_LOCAL_ROOT/``. That label names the
    machine-local evidence store, which holds cluster downloads that are pinned by
    SHA-256 but never enter version control. Recording the label rather than a home
    directory is what lets one result document be read on another machine.
    """
    logical = Path(recorded)
    if not logical.parts or logical.is_absolute() or ".." in logical.parts:
        raise ValueError("expected a safe, non-empty recorded path")
    head, *rest = logical.parts
    if head == LOCAL_ROOT_LABEL:
        return local_root().joinpath(*rest)
    if head in _MOVED:
        return data_path(recorded)
    return REPO_ROOT / recorded


def display_path(path: Path) -> str:
    """A stable label for a path, for recording provenance in output manifests.

    Paths inside the repository render relative to it, as they always have.
    Paths in the data store render under their **pre-split** name — a file now at
    `<store>/research-projects/MANUKA/x.pdb` still records as
    `research projects/MANUKA/x.pdb`.

    That is deliberate: these strings go into manifests that are checksummed and
    compared against ones generated before the split. Recording the new location
    would change the manifest bytes and break that comparison, for a path that
    names the same evidence either way.
    """
    resolved = path.resolve()
    root = data_root().resolve()
    if resolved.is_relative_to(root):
        relative = resolved.relative_to(root)
        head, *rest = relative.parts
        legacy_head = {new: old for old, new in _MOVED.items()}.get(head, head)
        return str(Path(legacy_head, *rest))
    return str(resolved.relative_to(REPO_ROOT))


def require(path: Path, *, hint: str = "") -> Path:
    """Fail with an actionable message rather than a bare FileNotFoundError."""
    if path.exists():
        return path
    detail = f" {hint}" if hint else ""
    raise SystemExit(
        f"Research data not found: {path}\n"
        f"It moved out of the repository during the v3 split. Set BDA_DATA_ROOT "
        f"to the directory holding research-projects/ and deliverables/.{detail}"
    )
