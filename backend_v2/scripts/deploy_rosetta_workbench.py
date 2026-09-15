"""Install the new native Rosetta declaration without changing legacy deployments or jobs.

Defaults to a read-only dry run. Runtime validation remains unproven until a real
Rosetta run supports this exact declaration fingerprint.
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.audit.service import record_audit
from backend_v2.app.core.database import SessionFactory, set_request_rls_context
from backend_v2.app.identity.models import User
from backend_v2.app.registry.models import ModelPlugin
from backend_v2.app.registry.plugin_manifest import PluginManifestCatalog
from backend_v2.app.registry.schemas import PluginDeploymentCreate, PluginSiteOverrides
from backend_v2.app.registry.service import deploy_plugin_manifest
from backend_v2.app.registry.site_runtime import resolve_plugin_runtime
from backend_v2.app.registry.tasks import _model_plugin_errors
from sqlalchemy import select, text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--actor-id", required=True, type=uuid.UUID)
    ap.add_argument("--runtime-root", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    manifest = next(
        m
        for m in PluginManifestCatalog(Path(__file__).resolve().parents[1] / "plugin_manifests").manifests()
        if m.plugin_key == "Rosetta" and m.plugin_version == "2024.09-bda.1"
    )
    payload = PluginDeploymentCreate(
        manifest_id=manifest.manifest_id,
        plugin_version=manifest.plugin_version,
        checksum=manifest.checksum_sha256,
        site_overrides=PluginSiteOverrides(runtime_root=args.runtime_root),
    )
    with SessionFactory() as s:
        if not args.apply:
            s.execute(text("SET TRANSACTION READ ONLY"))
        actor = s.get(User, args.actor_id)
        if actor is None or not actor.enabled or actor.role != "admin":
            raise ValueError("An enabled administrator actor is required")
        set_request_rls_context(s, user_id=actor.id, is_global_admin=True)
        existing = list(s.scalars(select(ModelPlugin).where(ModelPlugin.plugin_key == "Rosetta")))
        legacy = {
            str(p.id): {
                "version": p.version,
                "plugin_version": p.plugin_version,
                "command": p.command,
                "parameters": p.parameter_schema,
                "enabled": p.enabled,
            }
            for p in existing
            if p.plugin_version != manifest.plugin_version
        }
        report = {
            "plugin_key": "Rosetta",
            "plugin_version": manifest.plugin_version,
            "checksum": manifest.checksum_sha256,
            "parameters": len(manifest.parameter_schema["properties"]),
            "legacy_count": len(legacy),
            "compute_jobs_submitted": 0,
        }
        if not args.apply:
            print(json.dumps({**report, "status": "validated_no_writes"}, ensure_ascii=False))
            return 0
        plugin = deploy_plugin_manifest(s, manifest, payload)
        errors = _model_plugin_errors(plugin)
        if errors:
            raise ValueError(errors)
        runtime = resolve_plugin_runtime(plugin, backend="lsf")
        if not any(line.startswith("export BDA_PLUGIN_ROOT=") for line in runtime["runtime_setup"]):
            raise ValueError("Missing resolved runtime root")
        if plugin.validation_status != "valid":
            plugin.validation_status = "valid"
            plugin.validation_errors = []
            plugin.validated_at = datetime.now(UTC)
        record_audit(
            s,
            action="registry.model_plugin.deploy",
            entity_type="model_plugin",
            entity_id=plugin.id,
            actor_id=actor.id,
            payload={
                "manifest_id": manifest.manifest_id,
                "plugin_version": manifest.plugin_version,
                "checksum_sha256": manifest.checksum_sha256,
                "deployment_status": plugin.deployment_status,
                "source": "deploy_rosetta_workbench",
            },
        )
        s.commit()
        for old_id, before in legacy.items():
            p = s.get(ModelPlugin, uuid.UUID(old_id))
            if p is None:
                raise RuntimeError("Legacy deployment disappeared unexpectedly")
            s.refresh(p)
            after = {
                "version": p.version,
                "plugin_version": p.plugin_version,
                "command": p.command,
                "parameters": p.parameter_schema,
                "enabled": p.enabled,
            }
            if before != after:
                raise RuntimeError("Legacy deployment changed unexpectedly")
        print(
            json.dumps(
                {
                    **report,
                    "status": "installed_declaration_valid",
                    "plugin_id": str(plugin.id),
                    "runtime_validation_status": plugin.runtime_validation_status,
                    "legacy_unchanged": True,
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
