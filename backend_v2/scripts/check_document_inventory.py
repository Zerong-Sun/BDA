#!/usr/bin/env python3
"""Validate active Markdown, index reachability, links, and external-data references."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from backend_v2.scripts._data_root import data_root

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"
INDEX = DOCS_ROOT / "README.md"
DATA_INDEX = DOCS_ROOT / "data/BDA_DATA_INDEX_2026-09-01.json"
KNOWN_MISSING = DOCS_ROOT / "data/KNOWN_MISSING_2026-09-01.json"

HISTORICAL_FILES = {
    "docs/NEXT_EXPERIMENTS_2026-08-29.md",
    "docs/V2_LOCAL_ACCEPTANCE.md",
    "docs/refactor/CURRENT_STATE_2026-08-22.md",
    "docs/refactor/CURRENT_STATE_2026-08-27.md",
    "docs/refactor/DEFECTS_FOUND.md",
    "docs/refactor/MASTER_PLAN.md",
    "docs/refactor/NEXT_STEPS.md",
}
METADATA_FIELDS = ("状态：", "最后核验：", "权威范围：", "数据来源：", "替代关系：")
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
DATA_LINK_PREFIX = "BDA_DATA_ROOT/"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def category(path: Path) -> str:
    name = relative(path)
    if name.startswith("docs/archive/") or name in HISTORICAL_FILES:
        return "history"
    if name.startswith("docs/superpowers/"):
        return "draft"
    return "active"


def markdown_lines_outside_fences(text: str) -> list[str]:
    result: list[str] = []
    fenced = False
    marker = ""
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            current = stripped[:3]
            if not fenced:
                fenced = True
                marker = current
            elif current == marker:
                fenced = False
            continue
        if not fenced:
            result.append(line)
    return result


def link_target(raw: str) -> str:
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        return target[1 : target.index(">")]
    return target.split(maxsplit=1)[0]


def local_link(source: Path, target: str) -> Path | None:
    if not target or target.startswith(("#", "http://", "https://", "mailto:", "tel:")):
        return None
    if target.startswith(DATA_LINK_PREFIX):
        return None
    path_part = unquote(target.split("#", 1)[0])
    if not path_part:
        return None
    return (source.parent / path_part).resolve()


def sha256_file(path: Path) -> str:
    """Hash a file without loading large research artifacts into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_data_index(path: Path = DATA_INDEX) -> tuple[dict[str, Any] | None, list[str]]:
    """Load and validate the versioned catalog used when CI has no data store."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        # The index names research snapshots and their manifest hashes, so it is a
        # private record and `docs/data/` is absent from every public checkout. An
        # absent directory means there is nothing to check; a present directory
        # missing this file means the index was dropped, which is a real failure.
        if not path.parent.is_dir():
            return None, []
        return None, [f"{relative(path)}: required external-data index is missing"]
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"{relative(path)}: cannot read external-data index: {exc}"]

    errors: list[str] = []
    if not isinstance(payload, dict):
        return None, [f"{relative(path)}: external-data index must be a JSON object"]
    required = {
        "schema_version": int,
        "logical_root": str,
        "snapshot": str,
        "manifest": str,
        "manifest_sha256": str,
        "payload_count": int,
        "source_index": str,
    }
    for field, expected_type in required.items():
        value = payload.get(field)
        if not isinstance(value, expected_type) or isinstance(value, bool):
            errors.append(f"{relative(path)}: {field} must be {expected_type.__name__}")
    if errors:
        return payload, errors
    if payload["schema_version"] != 1:
        errors.append(f"{relative(path)}: unsupported schema_version {payload['schema_version']}")
    if payload["logical_root"] != "BDA_DATA_ROOT":
        errors.append(f"{relative(path)}: logical_root must be BDA_DATA_ROOT")
    if payload["payload_count"] < 1:
        errors.append(f"{relative(path)}: payload_count must be positive")
    if not SHA256_RE.fullmatch(payload["manifest_sha256"]):
        errors.append(f"{relative(path)}: manifest_sha256 must be 64 lowercase hexadecimal characters")
    for field in ("snapshot", "manifest", "source_index"):
        logical = Path(payload[field])
        if logical.is_absolute() or ".." in logical.parts:
            errors.append(f"{relative(path)}: {field} must be a safe relative path")
    manifest = Path(payload["manifest"])
    snapshot = Path(payload["snapshot"])
    if manifest.parent != snapshot:
        errors.append(f"{relative(path)}: manifest must be directly inside snapshot")
    return payload, errors


def verify_data_manifest(store: Path, index: dict[str, Any]) -> list[str]:
    """Verify the snapshot manifest and every payload it names."""
    errors: list[str] = []
    manifest = store / str(index["manifest"])
    snapshot = store / str(index["snapshot"])
    if not manifest.is_file():
        return [f"{DATA_LINK_PREFIX}{index['manifest']}: manifest is missing"]
    actual_manifest_hash = sha256_file(manifest)
    if actual_manifest_hash != index["manifest_sha256"]:
        errors.append(
            f"{DATA_LINK_PREFIX}{index['manifest']}: SHA-256 mismatch "
            f"({actual_manifest_hash} != {index['manifest_sha256']})"
        )

    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [*errors, f"{DATA_LINK_PREFIX}{index['manifest']}: cannot read manifest: {exc}"]
    if len(lines) != index["payload_count"]:
        errors.append(
            f"{DATA_LINK_PREFIX}{index['manifest']}: expected {index['payload_count']} payloads, found {len(lines)}"
        )

    seen: set[str] = set()
    snapshot_resolved = snapshot.resolve()
    for line_number, line in enumerate(lines, 1):
        try:
            expected, name = line.split("  ", 1)
        except ValueError:
            errors.append(f"{DATA_LINK_PREFIX}{index['manifest']}:{line_number}: malformed checksum line")
            continue
        logical = Path(name)
        if not SHA256_RE.fullmatch(expected):
            errors.append(f"{DATA_LINK_PREFIX}{index['manifest']}:{line_number}: malformed SHA-256")
            continue
        if not name or logical.is_absolute() or ".." in logical.parts:
            errors.append(f"{DATA_LINK_PREFIX}{index['manifest']}:{line_number}: unsafe payload path {name!r}")
            continue
        if name in seen:
            errors.append(f"{DATA_LINK_PREFIX}{index['manifest']}:{line_number}: duplicate payload path {name}")
            continue
        seen.add(name)
        candidate = (snapshot / logical).resolve()
        if not candidate.is_relative_to(snapshot_resolved):
            errors.append(f"{DATA_LINK_PREFIX}{index['manifest']}:{line_number}: payload escapes snapshot")
        elif not candidate.is_file():
            errors.append(f"{DATA_LINK_PREFIX}{index['snapshot']}/{name}: payload is missing")
        else:
            actual = sha256_file(candidate)
            if actual != expected:
                errors.append(
                    f"{DATA_LINK_PREFIX}{index['snapshot']}/{name}: SHA-256 mismatch ({actual} != {expected})"
                )
    return errors


def load_known_missing() -> set[str]:
    """Logical data paths that are registered as lost, not as broken links.

    Some research data existed only as untracked working files and went with the
    data store. The documents that cite it stay as they are — the citation is the
    provenance — but the checker must not report the same known hole every run,
    or it stops being read. Registering a path downgrades it to a notice.

    The register is fail-closed in both directions: an entry whose file is present
    again is an error, so the register cannot quietly outlive the loss it records.
    """
    if not KNOWN_MISSING.is_file():
        return set()
    try:
        payload = json.loads(KNOWN_MISSING.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {str(entry["path"]) for entry in payload.get("missing", []) if entry.get("path")}


def main() -> int:
    markdown = sorted(DOCS_ROOT.rglob("*.md"))
    errors: list[str] = []
    notices: list[str] = []
    edges: dict[Path, set[Path]] = {path.resolve(): set() for path in markdown}
    store = data_root()
    verify_data = store.is_dir()
    data_index, data_index_errors = load_data_index()
    errors.extend(data_index_errors)
    known_missing = load_known_missing()

    for path in markdown:
        text = path.read_text(encoding="utf-8")
        visible = markdown_lines_outside_fences(text)
        visible_text = "\n".join(visible)
        kind = category(path)
        h1_count = sum(line.startswith("# ") for line in visible)
        if kind == "active":
            if h1_count != 1:
                errors.append(f"{relative(path)}: active document has {h1_count} H1 headings")
            header = "\n".join(visible[:30])
            for field in METADATA_FIELDS:
                if field not in header:
                    errors.append(f"{relative(path)}: missing active metadata field {field}")

        for match in LINK_RE.finditer(visible_text):
            target = link_target(match.group(1))
            if target.startswith(DATA_LINK_PREFIX):
                logical = unquote(target.removeprefix(DATA_LINK_PREFIX).split("#", 1)[0])
                if not logical or logical.startswith(("/", "../")):
                    errors.append(f"{relative(path)}: malformed BDA_DATA_ROOT link {target}")
                elif verify_data and not (store / logical).exists():
                    if logical in known_missing:
                        notices.append(f"known-missing: {relative(path)} cites {target}")
                    else:
                        errors.append(f"{relative(path)}: missing external data {target}")
                continue
            resolved = local_link(path, target)
            if resolved is None:
                continue
            if resolved.exists():
                if resolved.suffix.lower() == ".md" and resolved in edges:
                    edges[path.resolve()].add(resolved)
                continue
            message = f"{relative(path)}: broken link {target}"
            if kind == "active":
                errors.append(message)
            else:
                notices.append(f"{kind}: {message}")

    reachable: set[Path] = set()
    queue: deque[Path] = deque([INDEX.resolve()])
    while queue:
        current = queue.popleft()
        if current in reachable:
            continue
        reachable.add(current)
        queue.extend(edges.get(current, set()) - reachable)
    for path in markdown:
        if category(path) == "active" and path.resolve() not in reachable:
            errors.append(f"{relative(path)}: active document is not reachable from docs/README.md")

    if not (DOCS_ROOT / "DATA_CATALOG.md").is_file():
        errors.append("docs/DATA_CATALOG.md: external-data catalog is required")
    if verify_data and data_index is not None and not data_index_errors:
        errors.extend(verify_data_manifest(store, data_index))
    if verify_data:
        for logical in sorted(known_missing):
            if (store / logical).exists():
                errors.append(
                    f"{relative(KNOWN_MISSING)}: {logical} is present again; "
                    "remove it from the register instead of leaving a stale entry"
                )

    for notice in notices:
        label, _, rest = notice.partition(": ")
        if label == "known-missing":
            print(f"[known-missing] {rest}")
        else:
            print(f"[historical-reference] {notice}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"document inventory: {len(markdown)} Markdown files; "
        f"{sum(category(path) == 'active' for path in markdown)} active; "
        f"external_data={'verified' if verify_data else 'catalog-only'}; OK"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
