from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from backend_v2.app.research.package_import import (
    _managed_package_match,
    _project_package_meta,
)
from backend_v2.app.research.package_validation import (
    TRUSTED_BUILTIN_PACKAGE_CHECKSUMS,
    normalize_research_package,
    research_package_checksum,
)

ROOT = Path(__file__).resolve().parents[2]
COMMITTED_PACKAGE = ROOT / "frontend" / "public" / "research-packages" / "pd1-demo-v1.json"


def _load() -> tuple[dict, str]:
    return normalize_research_package(json.loads(COMMITTED_PACKAGE.read_text()))


def test_committed_pd1_package_matches_server_trust_manifest() -> None:
    package, schema_version = _load()

    assert schema_version == "1.1"
    assert package["package_id"] == "pd1-demo-v1"
    assert package["license"] == "CC-BY-4.0"
    assert package["synthetic_demo"] is True
    assert [project["id"] for project in package["projects"]] == ["PD1"]
    assert len(package["references"]) == 12
    assert len(package["edges"]) == 4
    assert package["candidates"] == []
    assert TRUSTED_BUILTIN_PACKAGE_CHECKSUMS[package["package_id"]] == research_package_checksum(package)


def _as_javascript_sends_it(value: object) -> object:
    """Mimic JSON.stringify losing the float/int distinction."""
    if isinstance(value, dict):
        return {key: _as_javascript_sends_it(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_as_javascript_sends_it(item) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value == int(value):
        return int(value)
    return value


def test_trust_manifest_survives_browser_json_round_trip() -> None:
    source = json.loads(COMMITTED_PACKAGE.read_text())
    package, _ = normalize_research_package(source)
    posted, _ = normalize_research_package(_as_javascript_sends_it(source))

    assert research_package_checksum(posted) == research_package_checksum(package)
    assert TRUSTED_BUILTIN_PACKAGE_CHECKSUMS[package["package_id"]] == research_package_checksum(posted)


def test_public_builtin_package_family_does_not_match_private_packages() -> None:
    assert _managed_package_match("pd1-demo-v1", "pd1-demo-v2")
    assert not _managed_package_match("private-package-v1", "pd1-demo-v1")
    assert _project_package_meta(
        SimpleNamespace(localized_content={"package": {"id": "package"}})
    ) == {"id": "package"}
    assert _project_package_meta(SimpleNamespace(localized_content="invalid")) == {}
