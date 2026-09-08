"""Application services for durable gate preview, inspection and release."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ..core.problem import DomainError
from ..identity.models import User
from ..projects.service import require_project
from .gate_schemas import GatePreview, GateRelease
from .repository import WorkflowRepository


def _workflow(session, workflow_id, user):
    workflow = WorkflowRepository(session).get(workflow_id)
    if workflow is None:
        raise DomainError("workflow_not_found", "Workflow not found", status_code=404)
    require_project(session, workflow.project_id, user)
    return workflow


def _gate_summary(row):
    return {
        "id": str(row.id),
        "edge_id": row.edge_id,
        "target_job_id": str(row.target_job_id) if row.target_job_id else None,
        "status": row.status,
        "version": row.version,
        "revision": row.revision,
        "preview": row.preview,
        "total": len(row.decisions),
        "passed": sum(d["passed"] for d in row.decisions),
        "selected": len(row.selected_ids),
        "selected_ids": row.selected_ids,
        "error": row.error_message,
        "released_by": str(row.released_by) if row.released_by else None,
        "created_at": row.created_at.isoformat(),
        "policy": row.snapshot.get("edge", {}).get("gate"),
        "source_job_id": row.snapshot.get("source_job_id"),
    }


def list_gates(workflow_id: uuid.UUID, session: Session | None = None, user: User | None = None) -> dict:
    assert session is not None and user is not None
    from sqlalchemy import select

    from .models import GateEvaluation

    _workflow(session, workflow_id, user)
    rows = session.scalars(
        select(GateEvaluation)
        .where(GateEvaluation.workflow_run_id == workflow_id)
        .order_by(GateEvaluation.created_at.desc())
    )
    return {"items": [_gate_summary(r) for r in rows]}


def gate_results(
    workflow_id: uuid.UUID,
    gate_id: uuid.UUID,
    q: str = "",
    offset: int = 0,
    limit: int = 100,
    sort_metric: str | None = None,
    descending: bool = True,
    session: Session | None = None,
    user: User | None = None,
) -> dict:
    assert session is not None and user is not None
    from .models import GateEvaluation

    _workflow(session, workflow_id, user)
    gate = session.get(GateEvaluation, gate_id)
    if not gate or gate.workflow_run_id != workflow_id:
        raise DomainError("gate_not_found", "Gate not found", status_code=404)
    by_id = {r["id"]: r for r in gate.snapshot.get("records", [])}
    rows = [{**by_id.get(d["id"], {}), **d, "selected": d["id"] in gate.selected_ids} for d in gate.decisions]
    rows = [
        r
        for r in rows
        if q.lower() in (str(r.get("key", "")) + str(r.get("sequence", "")) + str(r.get("reasons", []))).lower()
    ]
    if sort_metric:
        rows.sort(
            key=lambda r: (
                not isinstance(r.get("metrics", {}).get(sort_metric), (int, float)),
                (-1 if descending else 1)
                * (
                    r.get("metrics", {}).get(sort_metric)
                    if isinstance(r.get("metrics", {}).get(sort_metric), (int, float))
                    else 0
                ),
                r["id"],
            )
        )
    else:
        rows.sort(key=lambda r: r["id"])
    return {"gate": _gate_summary(gate), "items": rows[offset : offset + limit], "total": len(rows)}


def release_gate(
    workflow_id: uuid.UUID,
    gate_id: uuid.UUID,
    payload: GateRelease,
    session: Session | None = None,
    user: User | None = None,
) -> dict:
    assert session is not None and user is not None
    from sqlalchemy import select

    from ..compute.models import Job
    from ..compute.repository import ComputeRepository
    from .models import GateEvaluation

    _workflow(session, workflow_id, user)
    gate = session.scalar(
        select(GateEvaluation)
        .where(GateEvaluation.id == gate_id, GateEvaluation.workflow_run_id == workflow_id)
        .with_for_update()
    )
    if not gate:
        raise DomainError("gate_not_found", "Gate not found", status_code=404)
    chosen = sorted(set(payload.selected_ids))
    if gate.status in {"materializing", "released", "empty"} and sorted(gate.selected_ids) == chosen:
        return _gate_summary(gate)
    if gate.version != payload.version:
        raise DomainError("version_conflict", "Selection is stale; reload gate results", status_code=412)
    target = session.get(Job, gate.target_job_id) if gate.target_job_id else None
    if gate.preview or gate.status != "awaiting_review" or target is None or target.status != "pending":
        raise DomainError("gate_not_waiting", "Gate is not waiting for a selection", status_code=409)
    qualified = {d["id"] for d in gate.decisions if d["passed"]}
    if not set(chosen) <= qualified:
        raise DomainError(
            "gate_selection_invalid", "Select only qualified results from this evaluation", status_code=422
        )
    gate.selected_ids = chosen
    gate.snapshot = {**gate.snapshot, "release_selection": chosen}
    gate.status = "materializing"
    gate.released_by = user.id
    gate.version += 1
    ComputeRepository(session).enqueue("gate.resume", gate.id, project_id=gate.project_id)
    from ..audit.service import record_audit

    project = require_project(session, gate.project_id, user)
    record_audit(
        session,
        action="workflow.gate.release",
        entity_type="workflow_gate",
        entity_id=gate.id,
        project_id=gate.project_id,
        organization_id=project.organization_id,
        actor_id=user.id,
        payload={"selected_ids": chosen, "version": gate.version},
    )
    return _gate_summary(gate)


def retry_gate(
    workflow_id: uuid.UUID, gate_id: uuid.UUID, session: Session | None = None, user: User | None = None
) -> dict:
    assert session is not None and user is not None
    from sqlalchemy import select

    from ..compute.models import Job
    from ..compute.repository import ComputeRepository
    from .models import GateEvaluation

    workflow = _workflow(session, workflow_id, user)
    session.refresh(workflow, with_for_update=True)
    old = session.scalar(
        select(GateEvaluation)
        .where(GateEvaluation.id == gate_id, GateEvaluation.workflow_run_id == workflow_id)
        .with_for_update()
    )
    target = session.get(Job, old.target_job_id) if old and old.target_job_id else None
    if not old or old.status != "error" or (not old.preview and (target is None or target.status != "pending")):
        raise DomainError("gate_not_retryable", "Only a failed gate before dispatch can be retried", status_code=409)
    from .gate_runtime import latest_gate

    newest = latest_gate(session, old.target_job_id, old.edge_id, preview=old.preview, workflow_id=workflow_id)
    if newest.id != old.id:
        return _gate_summary(newest)
    old.status = "superseded"
    from .gate_runtime import next_revision

    revision = next_revision(session, workflow_id, old.edge_id, old.target_job_id)
    resume = "release_selection" in old.snapshot
    row = GateEvaluation(
        project_id=old.project_id,
        workflow_run_id=workflow_id,
        target_job_id=old.target_job_id,
        edge_id=old.edge_id,
        revision=revision,
        preview=old.preview,
        snapshot=dict(old.snapshot) if resume else {k: v for k, v in old.snapshot.items() if k != "records"},
        status="materializing" if resume else "waiting",
        decisions=old.decisions if resume else [],
        selected_ids=old.selected_ids if resume else [],
        released_by=old.released_by if resume else None,
    )
    session.add(row)
    session.flush()
    ComputeRepository(session).enqueue("gate.evaluate", row.id, project_id=row.project_id)
    return _gate_summary(row)


def preview_gate(
    workflow_id: uuid.UUID, edge_id: str, payload: GatePreview, session: Session | None = None, user: User | None = None
) -> dict:
    assert session is not None and user is not None
    from sqlalchemy import select

    from ..compute.models import Job
    from ..compute.repository import ComputeRepository
    from .models import GateEvaluation

    workflow = _workflow(session, workflow_id, user)
    session.refresh(workflow, with_for_update=True)
    edge = next((e for e in workflow.graph.get("edges", []) if e.get("id") == edge_id), None)
    if not edge:
        raise DomainError("connection_not_found", "Connection not found", status_code=404)
    jobs = list(session.scalars(select(Job).where(Job.workflow_run_id == workflow_id).order_by(Job.created_at.desc())))
    target = next((j for j in jobs if j.runtime_spec.get("node_key") == edge["target"]), None)
    source = next(
        (j for j in jobs if j.runtime_spec.get("node_key") == edge["source"] and j.status == "succeeded"), None
    )
    if payload.source_job_id:
        source = session.get(Job, payload.source_job_id)
        source_node = next(
            (n for n in WorkflowRepository(session).nodes(workflow.id) if n.node_key == edge["source"]), None
        )
        if (
            source is None
            or source.project_id != workflow.project_id
            or source.status != "succeeded"
            or source_node is None
            or str(source_node.model_plugin_id) != (source.runtime_spec.get("plugin_snapshot") or {}).get("id")
        ):
            raise DomainError(
                "gate_preview_source_invalid",
                "Choose a completed source job for the same plugin in this project",
                status_code=422,
            )
    if not source:
        raise DomainError("gate_preview_no_results", "Choose an upstream result set for the preview", status_code=409)
    revisions = list(
        session.scalars(
            select(GateEvaluation.revision).where(
                GateEvaluation.workflow_run_id == workflow_id, GateEvaluation.edge_id == edge_id
            )
        )
    )
    row = GateEvaluation(
        project_id=workflow.project_id,
        workflow_run_id=workflow_id,
        target_job_id=target.id if target else None,
        edge_id=edge_id,
        revision=max(revisions, default=0) + 1,
        preview=True,
        snapshot={
            "edge": {**edge, "gate": payload.policy.model_dump(mode="json")},
            "source_job_id": str(source.id),
            "output_policy": next(
                (
                    n.configuration.get("output_policy")
                    for n in WorkflowRepository(session).nodes(workflow_id)
                    if n.node_key == edge["source"]
                ),
                None,
            ),
        },
    )
    session.add(row)
    session.flush()
    ComputeRepository(session).enqueue("gate.evaluate", row.id, project_id=row.project_id)
    return _gate_summary(row)


def preview_sources(session, workflow_id, edge_id, user):
    from sqlalchemy import func, select

    from ..compute.models import Job
    from .models import WorkflowResult

    workflow = _workflow(session, workflow_id, user)
    edge = next((e for e in workflow.graph.get("edges", []) if e.get("id") == edge_id), None)
    if edge is None:
        raise DomainError("connection_not_found", "Connection not found", status_code=404)
    source_node = next(
        (n for n in WorkflowRepository(session).nodes(workflow.id) if n.node_key == edge["source"]), None
    )
    jobs = session.scalars(
        select(Job)
        .where(Job.project_id == workflow.project_id, Job.status == "succeeded")
        .order_by(Job.created_at.desc())
        .limit(200)
    )
    items = []
    for job in jobs:
        snapshot = job.runtime_spec.get("plugin_snapshot") or {}
        if source_node and str(source_node.model_plugin_id) != snapshot.get("id"):
            continue
        count = session.scalar(select(func.count()).select_from(WorkflowResult).where(WorkflowResult.job_id == job.id))
        if count:
            items.append(
                {
                    "id": str(job.id),
                    "node_key": job.runtime_spec.get("node_key"),
                    "attempt": job.attempt_number,
                    "created_at": job.created_at.isoformat(),
                    "count": count,
                }
            )
    return {"items": items}


def script_preview_valid(session, workflow, edge, output_policy):
    import uuid

    from .gate_schemas import GatePolicy
    from .models import GateEvaluation

    policy = GatePolicy.model_validate(edge.get("gate") or {})
    if not policy.script and not (output_policy or {}).get("script"):
        return True
    if not policy.script_preview_id:
        return False
    preview = session.get(GateEvaluation, uuid.UUID(str(policy.script_preview_id)))
    if (
        preview is None
        or preview.workflow_run_id != workflow.id
        or preview.edge_id != edge.get("id")
        or not preview.preview
        or preview.status != "previewed"
    ):
        return False

    def clean(p):
        return {
            k: v
            for k, v in GatePolicy.model_validate(p or {}).model_dump(mode="json").items()
            if k not in {"script_preview_id", "configured"}
        }

    return clean(preview.snapshot["edge"]["gate"]) == clean(edge.get("gate")) and clean(
        preview.snapshot.get("output_policy")
    ) == clean(output_policy)
