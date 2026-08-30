from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from ..compute.binding import BindingError, resolve_artifact_bindings
from ..compute.scripts import preview_context, render_script
from ..core.database import get_session
from ..core.etag import etag, parse_if_match
from ..core.pagination import decode_cursor, encode_cursor
from ..core.problem import DomainError
from ..identity.deps import current_user, require_command
from ..identity.models import User
from ..projects.service import require_project
from ..registry.repository import RegistryRepository
from .models import WorkflowNode, WorkflowRun
from .preflight import evaluate_preflight
from .repository import WorkflowRepository
from .schemas import (
    ScriptPreviewCreate,
    ScriptPreviewResponse,
    WorkflowCreate,
    WorkflowGraphResponse,
    WorkflowLayoutUpdate,
    WorkflowNodeDeleteResponse,
    WorkflowNodeInput,
    WorkflowNodePage,
    WorkflowNodeResponse,
    WorkflowNodeUpdate,
    WorkflowPage,
    WorkflowPreflightResponse,
    WorkflowResponse,
    WorkflowValidation,
)
from .service import add_node, create_workflow, delete_node, replace_workflow_graph, update_layout, update_node

router = APIRouter(tags=["workflows"])


@router.get("/projects/{project_id}/workflow-runs", response_model=WorkflowPage)
def list_workflows(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> WorkflowPage:
    require_project(session, project_id, user)
    items = WorkflowRepository(session).list_project(project_id, after=decode_cursor(cursor), limit=limit)
    has_next = len(items) > limit
    page = items[:limit]
    return WorkflowPage(
        items=[WorkflowResponse.model_validate(item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if has_next and page else None,
    )


@router.post(
    "/projects/{project_id}/workflow-runs",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "workflow.create"},
)
def post_workflow(
    project_id: uuid.UUID,
    payload: WorkflowCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> WorkflowResponse:
    project = require_project(session, project_id, user)
    return WorkflowResponse.model_validate(create_workflow(session, project, payload, user))


@router.get("/workflow-runs/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> WorkflowResponse:
    workflow = WorkflowRepository(session).get(workflow_id)
    if workflow is None:
        from ..core.problem import DomainError

        raise DomainError("workflow_not_found", "Workflow run was not found", status_code=404)
    require_project(session, workflow.project_id, user)
    response.headers["ETag"] = etag(workflow.version)
    return WorkflowResponse.model_validate(workflow)


@router.put(
    "/workflow-runs/{workflow_id}/graph",
    response_model=WorkflowResponse,
    openapi_extra={"x-permission": "workflow.update"},
)
def put_workflow_graph(
    workflow_id: uuid.UUID,
    payload: WorkflowCreate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> WorkflowResponse:
    workflow = WorkflowRepository(session).get(workflow_id)
    if workflow is None:
        raise DomainError("workflow_not_found", "Workflow run was not found", status_code=404)
    project = require_project(session, workflow.project_id, user)
    row = replace_workflow_graph(session, workflow, payload, user, project, parse_if_match(if_match))
    response.headers["ETag"] = etag(row.version)
    return WorkflowResponse.model_validate(row)


@router.post(
    "/workflow-runs/{workflow_id}/validate",
    response_model=WorkflowValidation,
    openapi_extra={"x-permission": "workflow.validate"},
)
def validate_workflow(
    workflow_id: uuid.UUID, session: Session = Depends(get_session), user: User = Depends(require_command)
) -> WorkflowValidation:
    workflow = WorkflowRepository(session).get(workflow_id)
    if workflow is None:
        raise DomainError("workflow_not_found", "Workflow run was not found", status_code=404)
    require_project(session, workflow.project_id, user)
    nodes = WorkflowRepository(session).nodes(workflow.id)
    errors = [] if nodes else ["workflow has no executable nodes"]
    return WorkflowValidation(valid=not errors, errors=errors)


def _workflow(session: Session, workflow_id: uuid.UUID, user: User) -> WorkflowRun:
    workflow = WorkflowRepository(session).get(workflow_id)
    if workflow is None:
        raise DomainError("workflow_not_found", "Workflow run was not found", status_code=404)
    require_project(session, workflow.project_id, user)
    return workflow


def _node_position(workflow: WorkflowRun, node_key: str) -> dict[str, float] | None:
    for item in workflow.graph.get("nodes", []):
        if item.get("key") == node_key and isinstance(item.get("position"), dict):
            return item["position"]
    return None


def _node_response(workflow: WorkflowRun, node: WorkflowNode) -> WorkflowNodeResponse:
    return WorkflowNodeResponse.model_validate(node).model_copy(
        update={"position": _node_position(workflow, node.node_key)}
    )


@router.get("/workflow-runs/{workflow_id}/graph", response_model=WorkflowGraphResponse)
def get_workflow_graph(
    workflow_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> WorkflowGraphResponse:
    workflow = _workflow(session, workflow_id, user)
    response.headers["ETag"] = etag(workflow.version)
    nodes = WorkflowRepository(session).nodes(workflow.id)
    return WorkflowGraphResponse(
        workflow=WorkflowResponse.model_validate(workflow),
        nodes=[_node_response(workflow, node) for node in nodes],
        edges=workflow.graph.get("edges", []),
        layout=workflow.graph.get("layout", {}),
    )


@router.get("/workflow-runs/{workflow_id}/nodes", response_model=WorkflowNodePage)
def list_workflow_nodes(
    workflow_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> WorkflowNodePage:
    workflow = _workflow(session, workflow_id, user)
    response.headers["ETag"] = etag(workflow.version)
    return WorkflowNodePage(
        items=[_node_response(workflow, node) for node in WorkflowRepository(session).nodes(workflow.id)]
    )


@router.post(
    "/workflow-runs/{workflow_id}/nodes",
    response_model=WorkflowNodeResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "workflow.update"},
)
def add_workflow_node(
    workflow_id: uuid.UUID,
    payload: WorkflowNodeInput,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> WorkflowNodeResponse:
    workflow = _workflow(session, workflow_id, user)
    node = add_node(session, workflow, payload, parse_if_match(if_match))
    response.headers["ETag"] = etag(workflow.version)
    return _node_response(workflow, node)


@router.patch(
    "/workflow-runs/{workflow_id}/nodes/{node_id}",
    response_model=WorkflowNodeResponse,
    openapi_extra={"x-permission": "workflow.update"},
)
def patch_workflow_node(
    workflow_id: uuid.UUID,
    node_id: uuid.UUID,
    payload: WorkflowNodeUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> WorkflowNodeResponse:
    workflow = _workflow(session, workflow_id, user)
    node = WorkflowRepository(session).node(node_id)
    if node is None or node.workflow_run_id != workflow.id:
        raise DomainError("workflow_node_not_found", "Workflow node was not found", status_code=404)
    update_node(workflow, node, payload, parse_if_match(if_match))
    response.headers["ETag"] = etag(workflow.version)
    return _node_response(workflow, node)


@router.delete(
    "/workflow-runs/{workflow_id}/nodes/{node_id}",
    response_model=WorkflowNodeDeleteResponse,
    openapi_extra={"x-permission": "workflow.update"},
)
def delete_workflow_node(
    workflow_id: uuid.UUID,
    node_id: uuid.UUID,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> WorkflowNodeDeleteResponse:
    workflow = _workflow(session, workflow_id, user)
    node = WorkflowRepository(session).node(node_id)
    if node is None or node.workflow_run_id != workflow.id:
        raise DomainError("workflow_node_not_found", "Workflow node was not found", status_code=404)
    delete_node(session, workflow, node, parse_if_match(if_match))
    return WorkflowNodeDeleteResponse(id=node.id, workflow_version=workflow.version)


@router.patch(
    "/workflow-runs/{workflow_id}/layout",
    response_model=WorkflowGraphResponse,
    openapi_extra={"x-permission": "workflow.update"},
)
def patch_workflow_layout(
    workflow_id: uuid.UUID,
    payload: WorkflowLayoutUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> WorkflowGraphResponse:
    workflow = _workflow(session, workflow_id, user)
    graph = update_layout(workflow, payload, parse_if_match(if_match))
    response.headers["ETag"] = etag(workflow.version)
    nodes = WorkflowRepository(session).nodes(workflow.id)
    return WorkflowGraphResponse(
        workflow=WorkflowResponse.model_validate(workflow),
        nodes=[_node_response(workflow, node) for node in nodes],
        edges=graph.get("edges", []),
        layout=graph["layout"],
    )


@router.get("/workflow-runs/{workflow_id}/preflight", response_model=WorkflowPreflightResponse)
def workflow_preflight(
    workflow_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> WorkflowPreflightResponse:
    workflow = _workflow(session, workflow_id, user)
    blockers, warnings, checks = evaluate_preflight(session, workflow)
    return WorkflowPreflightResponse(
        workflow_run_id=workflow.id,
        allowed=not blockers,
        blockers=blockers,
        warnings=warnings,
        checks=checks,
    )


@router.post(
    "/workflow-nodes/{node_id}/script-previews",
    response_model=ScriptPreviewResponse,
    openapi_extra={"x-permission": "workflow.preview"},
)
def preview_node_script(
    node_id: uuid.UUID,
    payload: ScriptPreviewCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ScriptPreviewResponse:
    node = WorkflowRepository(session).node(node_id)
    if node is None:
        raise DomainError("workflow_node_not_found", "Workflow node was not found", status_code=404)
    workflow = _workflow(session, node.workflow_run_id, user)
    plugin = RegistryRepository(session).plugin(node.model_plugin_id) if node.model_plugin_id else None
    command = (plugin.command if plugin else None) or node.command
    if not command:
        raise DomainError("runtime_not_configured", "Node runtime command is not configured", status_code=409)
    try:
        resolved_inputs, pending_inputs = resolve_artifact_bindings(
            session, node=node, plugin=plugin, project_id=workflow.project_id
        )
    except BindingError as exc:
        raise DomainError(
            "input_binding_unsatisfied",
            "Workflow inputs could not be resolved",
            status_code=409,
            errors=exc.blockers,
        ) from exc
    effective_parameters = {**node.parameters, **payload.overrides}
    manifest = {
        "schema_version": "1",
        "parameters": effective_parameters,
        "inputs": resolved_inputs,
        "pending_inputs": pending_inputs,
    }
    return ScriptPreviewResponse(
        workflow_node_id=node.id,
        plugin_id=plugin.id if plugin else None,
        script=render_script(
            preview_context(node, plugin, payload.compute_backend, command, effective_parameters)
        ),
        input_manifest=manifest,
    )
