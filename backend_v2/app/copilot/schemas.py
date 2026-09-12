from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class CopilotTurnContext(BaseModel):
    route: str | None = Field(default=None, max_length=500)
    research_tab: str | None = Field(default=None, max_length=80)
    selected_entity_ids: list[
        Annotated[str, Field(min_length=1, max_length=100)]
    ] = Field(default_factory=list, max_length=50)
    language: Literal["en", "zh"] = "en"


class ChatCreate(BaseModel):
    project_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=50000)
    context: CopilotTurnContext = Field(default_factory=CopilotTurnContext)
    intent: Literal["chat", "review_section"] = "chat"
    skill: str | None = Field(default=None, max_length=80)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    status: str
    citations: list
    tool_calls: list
    context: dict
    error: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class MessagePage(BaseModel):
    items: list[MessageResponse]
    next_cursor: str | None = None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    status: str
    created_by: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime


class ConversationPage(BaseModel):
    items: list[ConversationResponse]
    next_cursor: str | None = None


class ChatAccepted(BaseModel):
    operation_id: uuid.UUID
    conversation_id: uuid.UUID
    message: MessageResponse


class CopilotConfigUpdate(BaseModel):
    llm_provider_id: uuid.UUID | None = None
    settings: dict = Field(default_factory=dict)
    enabled_skills: list[
        Annotated[str, Field(min_length=1, max_length=80)]
    ] = Field(default_factory=list, max_length=50)


class CopilotConfigResponse(CopilotConfigUpdate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    api_key_configured: bool = False
    version: int
    created_at: datetime
    updated_at: datetime


class CopilotConfigTestResponse(BaseModel):
    connected: bool
    model: str
    sample: str | None = None
    reason: str | None = None


class SkillResponse(BaseModel):
    id: str
    title: str
    description: str
    async_execution: bool = True
    execution_mode: Literal["read", "draft", "queue", "confirm"] = "read"
    chat_tools: list[str] = Field(default_factory=list)
    requires_explicit_request: bool = False
    requires_confirmation: bool = False


class RoutePlanCreate(BaseModel):
    project_id: uuid.UUID
    goal: str = Field(min_length=1, max_length=5000)


class RoutePlanKnowledgeRef(BaseModel):
    knowledge_entry_id: uuid.UUID
    title: str
    category: str
    summary: str


class RoutePlanModule(BaseModel):
    module_id: str
    model_plugin_id: uuid.UUID | None = None
    model_name: str
    node_type: str
    available: bool
    summary: str
    default_parameters: dict = Field(default_factory=dict)
    parameter_schema: dict = Field(default_factory=dict)


class RoutePlanOption(BaseModel):
    route_id: str
    label: str
    rank: int
    recommended: bool
    summary: str
    rationale: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    modules: list[RoutePlanModule] = Field(default_factory=list)
    estimated_steps: int
    workflow_spec: dict = Field(default_factory=dict)


class RoutePlanResponse(BaseModel):
    project_id: uuid.UUID
    goal: str
    recommended_route: str
    rationale: list[str]
    workflow_spec: dict
    evidence_refs: list[uuid.UUID]
    route_options: list[RoutePlanOption] = Field(default_factory=list)
    knowledge_context: list[RoutePlanKnowledgeRef] = Field(default_factory=list)


class InterpretationCreate(BaseModel):
    project_id: uuid.UUID
    subject: str = Field(pattern="^(candidate|results)$")
    candidate_id: uuid.UUID | None = None


class InterpretationResponse(BaseModel):
    project_id: uuid.UUID
    subject: str
    summary: str
    observations: list[str]
    limitations: list[str]
    evidence_refs: list[uuid.UUID]


# --- Durable agent runs ------------------------------------------------------


class AgentRunCreate(BaseModel):
    project_id: uuid.UUID
    goal: str = Field(min_length=1, max_length=50000)
    conversation_id: uuid.UUID | None = None
    #: Capability ids, not tool ids. The client asks for what the run may do; the
    #: server derives the tools, so a client cannot name a tool its project has
    #: not enabled.
    skills: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(
        default_factory=list, max_length=20
    )
    max_turns: int = Field(default=24, ge=1, le=200)
    max_cost_usd_cents: int | None = Field(default=None, ge=0, le=1_000_000)


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    conversation_id: uuid.UUID | None
    created_by: uuid.UUID
    goal: str
    status: str
    parent_run_id: uuid.UUID | None
    allowed_tools: list
    max_turns: int
    turn_count: int
    cost_usd_cents: int
    #: This run plus everything it spawned. The ceiling applies to the tree, so
    #: a parent that could only see its own spend could not tell whether it was
    #: about to be stopped.
    subtree_cost_usd_cents: int = 0
    max_cost_usd_cents: int | None
    error: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class AgentRunPage(BaseModel):
    items: list[AgentRunResponse]
    next_cursor: str | None = None


class AgentTurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    sequence: int
    role: str
    content: str
    tool_calls: list
    tokens_in: int
    tokens_out: int
    cost_usd_cents: int
    created_at: datetime


class AgentTurnPage(BaseModel):
    items: list[AgentTurnResponse]
    next_cursor: str | None = None


class AgentTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    kind: str
    resource_id: uuid.UUID
    status: str
    tool_call_id: str
    result: dict
    error: str | None


class AgentRunAccepted(BaseModel):
    run: AgentRunResponse
    operation_id: uuid.UUID


class AgentRunCancelled(BaseModel):
    run: AgentRunResponse
    cancelled_runs: int


# --- MCP sessions ------------------------------------------------------------


class McpSessionCreate(BaseModel):
    project_id: uuid.UUID
    label: str = Field(min_length=1, max_length=120)
    #: The run whose goal is this grant's mandate. Omit for a read-only grant -
    #: `mcp.available_tools` lists no write tool without one.
    agent_run_id: uuid.UUID | None = None
    #: Capability ids, not tool ids, for the same reason `AgentRunCreate.skills`
    #: takes capabilities: the server derives the tools, so a client cannot name
    #: one its project has not enabled.
    capabilities: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(
        default_factory=list, max_length=20
    )
    expires_in_hours: int = Field(default=24, ge=1, le=720)


class McpSessionResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    agent_run_id: uuid.UUID | None
    issued_by: uuid.UUID
    label: str
    granted_capabilities: list[str]
    #: Whether the bound run is still live. False means the grant is read-only
    #: right now, whether or not it names a run.
    mandate_live: bool
    #: What this grant can actually call, after the project configuration, the
    #: run vocabulary and the intent gate have all narrowed it. Derived on read
    #: rather than stored, because every one of those inputs can change after the
    #: grant was written.
    tools: list[str]
    write_tools: list[str]
    expires_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None
    call_count: int
    version: int
    created_at: datetime
    updated_at: datetime


class McpSessionIssued(BaseModel):
    session: McpSessionResponse
    #: Returned exactly once. Only the SHA-256 hash is stored, so this value
    #: cannot be shown again - reissue instead of recovering it.
    token: str
    endpoint: str


class McpSessionPage(BaseModel):
    items: list[McpSessionResponse]
    next_cursor: str | None = None
