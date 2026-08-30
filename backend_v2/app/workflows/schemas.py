from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.statuses import WorkflowNodeStatus, WorkflowRunStatus


class WorkflowInputBinding(BaseModel):
    """Where one input port of a node gets its data from."""

    port: str = Field(min_length=1, max_length=120)
    source: str = Field(pattern="^(artifact|upstream)$")
    artifact_id: uuid.UUID | None = None
    from_node: str | None = Field(default=None, max_length=120)
    from_port: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_source(self) -> WorkflowInputBinding:
        if self.source == "artifact" and self.artifact_id is None:
            raise ValueError("artifact bindings require artifact_id")
        if self.source == "upstream" and not (self.from_node and self.from_port):
            raise ValueError("upstream bindings require from_node and from_port")
        return self


class WorkflowNodeInput(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    node_type: str = Field(min_length=1, max_length=80)
    model_plugin: str = Field(min_length=1, max_length=160)
    model_plugin_id: uuid.UUID | None = None
    container_image: str | None = Field(default=None, max_length=500)
    command: str | None = None
    queue: str | None = Field(default=None, max_length=120)
    parameters: dict = Field(default_factory=dict)
    input_bindings: list[WorkflowInputBinding] = Field(default_factory=list, max_length=50)
    position: dict[str, float] | None = None


class WorkflowEdgeInput(BaseModel):
    source: str
    target: str
    source_port: str | None = Field(default=None, max_length=120)
    target_port: str | None = Field(default=None, max_length=120)


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    nodes: list[WorkflowNodeInput] = Field(default_factory=list, max_length=200)
    edges: list[WorkflowEdgeInput] = Field(default_factory=list, max_length=500)
    # The run this one is to be compared against. Only the ancestor is declared here;
    # what differs is computed at submission, never supplied by the author.
    derived_from_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_graph(self) -> WorkflowCreate:
        keys = [node.key for node in self.nodes]
        if len(keys) != len(set(keys)):
            raise ValueError("workflow node keys must be unique")
        key_set = set(keys)
        if any(edge.source not in key_set or edge.target not in key_set for edge in self.edges):
            raise ValueError("workflow edges must reference known nodes")
        outgoing: dict[str, list[str]] = {key: [] for key in keys}
        indegree = {key: 0 for key in keys}
        for edge in self.edges:
            outgoing[edge.source].append(edge.target)
            indegree[edge.target] += 1
        ready = [key for key, degree in indegree.items() if degree == 0]
        visited = 0
        while ready:
            current = ready.pop()
            visited += 1
            for target in outgoing[current]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
        if visited != len(keys):
            raise ValueError("workflow graph must be acyclic")
        return self


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    status: WorkflowRunStatus
    graph: dict
    version: int
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    derived_from_id: uuid.UUID | None = None
    arm_label: str = "baseline"
    varied_parameters: dict = Field(default_factory=dict)


class WorkflowPage(BaseModel):
    items: list[WorkflowResponse]
    next_cursor: str | None = None


class WorkflowValidation(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WorkflowNodeUpdate(BaseModel):
    node_type: str | None = Field(default=None, min_length=1, max_length=80)
    model_plugin: str | None = Field(default=None, min_length=1, max_length=160)
    model_plugin_id: uuid.UUID | None = None
    container_image: str | None = Field(default=None, max_length=500)
    command: str | None = None
    queue: str | None = Field(default=None, max_length=120)
    parameters: dict | None = None
    input_bindings: list[WorkflowInputBinding] | None = Field(default=None, max_length=50)
    position: dict[str, float] | None = None


class WorkflowNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_run_id: uuid.UUID
    node_key: str
    node_type: str
    model_plugin: str
    model_plugin_id: uuid.UUID | None
    container_image: str | None
    command: str | None
    queue: str | None
    status: WorkflowNodeStatus
    execution_mode: str = "dispatch"
    parameters: dict
    input_bindings: list = Field(default_factory=list)
    error_message: str | None
    position: dict[str, float] | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class WorkflowNodePage(BaseModel):
    items: list[WorkflowNodeResponse]
    next_cursor: str | None = None


class WorkflowGraphResponse(BaseModel):
    workflow: WorkflowResponse
    nodes: list[WorkflowNodeResponse]
    edges: list[WorkflowEdgeInput]
    layout: dict = Field(default_factory=dict)


class WorkflowLayoutUpdate(BaseModel):
    nodes: list[dict] = Field(default_factory=list, max_length=200)
    edges: list[dict] = Field(default_factory=list, max_length=500)


class WorkflowPreflightResponse(BaseModel):
    workflow_run_id: uuid.UUID
    allowed: bool
    blockers: list[dict]
    warnings: list[dict]
    checks: dict


class ScriptPreviewCreate(BaseModel):
    compute_backend: str = Field(default="lsf", pattern="^(docker|lsf)$")
    overrides: dict = Field(default_factory=dict)


class ScriptPreviewResponse(BaseModel):
    workflow_node_id: uuid.UUID
    plugin_id: uuid.UUID | None
    script: str
    input_manifest: dict


class WorkflowNodeDeleteResponse(BaseModel):
    id: uuid.UUID
    deleted: bool = True
    workflow_version: int
