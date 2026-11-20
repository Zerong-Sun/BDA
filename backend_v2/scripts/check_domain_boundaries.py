"""Fail when one backend domain reaches into another domain's persistence.

A repository is persistence for the domain that owns its tables. Cross-domain
writes go through the owning domain's service or an outbox event (CLAUDE.md,
"Backend architecture"), because the service is where that domain's invariants,
version bumps and lock order live. Two ways of skipping it are checked here,
because nothing else in CI notices either - the code type-checks and the tests pass:

* importing another domain's ``repository``, in any spelling;
* constructing another domain's model, which inserts a row the owner never saw.

    PYTHONPATH=. python backend_v2/scripts/check_domain_boundaries.py
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterator
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
PACKAGE = ("backend_v2", "app")

def _app_relative(target: tuple[str, ...]) -> tuple[str, ...] | None:
    if target[:2] == PACKAGE:
        return target[2:]
    if target[:1] == ("app",):
        return target[1:]
    return None


def _imports(path: Path, app: Path) -> Iterator[tuple[ast.Import | ast.ImportFrom, tuple[str, ...], str]]:
    """Every imported name as (node, app-relative dotted target, local binding)."""
    relative = path.relative_to(app)
    module_path = PACKAGE + relative.with_suffix("").parts
    if relative.name == "__init__.py":
        module_path = module_path[:-1] + ("__init__",)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = module_path[: len(module_path) - node.level] if node.level else ()
            module = base + tuple(node.module.split(".")) if node.module else base
            for alias in node.names:
                target = _app_relative(module + (alias.name,))
                if target is not None:
                    yield node, target, alias.asname or alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                target = _app_relative(tuple(alias.name.split(".")))
                if target is not None:
                    yield node, target, alias.asname or alias.name.split(".")[0]


def _domain_files(app: Path) -> Iterator[tuple[Path, Path, str]]:
    for path in sorted(app.rglob("*.py")):
        relative = path.relative_to(app)
        if len(relative.parts) >= 2:
            yield path, relative, relative.parts[0]


def violations(app: Path = APP) -> list[str]:
    found: list[str] = []
    for path, relative, domain in _domain_files(app):
        for node, target, _ in _imports(path, app):
            if "repository" in target[1:2] and target[0] != domain:
                found.append(f"{relative}:{node.lineno}: {domain} imports {target[0]}.repository")
    return found


def constructions(app: Path = APP) -> list[tuple[str, int, str]]:
    """(file, line, "<domain>.<Model>") for every call that builds another domain's model."""
    found: list[tuple[str, int, str]] = []
    for path, relative, domain in _domain_files(app):
        classes: dict[str, str] = {}
        modules: dict[str, str] = {}
        for _, target, binding in _imports(path, app):
            if len(target) >= 2 and target[1] == "models" and target[0] not in (domain, "core"):
                if len(target) == 2:
                    modules[binding] = target[0]
                elif len(target) == 3:
                    classes[binding] = f"{target[0]}.{target[2]}"
        if not classes and not modules:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id in classes:
                found.append((relative.as_posix(), node.lineno, classes[func.id]))
            elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in modules:
                found.append((relative.as_posix(), node.lineno, f"{modules[func.value.id]}.{func.attr}"))
    return found


def construction_problems(app: Path = APP) -> list[str]:
    return [
        f"{path}:{line}: constructs {model}; create it through the owning domain's service"
        for path, line, model in constructions(app)
    ]


def main() -> int:
    found = violations()
    problems = construction_problems()
    for line in [*found, *problems]:
        print(line)
    if found or problems:
        print(f"{len(found)} cross-domain repository import(s), {len(problems)} cross-domain model construction(s).")
        return 1
    print("No cross-domain repository imports or model constructions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
