#!/usr/bin/env python3
"""Validate active Markdown, index reachability, links, and external-data references."""

from __future__ import annotations

import re
import sys
from collections import deque
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"
INDEX = DOCS_ROOT / "README.md"

METADATA_FIELDS = ("状态：", "最后核验：", "权威范围：", "数据来源：", "替代关系：")
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
DATA_LINK_PREFIX = "BDA_DATA_ROOT/"


def relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def category(path: Path) -> str:
    name = relative(path)
    if name.startswith("docs/archive/"):
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


def main() -> int:
    markdown = sorted(DOCS_ROOT.rglob("*.md"))
    errors: list[str] = []
    notices: list[str] = []
    edges: dict[Path, set[Path]] = {path.resolve(): set() for path in markdown}

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
        errors.append("docs/DATA_CATALOG.md: data publication policy is required")

    for notice in notices:
        print(f"[historical-reference] {notice}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"document inventory: {len(markdown)} Markdown files; "
        f"{sum(category(path) == 'active' for path in markdown)} active; "
        "external_data=policy-only; OK"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
