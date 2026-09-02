#!/usr/bin/env python3
"""Fail closed when the public repository contains unapproved data."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path("frontend/public/research-packages/pd1-demo-v1.json")
FIXTURE_ROOT = Path("examples/migration-fixtures/pd1")
ALLOWED_FIXTURES = {
    FIXTURE_ROOT / "DATA_CARD.md",
    FIXTURE_ROOT / "manifest.json",
    FIXTURE_ROOT / "structures/PD1Binder_a0172.pdb",
    FIXTURE_ROOT / "structures/PD1Binder_b1923.pdb",
    FIXTURE_ROOT / "structures/PD1Binder_c4361.pdb",
    FIXTURE_ROOT / "complexes/PD1Binder_a0172_complex.pdb",
    FIXTURE_ROOT / "complexes/PD1Binder_b1923_complex.pdb",
    FIXTURE_ROOT / "complexes/PD1Binder_c4361_complex.pdb",
}
FORBIDDEN_ROOTS = (Path("analysis"), Path("backend_v2/data"))
FORBIDDEN_SUFFIXES = {".7z", ".backup", ".dump", ".parquet", ".sqlite", ".tar", ".tgz", ".zip"}
SECRET_PATTERNS = {
    "AWS access key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(rb"gh[pousr]_[A-Za-z0-9_]{30,}"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
MAX_FILE_BYTES = 10 * 1024 * 1024
PUBLICATION_TEXT_ROOTS = (Path("docs"),)
PUBLICATION_TEXT_FILES = {Path("README.md"), Path("README.zh-CN.md"), Path("CLAUDE.md")}
FORBIDDEN_PUBLICATION_MARKERS = {
    "missing private status document": b"docs/refactor/CURRENT_STATE",
    "private demo checkout path": b"/mnt/e/BDA-demo",
    "user-specific cluster path": b"/work/" + b"bme-" + b"sunzr/",
    "private cluster-sync snapshot": b"backups/cluster-sync/",
    "private data snapshot index": b"BDA_DATA_INDEX_",
    "worktree recovery inventory": b"worktree-recovery/",
    "private project run identifier": b"SweetProtein_" + b"RFdiffusion_100x2_20260626",
    "private stash reference": b"stash@{",
    "unmerged branch as product truth": b"codex/autopilot-campaigns-wip",
}
FORBIDDEN_REPOSITORY_MARKERS = {
    "private research package identifier": b"protein_knowledge_" + b"pain_targets",
    "private cannabinoid design report": b"CANNABINOID_" + b"DESIGN_REASONING",
    "private cannabinoid phase report": b"CANNABINOID_" + b"PHASE2",
    "private project run identifier": b"SweetProtein_" + b"RFdiffusion_100x2_20260626",
}


def sha256(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def repository_files() -> set[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {Path(line) for line in result.stdout.splitlines() if line}


def is_publication_text(path: Path) -> bool:
    return path in PUBLICATION_TEXT_FILES or any(path.is_relative_to(root) for root in PUBLICATION_TEXT_ROOTS)


def validate_publication_text(path: Path, content: bytes, errors: list[str]) -> None:
    if not is_publication_text(path) or path.suffix.lower() not in {".md", ".json"}:
        return
    for description, marker in FORBIDDEN_PUBLICATION_MARKERS.items():
        if marker in content:
            errors.append(f"{description} is forbidden in public documentation: {path}")


#: Any personal cluster account, not just this project owner's. The rule was always
#: "a user-specific cluster account is forbidden", but it was written as one literal
#: string, so three other people's accounts passed it and shipped in v0.1.0-alpha.1 and
#: v0.1.0-alpha.2. They are deliberately not spelled out here: this file is itself
#: scanned, and naming them would be one more public copy.
CLUSTER_ACCOUNT = re.compile(rb"/work/bme-[a-z]+")

#: Where those accounts already are, recorded 2026-09-02 with the count at that date.
#: This is a freeze, not an approval: the paths are still someone's account name in a
#: public repository, and the fix is to supply them as site configuration - see
#: `docs/QM_CLUSTER_OPERATION_RULES.md` section 8. Listing them here stops the set from growing while
#: that work is scoped, and every entry has to be deleted rather than edited, so the
#: exemption cannot quietly widen.
#:
#: The alembic files are the reason this is a freeze at all. They are applied history:
#: rewriting a migration that has run against a database breaks `alembic check` and
#: leaves every migrated deployment describing a revision that no longer exists. The
#: paths there are inside executed command templates, so removing them is a change to
#: how dispatch resolves software roots, not a text edit.
CLUSTER_ACCOUNT_EXEMPT: dict[str, int] = {
    "backend_v2/alembic/versions/0021_register_proteinhunter.py": 5,
    "backend_v2/alembic/versions/0024_plugins_point_at_qm.py": 14,
    "backend_v2/alembic/versions/0025_qm_paths_verified.py": 13,
    "backend_v2/alembic/versions/0026_rfd3_and_af3.py": 4,
    "backend_v2/alembic/versions/0028_superfold_af3_real_runs.py": 2,
    "backend_v2/alembic/versions/0029_proteinhunter_sampling.py": 2,
    "backend_v2/alembic/versions/0046_workflow_plugin_ports.py": 5,
    "backend_v2/tests/test_qm_plugin_commands.py": 6,
    "backend_v2/tests/test_workflow_plugin_ports_migration.py": 2,
    "qm-scripts/library/TUTORIAL.md": 4,
    "qm-scripts/library/catalog.json": 2,
    "qm-scripts/library/examples/01-backbone-design/rfdiffusion-binder.json": 2,
    "qm-scripts/library/examples/02-sequence-design/proteinmpnn.json": 2,
    "qm-scripts/library/examples/03-structure-prediction/alphafold2.json": 7,
    "qm-scripts/library/examples/03-structure-prediction/alphafold3.json": 1,
    "qm-scripts/plugins/bindcraft/README.md": 1,
    "qm-scripts/plugins/boltz/README.md": 2,
    "qm-scripts/plugins/proteinhunter-boltz/README.md": 2,
    "qm-scripts/plugins/proteinmpnn/README.md": 1,
    "qm-scripts/plugins/registry.json": 12,
    "qm-scripts/plugins/rfdiffusion/README.md": 2,
    "qm-scripts/plugins/rfdiffusion3/README.md": 2,
    "qm-scripts/plugins/rosetta/README.md": 1,
    "qm-scripts/plugins/superfold/README.md": 1,
}


def validate_repository_text(path: Path, content: bytes, errors: list[str]) -> None:
    """Reject exact private identifiers while allowing generic research capabilities."""
    for description, marker in FORBIDDEN_REPOSITORY_MARKERS.items():
        if marker in content:
            errors.append(f"{description} is forbidden in the public repository: {path}")

    found = len(CLUSTER_ACCOUNT.findall(content))
    if not found:
        return
    allowed = CLUSTER_ACCOUNT_EXEMPT.get(path.as_posix())
    if allowed is None:
        errors.append(
            f"personal cluster account is forbidden in the public repository: {path}. "
            "Cluster software roots are site configuration; do not commit an account path. "
            "See docs/QM_CLUSTER_OPERATION_RULES.md section 8."
        )
    elif found > allowed:
        # A ratchet in one direction only: the recorded count may fall, and when it
        # reaches zero the entry is deleted. It may never rise.
        errors.append(
            f"{path}: personal cluster account references grew from {allowed} to {found}. "
            "This set is frozen and may only shrink."
        )


def validate_package(errors: list[str]) -> None:
    payload = json.loads((ROOT / PACKAGE).read_text())
    if payload.get("package_id") != "pd1-demo-v1" or payload.get("schema_version") != "1.1":
        errors.append("PD1 package ID/schema version changed without updating the public contract")
    if payload.get("license") != "CC-BY-4.0" or payload.get("synthetic_demo") is not True:
        errors.append("PD1 package must remain CC-BY-4.0 and explicitly synthetic")
    if [item.get("id") for item in payload.get("projects", [])] != ["PD1"]:
        errors.append("the public research package must contain exactly the PD1 project")
    if payload.get("candidates") != []:
        errors.append("candidate results belong in the synthetic fixture manifest, not curated evidence")
    if len(payload.get("references", [])) != 12 or len(payload.get("edges", [])) != 4:
        errors.append("PD1 evidence cardinality changed; publish a reviewed package version")
    package_blob = json.dumps(payload, ensure_ascii=False).encode()
    for marker in (
        b"CANN",
        b"INSECT",
        b"PAIN",
        b"all four projects",
        "全部四个项目".encode(),
    ):
        if marker in package_blob:
            errors.append("PD1 package contains an identifier from a removed private project")
            break

    project = payload["projects"][0]
    visible = {item["ref_id"] for item in payload["references"] if item["project_ids"] == ["PD1"]}
    if len(visible) != 12:
        errors.append("every public reference must be uniquely assigned to PD1")
    if any(item["ref_id"] not in visible for item in payload["edges"]):
        errors.append("an evidence edge has an unresolved reference")
    if any(item["reference_id"] not in visible for item in project["structures"]):
        errors.append("a structure has an unresolved reference")


def validate_manifest(errors: list[str]) -> None:
    manifest = json.loads((ROOT / FIXTURE_ROOT / "manifest.json").read_text())
    if manifest.get("package_file_sha256") != sha256(PACKAGE):
        errors.append("PD1 package raw checksum does not match its manifest")
    if manifest.get("synthetic_demo") is not True or manifest.get("license") != "CC-BY-4.0":
        errors.append("PD1 fixture manifest must remain CC-BY-4.0 and synthetic")
    candidates = manifest.get("candidates", [])
    if [item.get("candidate_id") for item in candidates] != ["a0172", "b1923", "c4361"]:
        errors.append("PD1 fixture candidate allowlist changed")
    for candidate in candidates:
        if candidate.get("classification") != "synthetic_demo":
            errors.append(f"{candidate.get('candidate_id')} is not classified as synthetic_demo")
        for kind in ("structure", "complex"):
            record = candidate[kind]
            path = FIXTURE_ROOT / record["path"]
            if path not in ALLOWED_FIXTURES or sha256(path) != record["sha256"]:
                errors.append(f"fixture checksum/path mismatch: {path}")


def main() -> int:
    errors: list[str] = []
    files = repository_files()
    research_packages = {path for path in files if path.parent == PACKAGE.parent}
    fixtures = {path for path in files if path.is_relative_to(FIXTURE_ROOT)}
    if research_packages != {PACKAGE}:
        errors.append(f"unexpected public research package files: {sorted(map(str, research_packages))}")
    if fixtures != ALLOWED_FIXTURES:
        errors.append(f"unexpected or missing PD1 fixture files: {sorted(map(str, fixtures ^ ALLOWED_FIXTURES))}")

    for path in sorted(files):
        if any(path == root or path.is_relative_to(root) for root in FORBIDDEN_ROOTS):
            errors.append(f"private data root is forbidden: {path}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"archive/database artifact is forbidden: {path}")
        absolute = ROOT / path
        if not absolute.is_file():
            continue
        if absolute.stat().st_size > MAX_FILE_BYTES:
            errors.append(f"file exceeds 10 MiB public limit: {path}")
            continue
        content = absolute.read_bytes()
        validate_publication_text(path, content, errors)
        validate_repository_text(path, content, errors)
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                errors.append(f"possible {name} in {path}")

    validate_package(errors)
    validate_manifest(errors)
    if errors:
        print("Public data gate failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Public data gate passed: one PD1 package, six checksummed synthetic fixtures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
