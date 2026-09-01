from __future__ import annotations

import json
from pathlib import Path

from ..core.config import get_settings
from ..core.problem import DomainError
from .package_validation import normalize_research_package, research_package_checksum

# Public software only ships reviewed packages from this explicit allowlist.
# Private deployments register additional immutable manifests in their own data
# plane without changing this source tree.
BUILTIN_PACKAGES = {("pd1-demo-v1", "1.0.0"): "pd1-demo-v1.json"}


def _package_root() -> Path:
    configured = Path(get_settings().research_package_dir)
    if configured.is_absolute():
        return configured
    candidates = (Path.cwd() / configured, Path(__file__).resolve().parents[3] / configured)
    return next((candidate for candidate in candidates if candidate.is_dir()), candidates[0])


def load_catalog_package(package_id: str, version: str, checksum: str | None = None) -> tuple[dict, str, int]:
    filename = BUILTIN_PACKAGES.get((package_id, version))
    if filename is None:
        raise DomainError("research_package_not_found", "Research package was not found", status_code=404)
    path = _package_root() / filename
    if not path.is_file():
        raise DomainError("research_package_unavailable", "Research package is not installed", status_code=503)
    package, _ = normalize_research_package(json.loads(path.read_text()))
    semantic_checksum = research_package_checksum(package)
    if checksum is not None and checksum != semantic_checksum:
        raise DomainError("research_package_checksum_mismatch", "Research package checksum does not match", status_code=409)
    return package, semantic_checksum, path.stat().st_size


def catalog_packages() -> list[tuple[dict, str, int]]:
    return [load_catalog_package(package_id, version) for package_id, version in BUILTIN_PACKAGES]
