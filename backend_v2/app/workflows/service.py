from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from .models import WorkflowNode, WorkflowRun
from .repository import WorkflowRepository
from .schemas import RoutePresentation, WorkflowCreate, WorkflowLayoutUpdate, WorkflowNodeInput, WorkflowNodeUpdate


def update_presentation(
    session: Session, workflow: WorkflowRun, payload: RoutePresentation,
    user: User, project: Project, expected_version: int,
) -> WorkflowRun:
    """Organize existing records without touching nodes, results, gates or status."""
    if workflow.project_id != project.id:
        raise DomainError("workflow_not_found", "Workflow was not found", status_code=404)
    if workflow.version != expected_version:
        raise DomainError("version_conflict", "Workflow was modified by another request", status_code=412)
    previous = {"name": workflow.name, "route_presentation": (workflow.graph or {}).get("route_presentation")}
    presentation = payload.model_dump(mode="json")
    graph = workflow.graph or {}
    stored = graph.get("route_presentation")
    old_presentation = stored if isinstance(stored, dict) else {}
    stored_aliases = old_presentation.get("aliases")
    aliases = [*(stored_aliases if isinstance(stored_aliases, list) else []), *payload.aliases]
    if workflow.name != payload.name:
        aliases.append(workflow.name)
    # Keep the oldest identity and recent names visible; the audit retains the full transition.
    presentation["aliases"] = list(dict.fromkeys(name.strip() for name in aliases if isinstance(name, str) and name.strip()))
    if len(presentation["aliases"]) > 30:
        presentation["aliases"] = presentation["aliases"][:1] + presentation["aliases"][-29:]
    stored_localized = graph.get("localized_content")
    localized = {**(stored_localized if isinstance(stored_localized, dict) else {}), "name": {"zh": payload.name, "en": payload.name_en}}
    if graph.get("route_presentation") == presentation and workflow.name == payload.name and graph.get("localized_content") == localized:
        return workflow
    workflow.name = payload.name
    workflow.graph = {**graph, "route_presentation": presentation, "localized_content": localized}
    workflow.version += 1
    record_audit(session, action="workflow.presentation.update", entity_type="workflow_run",
        entity_id=workflow.id, project_id=project.id, organization_id=project.organization_id,
        actor_id=user.id, payload={"before": previous, "after": presentation})
    session.flush()
    return workflow


def create_workflow(session: Session, project: Project, payload: WorkflowCreate, user: User) -> WorkflowRun:
    graph: dict[str, Any] = {
        "nodes": [node.model_dump(mode="json") for node in payload.nodes],
        "edges": [edge.model_dump(mode="json") for edge in payload.edges],
    }
    if payload.compute_backend is not None:
        graph["compute_backend"] = payload.compute_backend
    if payload.derived_from_id is not None:
        ancestor = session.get(WorkflowRun, payload.derived_from_id)
        if ancestor is None or ancestor.project_id != project.id:
            raise DomainError("workflow_not_found", "The run this one derives from was not found", status_code=404)
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
                execution_mode=node.execution_mode,
                node_type=node.node_type,
                model_plugin=node.model_plugin,
                model_plugin_id=node.model_plugin_id,
                container_image=node.container_image,
                command=node.command,
                queue=node.queue,
                parameters=node.parameters,
                configuration=node.configuration,
                input_bindings=[item.model_dump(mode="json") for item in node.input_bindings],
            )
            for node in payload.nodes
        ]
    )
    session.flush()
    from .connections import initialize_connections

    initialize_connections(session, workflow)
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
    display = {key: workflow.graph[key] for key in ("route_presentation", "localized_content") if key in workflow.graph}
    if "route_presentation" in display and payload.name.strip() != workflow.name:
        raise DomainError("workflow_presentation_rename_required", "Rename an organized route through its presentation endpoint", status_code=409)
    workflow.name = payload.name.strip()
    backend = payload.compute_backend or workflow.graph.get("compute_backend")
    workflow.graph = {
        **display,
        "nodes": [node.model_dump(mode="json") for node in payload.nodes],
        "edges": [edge.model_dump(mode="json") for edge in payload.edges],
    }
    if backend:
        workflow.graph = {**workflow.graph, "compute_backend": backend}
    for node in WorkflowRepository(session).nodes(workflow.id):
        session.delete(node)
    session.flush()
    session.add_all(
        [
            WorkflowNode(
                workflow_run_id=workflow.id,
                node_key=node.key,
                execution_mode=node.execution_mode,
                node_type=node.node_type,
                model_plugin=node.model_plugin,
                model_plugin_id=node.model_plugin_id,
                container_image=node.container_image,
                command=node.command,
                queue=node.queue,
                parameters=node.parameters,
                configuration=node.configuration,
                input_bindings=[item.model_dump(mode="json") for item in node.input_bindings],
            )
            for node in payload.nodes
        ]
    )
    session.flush()
    from .connections import initialize_connections

    initialize_connections(session, workflow)
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
        execution_mode=payload.execution_mode,
        node_type=payload.node_type,
        model_plugin=payload.model_plugin,
        model_plugin_id=payload.model_plugin_id,
        container_image=payload.container_image,
        command=payload.command,
        queue=payload.queue,
        parameters=payload.parameters,
        configuration=payload.configuration,
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
    if payload.configuration is not None:
        old_script = (node.configuration or {}).get("script")
        if old_script and old_script != payload.configuration.get("script"):
            payload.configuration = {
                **payload.configuration,
                "script_history": [*(node.configuration or {}).get("script_history", []), old_script],
            }
        from .assistance import validate_configuration

        validate_configuration(payload.configuration)
    plugin_changed = "model_plugin_id" in payload.model_fields_set and payload.model_plugin_id != node.model_plugin_id
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
    if plugin_changed:
        # Keep authored thresholds for review, but never reuse their approval against
        # a different model's metrics/ports. Ordering-only edges have no data contract.
        graph["edges"] = [
            {**edge, "gate": {**(edge.get("gate") or {}), "configured": False, "script_preview_id": None}}
            if node.node_key in (edge.get("source"), edge.get("target"))
            and (edge.get("gate") or {}).get("mode") != "dependency"
            else edge
            for edge in graph.get("edges", [])
        ]
    workflow.graph = graph
    workflow.version += 1
    return node


def delete_node(session: Session, workflow: WorkflowRun, node: WorkflowNode, expected_version: int) -> None:
    _require_editable(workflow, expected_version)
    key = node.node_key
    for sibling in WorkflowRepository(session).nodes(workflow.id):
        sibling.input_bindings = [b for b in sibling.input_bindings if b.get("from_node") != key]
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
    graph["layout"] = {"nodes": payload.nodes}
    positions = {str(item.get("id")): item.get("position") for item in payload.nodes}
    graph["nodes"] = [
        {**item, **({"position": positions[item.get("key")]} if item.get("key") in positions else {})}
        for item in graph.get("nodes", [])
    ]
    workflow.graph = graph
    workflow.version += 1
    return graph


def _require_editable(workflow: WorkflowRun, expected_version: int) -> None:
    if workflow.status != "draft":
        raise DomainError("workflow_locked", "Only draft workflows can be edited", status_code=409)
    if workflow.version != expected_version:
        raise DomainError("version_conflict", "Workflow was modified by another request", status_code=412)
