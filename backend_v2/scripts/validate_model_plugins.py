"""Run registry declaration validation for every model plugin, synchronously.

``registry_model_plugin_validate`` is a Celery task, so the only way to act on preflight's
"run registry validation" advice was to have a worker running and to enqueue one message
per plugin. Nobody did, which is why all nineteen plugins sat at ``unknown`` indefinitely
and every workflow reported the same warning once per node.

This does the same checks in-process. It validates the *declaration* only - image tag,
non-empty command, JSON Schema well-formedness, port coherence - and says nothing about
whether the model runs; see ``record_plugin_runtime_validation`` for that.

    python -m backend_v2.scripts.validate_model_plugins --dry-run
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from backend_v2.app.core.database import session_scope
from backend_v2.app.registry.models import ModelPlugin
from backend_v2.app.registry.tasks import _model_plugin_errors
from sqlalchemy import select


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", default=None, help="Limit to one plugin_key.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def validate_all(plugin_key: str | None, dry_run: bool) -> dict:
    results: list[dict] = []
    with session_scope() as session:
        query = select(ModelPlugin).order_by(ModelPlugin.plugin_key, ModelPlugin.plugin_version)
        if plugin_key:
            query = query.where(ModelPlugin.plugin_key == plugin_key)
        for plugin in session.scalars(query):
            errors = _model_plugin_errors(plugin)
            status = "valid" if not errors else "invalid"
            changed = plugin.validation_status != status or list(plugin.validation_errors) != errors
            if not dry_run:
                plugin.validation_status = status
                plugin.validation_errors = errors
                plugin.validated_at = datetime.now(UTC)
                if changed:
                    plugin.version += 1
            results.append(
                {
                    "plugin_key": plugin.plugin_key,
                    "plugin_version": plugin.plugin_version,
                    "status": status,
                    "errors": errors,
                    "changed": changed,
                }
            )
        if dry_run:
            session.rollback()
    return {
        "dry_run": dry_run,
        "valid": sum(item["status"] == "valid" for item in results),
        "invalid": sum(item["status"] == "invalid" for item in results),
        "plugins": results,
    }


def main() -> int:
    args = arguments()
    report = validate_all(args.plugin, args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # A malformed declaration is a real defect; make it visible to a caller in CI.
    return 1 if report["invalid"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
