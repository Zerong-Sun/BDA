"""Pure helpers from `research.package_import`, tested without the data store.

The package-import suite that exercised these needs research working data, so it
skips on CI and on any clone — which left these defensive branches uncovered in
exactly the environment the coverage gate runs in. They are pure functions over
a row, so they need no fixture at all.
"""

from __future__ import annotations

from backend_v2.app.projects.models import Project
from backend_v2.app.research.package_import import (
    BUILTIN_RESEARCH_PACKAGE_PREFIXES,
    _managed_package_match,
    _project_package_meta,
)


def _project(localized_content: object) -> Project:
    """An in-memory row. Never flushed, so no session and no NOT NULL to satisfy."""
    return Project(localized_content=localized_content)


def test_package_meta_reads_the_nested_package_block() -> None:
    project = _project({"package": {"id": "pkg-1", "version": 3}})
    assert _project_package_meta(project) == {"id": "pkg-1", "version": 3}


def test_package_meta_tolerates_content_that_is_not_a_mapping() -> None:
    """`localized_content` is a JSON column: a row written by an older importer,
    or by hand, can hold a list or a string. Reading it must not raise, because
    the caller is deciding whether to *adopt* that project."""
    for content in ([], "not-a-dict", None, 42):
        assert _project_package_meta(_project(content)) == {}


def test_package_meta_tolerates_a_package_key_that_is_not_a_mapping() -> None:
    assert _project_package_meta(_project({"package": ["wrong", "shape"]})) == {}
    assert _project_package_meta(_project({"package": None})) == {}


def test_package_meta_is_empty_when_there_is_no_package_block() -> None:
    assert _project_package_meta(_project({"name": {"en": "A project"}})) == {}


def test_managed_match_accepts_an_exact_package_id() -> None:
    assert _managed_package_match("pkg-42", "pkg-42") is True
    assert _managed_package_match("pkg-42", "pkg-99") is False


def test_managed_match_treats_versions_in_one_builtin_family_as_managed() -> None:
    """Built-in packages are re-published under changing ids, so a row pinned to
    an older built-in id still belongs to the built-in package being imported."""
    older = f"{BUILTIN_RESEARCH_PACKAGE_PREFIXES[0]}-older-build"
    current = f"{BUILTIN_RESEARCH_PACKAGE_PREFIXES[0]}-current-build"
    assert _managed_package_match(older, current) is True
    assert _managed_package_match(older, f"{BUILTIN_RESEARCH_PACKAGE_PREFIXES[1]}-current") is False
    # A user-uploaded package gets no such latitude.
    assert _managed_package_match(older, "user-uploaded-pkg") is False


def test_managed_match_handles_a_missing_row_value() -> None:
    assert _managed_package_match(None, "pkg-42") is False
    assert _managed_package_match(None, f"{BUILTIN_RESEARCH_PACKAGE_PREFIXES[0]}-x") is False
