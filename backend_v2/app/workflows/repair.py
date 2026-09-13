"""Auditable, repeatable workflow repair. Historical runs are never rewritten."""

from __future__ import annotations

import copy
import uuid

from sqlalchemy import select

from .connections import canonical_edges
from .models import WorkflowRun
from .repository import WorkflowRepository
from .schemas import WorkflowCreate, WorkflowNodeInput
from .service import create_workflow


def inspect_repair(session, workflow):
    nodes = WorkflowRepository(session).nodes(workflow.id)
    execution = workflow.graph.get("edges", [])
    ids = {str(n.id): n.node_key for n in nodes}

    def signature(e):
        return (ids.get(e.get("source"), e.get("source")), ids.get(e.get("target"), e.get("target")))

    issues = []
    layout_edges = workflow.graph.get("layout", {}).get("edges", [])
    if layout_edges and {signature(e) for e in layout_edges} != {signature(e) for e in execution}:
        issues.append("layout_execution_conflict: retained execution graph; resolve visual-only connections")
    edges = [dict(e) for e in execution]
    for node in nodes:
        for b in node.input_bindings:
            if b.get("source") != "upstream":
                continue
            matches = [e for e in edges if signature(e) == (b["from_node"], node.node_key)]
            if not matches:
                edges.append(
                    {
                        "source": b["from_node"],
                        "target": node.node_key,
                        "source_port": b["from_port"],
                        "target_port": b["port"],
                    }
                )
            elif len(matches) == 1 and not matches[0].get("source_port") and not matches[0].get("target_port"):
                matches[0].update(source_port=b["from_port"], target_port=b["port"])
            elif not any(e.get("source_port") == b["from_port"] and e.get("target_port") == b["port"] for e in matches):
                issues.append(f"binding_execution_conflict:{node.node_key}.{b['port']}")
    # Stable IDs make report/application comparisons and retries deterministic.
    for index, edge in enumerate(edges):
        edge.setdefault("id", str(uuid.uuid5(workflow.id, f"connection:{index}:{signature(edge)}")))
    normalized = canonical_edges(session, nodes, edges, strict=False)
    has_conflicts = bool(issues)
    for edge in normalized:
        if has_conflicts:
            edge["gate"]["configured"] = False
        if not edge["gate"]["configured"]:
            issues.append(f"gate_configuration_required:{edge['id']}")
    return {
        "workflow_id": str(workflow.id),
        "version": workflow.version,
        "action": "repair_draft" if workflow.status == "draft" else "derive_draft",
        "edges": normalized,
        "issues": issues,
    }


def apply_repair(session, workflow, batch_id, user, project):
    marker = workflow.graph.get("gate_migration") or {}
    if marker:
        return {"workflow_id": str(workflow.id), "action": "already_repaired"}
    existing = next(
        (
            w
            for w in session.scalars(select(WorkflowRun).where(WorkflowRun.derived_from_id == workflow.id))
            if w.graph.get("gate_migration", {}).get("source_id") == str(workflow.id)
        ),
        None,
    )
    if existing:
        return {"workflow_id": str(workflow.id), "action": "already_derived", "draft_id": str(existing.id)}
    report = inspect_repair(session, workflow)
    nodes = WorkflowRepository(session).nodes(workflow.id)
    backup = {
        "graph": copy.deepcopy(workflow.graph),
        "nodes": [
            {
                "id": str(n.id),
                "input_bindings": copy.deepcopy(n.input_bindings),
                "configuration": copy.deepcopy(n.configuration),
            }
            for n in nodes
        ],
    }
    if workflow.status != "draft":
        payload = WorkflowCreate(
            name=f"{workflow.name} · gated",
            derived_from_id=workflow.id,
            nodes=[
                WorkflowNodeInput(
                    key=n.node_key,
                    node_type=n.node_type,
                    model_plugin=n.model_plugin,
                    model_plugin_id=n.model_plugin_id,
                    command=n.command,
                    container_image=n.container_image,
                    queue=n.queue,
                    parameters=n.parameters,
                    configuration=n.configuration,
                    input_bindings=n.input_bindings,
                    position=next(
                        (i.get("position") for i in workflow.graph.get("nodes", []) if i.get("key") == n.node_key), None
                    ),
                )
                for n in nodes
            ],
            edges=report["edges"],
        )
        repaired = create_workflow(session, project, payload, user)
        original_modes = {n.node_key: n.execution_mode for n in nodes}
        for n in WorkflowRepository(session).nodes(repaired.id):
            n.execution_mode = original_modes[n.node_key]
        report["draft_id"] = str(repaired.id)
    else:
        repaired = workflow
        from .connections import initialize_connections

        repaired.graph = {**repaired.graph, "edges": report["edges"]}
        initialize_connections(session, repaired)
    repaired.graph = {
        **repaired.graph,
        "edges": report["edges"],
        "gate_migration": {
            "batch_id": batch_id,
            "source_id": str(workflow.id),
            "issues": report["issues"],
            "backup": backup if repaired.id == workflow.id else None,
            "applied_version": repaired.version + 1,
        },
    }
    repaired.version += 1
    return report


def rollback_repair(session, workflow, batch_id):
    marker = workflow.graph.get("gate_migration") or {}
    if marker.get("batch_id") != batch_id:
        return False
    if workflow.status != "draft" or workflow.version != marker["applied_version"]:
        raise ValueError("Cannot restore a submitted or subsequently edited workflow")
    backup = marker.get("backup")
    if not backup:
        # Derived drafts can be inspected or removed explicitly, never delete their ancestor.
        return False
    by_id = {str(n.id): n for n in WorkflowRepository(session).nodes(workflow.id)}
    for old in backup["nodes"]:
        by_id[old["id"]].input_bindings = old["input_bindings"]
        by_id[old["id"]].configuration = old["configuration"]
    workflow.graph = backup["graph"]
    workflow.version += 1
    return True
