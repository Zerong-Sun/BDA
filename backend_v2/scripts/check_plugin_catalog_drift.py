"""Fail when qm-scripts/library/catalog.json and the model_plugins registry disagree.

There are two descriptions of the same tools in this repository:

* ``model_plugins`` - what the platform dispatches. Authoritative.
* ``qm-scripts/library/catalog.json`` - what ``qm_job.py`` renders for hand submission.

They were authored separately and drifted, with a real cost. RFdiffusion3 already existed as
an enabled plugin row when a catalog entry was added for it "because there was no sanctioned
way to render it" - the same tool described twice, and the second description had to be
re-derived from the cluster. The rule this check enforces is not "delete one" (hand
submission is genuinely needed while a route is being brought up) but "they may not
contradict each other".

    PYTHONPATH=. python backend_v2/scripts/check_plugin_catalog_drift.py qm-scripts/library/catalog.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend_v2.app.core.database import session_scope
from backend_v2.app.registry.models import ModelPlugin
from sqlalchemy import select

#: catalog.json model key -> model_plugins.plugin_key. Explicit because the two use
#: different naming conventions and guessing between them is how the duplication started.
CATALOG_TO_PLUGIN: dict[str, str] = {
    "rfdiffusion": "RFdiffusion",
    "rfdiffusion3": "RFdiffusion3",
    "proteinmpnn": "ProteinMPNN",
    "alphafold2": "AlphaFold2",
    "alphafold3": "AlphaFold 3",
    "boltz": "Boltz",
    "chai1": "Chai-1",
    "bindcraft": "BindCraft",
    "rosetta": "Rosetta",
    "maskrgn": "Mask RGN",
}

SITE_INSTALL = "site-install:"
DEFAULT_CLUSTER_PROFILES = Path("qm-scripts/plugins/registry.json")


def cluster_profile_problems(profile_path: Path, plugins: dict[str, list[ModelPlugin]]) -> list[str]:
    """Every registered plugin/version needs a dated, source-backed QM runbook."""
    if not profile_path.exists():
        return [f"cluster profile registry is missing: {profile_path}"]
    payload = json.loads(profile_path.read_text())
    profiles = payload.get("plugins", [])
    problems: list[str] = []
    if not isinstance(profiles, list):
        return [f"{profile_path}: plugins must be an array"]
    keys = [item.get("plugin_key") for item in profiles if isinstance(item, dict)]
    slugs = [item.get("slug") for item in profiles if isinstance(item, dict)]
    if len(keys) != len(set(keys)):
        problems.append("cluster profiles contain duplicate plugin_key values")
    if len(slugs) != len(set(slugs)):
        problems.append("cluster profiles contain duplicate slugs")
    by_key = {item.get("plugin_key"): item for item in profiles if isinstance(item, dict)}
    repo = profile_path.resolve().parents[2]
    for plugin_key, rows in sorted(plugins.items()):
        profile = by_key.get(plugin_key)
        if profile is None:
            problems.append(f"{plugin_key}: registered plugin has no QM cluster runbook profile")
            continue
        versions = set(profile.get("versions", []))
        undocumented = sorted({row.plugin_version for row in rows} - versions)
        if undocumented:
            problems.append(f"{plugin_key}: undocumented registered version(s): {', '.join(undocumented)}")
        if any(row.enabled for row in rows) and profile.get("state") == "disabled":
            problems.append(f"{plugin_key}: enabled registry row contradicts disabled cluster profile")
        if not isinstance(profile.get("submission_authorized"), bool):
            problems.append(f"{plugin_key}: submission_authorized must be a boolean")
        if profile.get("state") in {"disabled", "mixed"} and profile.get("submission_authorized"):
            problems.append(f"{plugin_key}: disabled or mixed profile cannot authorize direct submission")
        doc = profile_path.parent / str(profile.get("slug")) / "README.md"
        if not doc.exists():
            problems.append(f"{plugin_key}: generated runbook is missing: {doc}")
        example = profile.get("example")
        if example and not (repo / str(example)).exists():
            problems.append(f"{plugin_key}: example path does not exist: {example}")
        for observation in profile.get("observations", []):
            if not observation.get("observed_on"):
                problems.append(f"{plugin_key}: cluster observation has no date")
            for source in observation.get("sources", []):
                if not (repo / str(source)).exists():
                    problems.append(f"{plugin_key}: cluster observation source does not exist: {source}")
    return problems


def drift(
    catalog_path: Path,
    require_registered: bool = False,
    cluster_profiles_path: Path = DEFAULT_CLUSTER_PROFILES,
) -> list[str]:
    catalog = json.loads(catalog_path.read_text())
    models = catalog.get("models", catalog)
    problems: list[str] = []
    missing: list[str] = []

    with session_scope() as session:
        plugins: dict[str, list[ModelPlugin]] = {}
        for plugin in session.scalars(select(ModelPlugin)):
            plugins.setdefault(plugin.plugin_key, []).append(plugin)

        for catalog_key, entry in sorted(models.items()):
            plugin_key = CATALOG_TO_PLUGIN.get(catalog_key)
            if plugin_key is None:
                problems.append(f"{catalog_key}: no CATALOG_TO_PLUGIN mapping; add one or remove the catalog entry")
                continue
            rows = plugins.get(plugin_key, [])
            if not rows:
                # Not a contradiction, and not a repository fact: AlphaFold 3, Boltz,
                # Chai-1 and Mask RGN entered the registry through the v1 import rather
                # than through a migration, so a database built only from migrations - CI's,
                # and any new deployment's - legitimately has no row for them. Failing here
                # made the gate red on every pull request for a condition no commit could
                # fix. Use --require-registered against a real deployment, where absence
                # does mean "the catalog offers a model the platform cannot dispatch".
                missing.append(f"{catalog_key}: catalog offers this model but no '{plugin_key}' plugin is registered")
                continue

            # Deliberately NOT compared: catalog `entrypoint` is a repo-relative source
            # path ("src/boltz/main.py") while the plugin command is the installed
            # invocation ("boltz predict"). They describe the same tool at different
            # layers, and equating them produces four failures that are all false.
            if entry.get("available") is not False and not any(row.enabled for row in rows):
                problems.append(
                    f"{catalog_key}: catalog offers this model for submission but every "
                    f"'{plugin_key}' plugin is disabled; mark the catalog entry "
                    f'"available": false or re-enable the plugin'
                )

            commit = str(entry.get("commit", ""))
            if commit.startswith(SITE_INSTALL):
                site_path = commit[len(SITE_INSTALL) :]
                images = {row.container_image for row in rows}
                if site_path not in images:
                    problems.append(
                        f"{catalog_key}: catalog site-install path '{site_path}' matches no "
                        f"'{plugin_key}' container_image ({sorted(images)})"
                    )

        # A plugin with no catalog entry is fine - not every model needs a hand-submission
        # path - so that direction is reported but does not fail.
        unmapped = sorted(set(plugins) - set(CATALOG_TO_PLUGIN.values()))
        if unmapped:
            print(f"[info] registered plugins with no catalog entry: {', '.join(unmapped)}")

        problems.extend(cluster_profile_problems(cluster_profiles_path, plugins))

    if missing:
        for item in missing:
            print(f"[{'FAIL' if require_registered else 'info'}] {item}")
        if require_registered:
            problems.extend(missing)

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path, nargs="?", default=Path("qm-scripts/library/catalog.json"))
    parser.add_argument(
        "--require-registered",
        action="store_true",
        help="Also fail when a catalogued model has no plugin row. For a real deployment, "
        "not for a database built only from migrations.",
    )
    parser.add_argument(
        "--cluster-profiles",
        type=Path,
        default=DEFAULT_CLUSTER_PROFILES,
        help="Per-plugin QM/LSF documentation and dated run ledger.",
    )
    args = parser.parse_args()

    problems = drift(
        args.catalog,
        require_registered=args.require_registered,
        cluster_profiles_path=args.cluster_profiles,
    )
    if problems:
        print(f"[FAIL] {len(problems)} disagreement(s) between catalog.json and model_plugins:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("[OK] catalog.json and model_plugins agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
