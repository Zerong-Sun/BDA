from __future__ import annotations

from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from .models import WorkflowNode, WorkflowRun
from .repository import WorkflowRepository
from .schemas import WorkflowCreate, WorkflowLayoutUpdate, WorkflowNodeInput, WorkflowNodeUpdate


def create_workflow(session: Session, project: Project, payload: WorkflowCreate, user: User) -> WorkflowRun:
    graph = {
        "nodes": [node.model_dump(mode="json") for node in payload.nodes],
        "edges": [edge.model_dump(mode="json") for edge in payload.edges],
    }
    if payload.derived_from_id is not None:
        ancestor = session.get(WorkflowRun, payload.derived_from_id)
        if ancestor is None or ancestor.project_id != project.id:
            raise DomainError(
                "workflow_not_found", "The run this one derives from was not found", status_code=404
            )
    workflow = WorkflowRepository(session).add(
        WorkflowRun(
            project_id=project.id,
            name=payload.name.strip(),
            graph=graph,
            created_by=user.id,
            derived_from_id=payload.derived_from_id,
        )
    )
    session.add_all(
        [
            WorkflowNode(
                workflow_run_id=workflow.id,
                node_key=node.key,
                node_type=node.node_type,
                model_plugin=node.model_plugin,
                model_plugin_id=node.model_plugin_id,
                container_image=node.container_image,
                command=node.command,
                queue=node.queue,
                parameters=node.parameters,
                input_bindings=[item.model_dump(mode="json") for item in node.input_bindings],
            )
            for node in payload.nodes
        ]
    )
    session.flush()
    record_audit(
        session,
        action="workflow.create",
        entity_type="workflow_run",
        entity_id=workflow.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return workflow


def replace_workflow_graph(
    session: Session,
    workflow: WorkflowRun,
    payload: WorkflowCreate,
    user: User,
    project: Project,
    expected_version: int,
) -> WorkflowRun:
    if workflow.status != "draft":
        raise DomainError("workflow_locked", "Only draft workflows can be edited", status_code=409)
    if workflow.version != expected_version:
        raise DomainError("version_conflict", "Workflow was modified by another request", status_code=412)
    workflow.name = payload.name.strip()
    workflow.graph = {
        "nodes": [node.model_dump(mode="json") for node in payload.nodes],
        "edges": [edge.model_dump(mode="json") for edge in payload.edges],
    }
    for node in WorkflowRepository(session).nodes(workflow.id):
        session.delete(node)
    session.flush()
    session.add_all(
        [
            WorkflowNode(
                workflow_run_id=workflow.id,
                node_key=node.key,
                node_type=node.node_type,
                model_plugin=node.model_plugin,
                model_plugin_id=node.model_plugin_id,
                container_image=node.container_image,
                command=node.command,
                queue=node.queue,
                parameters=node.parameters,
                input_bindings=[item.model_dump(mode="json") for item in node.input_bindings],
            )
            for node in payload.nodes
        ]
    )
    workflow.version += 1
    record_audit(
        session,
        action="workflow.graph.update",
        entity_type="workflow_run",
        entity_id=workflow.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return workflow


def add_node(
    session: Session, workflow: WorkflowRun, payload: WorkflowNodeInput, expected_version: int
) -> WorkflowNode:
    _require_editable(workflow, expected_version)
    if any(node.node_key == payload.key for node in WorkflowRepository(session).nodes(workflow.id)):
        raise DomainError("workflow_node_exists", "Workflow node key already exists", status_code=409)
    node = WorkflowNode(
        workflow_run_id=workflow.id,
        node_key=payload.key,
        node_type=payload.node_type,
        model_plugin=payload.model_plugin,
        model_plugin_id=payload.model_plugin_id,
        container_image=payload.container_image,
        command=payload.command,
        queue=payload.queue,
        parameters=payload.parameters,
        input_bindings=[item.model_dump(mode="json") for item in payload.input_bindings],
    )
    session.add(node)
    session.flush()
    graph = dict(workflow.graph)
    graph["nodes"] = [*graph.get("nodes", []), payload.model_dump(mode="json")]
    workflow.graph = graph
    workflow.version += 1
    return node


def update_node(
    workflow: WorkflowRun, node: WorkflowNode, payload: WorkflowNodeUpdate, expected_version: int
) -> WorkflowNode:
    _require_editable(workflow, expected_version)
    values = payload.model_dump(exclude_unset=True, exclude={"position"})
    # The graph is a JSON column, so it needs JSON-safe values (UUIDs as strings);
    # the ORM attributes want native types. Dump twice rather than coercing.
    json_values = payload.model_dump(exclude_unset=True, exclude={"position"}, mode="json")
    for field, value in values.items():
        setattr(node, field, json_values[field] if field == "input_bindings" else value)
    node.version += 1
    graph = dict(workflow.graph)
    graph_nodes = []
    for item in graph.get("nodes", []):
        if item.get("key") == node.node_key:
            item = {**item, **json_values}
            if payload.position is not None:
                item["position"] = payload.position
        graph_nodes.append(item)
    graph["nodes"] = graph_nodes
    workflow.graph = graph
    workflow.version += 1
    return node


def delete_node(session: Session, workflow: WorkflowRun, node: WorkflowNode, expected_version: int) -> None:
    _require_editable(workflow, expected_version)
    key = node.node_key
    graph = dict(workflow.graph)
    graph["nodes"] = [item for item in graph.get("nodes", []) if item.get("key") != key]
    graph["edges"] = [
        edge for edge in graph.get("edges", []) if edge.get("source") != key and edge.get("target") != key
    ]
    workflow.graph = graph
    workflow.version += 1
    session.delete(node)


def update_layout(workflow: WorkflowRun, payload: WorkflowLayoutUpdate, expected_version: int) -> dict:
    if workflow.version != expected_version:
        raise DomainError("version_conflict", "Workflow was modified by another request", status_code=412)
    graph = dict(workflow.graph)
    graph["layout"] = payload.model_dump(mode="json")
    workflow.graph = graph
    workflow.version += 1
    return graph


def _require_editable(workflow: WorkflowRun, expected_version: int) -> None:
    if workflow.status != "draft":
        raise DomainError("workflow_locked", "Only draft workflows can be edited", status_code=409)
    if workflow.version != expected_version:
        raise DomainError("version_conflict", "Workflow was modified by another request", status_code=412)
