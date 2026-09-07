"""Audit all workflows; --apply repairs drafts and derives historical runs. No submissions."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend_v2.app import all_models  # noqa: E402,F401
from backend_v2.app.core.database import session_scope
from backend_v2.app.identity.models import User
from backend_v2.app.projects.models import Project
from backend_v2.app.workflows.models import WorkflowRun
from backend_v2.app.workflows.repair import apply_repair, inspect_repair, rollback_repair
from sqlalchemy import select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", type=uuid.UUID)
    parser.add_argument("--batch-id", default=str(uuid.uuid4()))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = {"batch_id": args.batch_id, "applied": args.apply, "items": []}
    with session_scope() as session:
        query = select(WorkflowRun).order_by(WorkflowRun.created_at)
        if args.project_id:
            query = query.where(WorkflowRun.project_id == args.project_id)
        for workflow in list(session.scalars(query)):
            try:
                with session.begin_nested():
                    if args.rollback:
                        item = {
                            "workflow_id": str(workflow.id),
                            "restored": rollback_repair(session, workflow, args.batch_id) if args.apply else False,
                        }
                    elif args.apply:
                        item = apply_repair(
                            session,
                            workflow,
                            args.batch_id,
                            session.get(User, workflow.created_by),
                            session.get(Project, workflow.project_id),
                        )
                    else:
                        item = inspect_repair(session, workflow)
                    report["items"].append(item)
            except Exception as exc:
                report["items"].append({"workflow_id": str(workflow.id), "error": str(exc)})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
