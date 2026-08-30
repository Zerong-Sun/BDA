"""Bind existing workflow nodes to registry plugins, once, for runs no seeder owns.

The seeders now write ``model_plugin_id`` and ``execution_mode`` themselves, so runs they
own are correct after a re-run. Nodes built by hand through the UI are not: they name their
tool in free text and preflight rejects them with ``plugin_snapshot_missing``, which is how
a fully executed route ends up reporting that it cannot run.

Deliberately conservative:

* a node already bound is left alone - this never rebinds;
* a tool name that resolves to no enabled plugin is left unbound and reported, because the
  blocker is true and hiding it is worse than the blocker;
* only names on the explicit manual list become ``manual``. Inferring "unresolvable
  therefore manual" would silently reclassify an unregistered model as a human step.

    python -m backend_v2.scripts.backfill_workflow_node_plugin_bindings --dry-run
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from backend_v2.app.core.database import session_scope
from backend_v2.app.projects.models import Project
from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun
from backend_v2.scripts.workflow_plugin_binding import (
    MANUAL_STAGE_PLUGINS,
    resolve_model_plugin,
)
from sqlalchemy import select


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-legacy-id",
        default=None,
        help="Limit to one project. Default: every project.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def backfill(project_legacy_id: str | None, dry_run: bool) -> dict:
    outcome: Counter[str] = Counter()
    unresolved: Counter[str] = Counter()
    changed_nodes: list[dict] = []

    with session_scope() as session:
        query = select(WorkflowNode)
        if project_legacy_id:
            project = session.scalar(
                select(Project).where(Project.legacy_id == project_legacy_id)
            )
            if project is None:
                raise ValueError(f"project_not_found:{project_legacy_id}")
            run_ids = select(WorkflowRun.id).where(WorkflowRun.project_id == project.id)
            query = query.where(WorkflowNode.workflow_run_id.in_(run_ids))

        for node in session.scalars(query):
            if node.model_plugin_id is not None:
                outcome["already_bound"] += 1
                continue
            if node.model_plugin in MANUAL_STAGE_PLUGINS:
                if node.execution_mode != "manual":
                    if not dry_run:
                        node.execution_mode = "manual"
                        node.version += 1
                    changed_nodes.append(
                        {"node_key": node.node_key, "change": "manual", "plugin": node.model_plugin}
                    )
                    outcome["marked_manual"] += 1
                else:
                    outcome["already_manual"] += 1
                continue
            plugin = resolve_model_plugin(session, node.model_plugin)
            if plugin is None:
                outcome["unresolved"] += 1
                unresolved[node.model_plugin] += 1
                continue
            if not dry_run:
                node.model_plugin_id = plugin.id
                node.version += 1
            changed_nodes.append(
                {
                    "node_key": node.node_key,
                    "change": "bound",
                    "plugin": node.model_plugin,
                    "plugin_version": plugin.plugin_version,
                }
            )
            outcome["bound"] += 1

        if dry_run:
            session.rollback()

    return {
        "dry_run": dry_run,
        "summary": dict(outcome),
        # These stay blocked on purpose: a real tool that nobody has registered.
        "unresolved_plugin_names": dict(unresolved),
        "changed": changed_nodes,
    }


def main() -> int:
    args = arguments()
    report = backfill(args.project_legacy_id, args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
