from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from ..core.database import SessionFactory, get_session
from ..core.etag import etag, parse_if_match
from ..core.pagination import decode_cursor, encode_cursor
from ..core.problem import DomainError
from ..core.sse import observed_sse
from ..identity.deps import current_user, require_command, streaming_user
from ..identity.models import User
from ..projects.service import require_project
from . import agent_runs
from .capabilities import (
    COPILOT_CAPABILITIES,
    capability_ids,
    normalize_capabilities,
)
from .models import CopilotAgentRun, CopilotConfig
from .provider import complete as complete_with_provider
from .provider import credential_available
from .repository import CopilotRepository
from .schemas import (
    AgentRunAccepted,
    AgentRunCancelled,
    AgentRunCreate,
    AgentRunPage,
    AgentRunResponse,
    AgentTurnPage,
    AgentTurnResponse,
    ChatAccepted,
    ChatCreate,
    ConversationPage,
    ConversationResponse,
    CopilotConfigResponse,
    CopilotConfigTestResponse,
    CopilotConfigUpdate,
    InterpretationCreate,
    InterpretationResponse,
    MessagePage,
    MessageResponse,
    RoutePlanCreate,
    RoutePlanResponse,
    SkillResponse,
)
from .service import (
    create_interpretation as create_interpretation_service,
)
from .service import (
    create_route_plan as create_route_plan_service,
)
from .service import (
    put_config as put_config_service,
)
from .service import (
    start_agent_run as start_agent_run_service,
)
from .service import (
    submit_chat,
)

router = APIRouter(prefix="/copilot", tags=["copilot"])
SKILLS = [SkillResponse(**item) for item in COPILOT_CAPABILITIES]


def _config_response(session: Session, row: CopilotConfig) -> CopilotConfigResponse:
    provider = CopilotRepository(session).llm_provider(row.llm_provider_id) if row.llm_provider_id else None
    return CopilotConfigResponse.model_validate(row).model_copy(
        update={
            "api_key_configured": bool(
                provider and provider.enabled and credential_available(provider.credential_ref)
            )
        }
    )


@router.get("/skills", response_model=list[SkillResponse])
def list_skills(user: User = Depends(current_user)) -> list[SkillResponse]:
    return SKILLS


@router.post(
    "/chat",
    response_model=ChatAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "copilot.chat"},
)
def post_chat(
    payload: ChatCreate, session: Session = Depends(get_session), user: User = Depends(require_command)
) -> ChatAccepted:
    if payload.skill is not None and payload.skill not in capability_ids():
        raise DomainError(
            "copilot_skill_not_found",
            "The requested Copilot capability was not found",
            status_code=422,
        )
    project = require_project(session, payload.project_id, user)
    config = CopilotRepository(session).config(project.id)
    if (
        payload.skill is not None
        and payload.skill
        not in normalize_capabilities(
            list(config.enabled_skills) if config else None
        )
    ):
        raise DomainError(
            "copilot_capability_disabled",
            "The requested Copilot capability is disabled for this project",
            status_code=422,
        )
    conversation, message, operation = submit_chat(
        session,
        project,
        payload.conversation_id,
        payload.message,
        user,
        context={
            **payload.context.model_dump(mode="json"),
            "skill_hint": payload.skill,
        },
        intent=payload.intent,
    )
    return ChatAccepted(
        operation_id=operation.id,
        conversation_id=conversation.id,
        message=MessageResponse.model_validate(message),
    )


@router.get("/projects/{project_id}/conversations", response_model=ConversationPage)
def list_conversations(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ConversationPage:
    require_project(session, project_id, user)
    rows = CopilotRepository(session).list_conversations(project_id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return ConversationPage(
        items=[ConversationResponse.model_validate(item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ConversationResponse:
    conversation = CopilotRepository(session).conversation(conversation_id)
    if conversation is None:
        raise DomainError("conversation_not_found", "Conversation was not found", status_code=404)
    require_project(session, conversation.project_id, user)
    response.headers["ETag"] = etag(conversation.version)
    return ConversationResponse.model_validate(conversation)


@router.get("/conversations/{conversation_id}/messages", response_model=MessagePage)
def list_messages(
    conversation_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> MessagePage:
    repository = CopilotRepository(session)
    conversation = repository.conversation(conversation_id)
    if conversation is None:
        raise DomainError("conversation_not_found", "Conversation was not found", status_code=404)
    require_project(session, conversation.project_id, user)
    rows = repository.list_messages(conversation_id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return MessagePage(
        items=[MessageResponse.model_validate(item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get("/conversations/{conversation_id}/stream")
def stream_messages(
    conversation_id: uuid.UUID,
    after_message_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(streaming_user),
) -> EventSourceResponse:
    with SessionFactory() as session:
        conversation = CopilotRepository(session).conversation(conversation_id)
        if conversation is None:
            raise DomainError("conversation_not_found", "Conversation was not found", status_code=404)
        require_project(session, conversation.project_id, user)

    async def stream() -> AsyncIterator[dict[str, str]]:
        seen: set[uuid.UUID] = set()
        if after_message_id is not None:
            with SessionFactory() as session:
                rows = CopilotRepository(session).all_messages(conversation_id)
                for row in rows:
                    seen.add(row.id)
                    if row.id == after_message_id:
                        break
        while True:
            with SessionFactory() as session:
                rows = CopilotRepository(session).all_messages(conversation_id)
                payloads = [MessageResponse.model_validate(x).model_dump(mode="json") for x in rows if x.id not in seen]
                seen.update(x.id for x in rows)
                done = bool(rows) and rows[-1].role == "assistant" and rows[-1].status in {"completed", "failed"}
            for payload in payloads:
                yield {"event": "message", "data": json.dumps(payload)}
            if done:
                yield {"event": "done", "data": "{}"}
                return
            await asyncio.sleep(1)

    return EventSourceResponse(observed_sse("copilot_messages", stream()))


@router.get("/projects/{project_id}/config", response_model=CopilotConfigResponse)
def get_config(
    project_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> CopilotConfigResponse:
    require_project(session, project_id, user)
    row = CopilotRepository(session).config(project_id)
    if row is None:
        raise DomainError("copilot_config_not_found", "Copilot config was not found", status_code=404)
    response.headers["ETag"] = etag(row.version)
    return _config_response(session, row)


@router.put(
    "/projects/{project_id}/config",
    response_model=CopilotConfigResponse,
    openapi_extra={"x-permission": "copilot.config.update"},
)
def put_config(
    project_id: uuid.UUID,
    payload: CopilotConfigUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> CopilotConfigResponse:
    require_project(session, project_id, user)
    existing = CopilotRepository(session).config(project_id)
    expected = parse_if_match(if_match) if existing is not None else None
    row = put_config_service(session, existing, project_id, payload, expected)
    response.headers["ETag"] = etag(row.version)
    return _config_response(session, row)


@router.post(
    "/projects/{project_id}/config/tests",
    response_model=CopilotConfigTestResponse,
    openapi_extra={"x-permission": "copilot.config.test"},
)
def test_config(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> CopilotConfigTestResponse:
    require_project(session, project_id, user)
    config = CopilotRepository(session).config(project_id)
    provider = CopilotRepository(session).llm_provider(config.llm_provider_id) if config and config.llm_provider_id else None
    if provider is None or not provider.enabled:
        return CopilotConfigTestResponse(connected=False, model="", reason="No enabled LLM provider is configured")
    try:
        sample = complete_with_provider(
            provider,
            [
                {"role": "system", "content": "Reply with exactly: BDA provider connected"},
                {"role": "user", "content": "Connection test"},
            ],
        )
    except Exception as exc:
        return CopilotConfigTestResponse(
            connected=False,
            model=provider.model,
            reason=f"{type(exc).__name__}: {str(exc)[:240]}",
        )
    return CopilotConfigTestResponse(connected=True, model=provider.model, sample=sample[:240])


@router.post(
    "/route-plans",
    response_model=RoutePlanResponse,
    openapi_extra={"x-permission": "copilot.plan"},
)
def create_route_plan(
    payload: RoutePlanCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> RoutePlanResponse:
    project = require_project(session, payload.project_id, user)
    return create_route_plan_service(session, project, payload)


@router.post(
    "/interpretations",
    response_model=InterpretationResponse,
    openapi_extra={"x-permission": "copilot.interpret"},
)
def create_interpretation(
    payload: InterpretationCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> InterpretationResponse:
    project = require_project(session, payload.project_id, user)
    return create_interpretation_service(session, project, payload)


# --- Durable agent runs ------------------------------------------------------
#
# A run outlives the request that started it, so the API only creates it and
# hands it to a worker. Everything else here reads the transcript, which is the
# run's whole state and therefore the only thing worth exposing.


def _run_response(session: Session, run: CopilotAgentRun) -> AgentRunResponse:
    """A run, with what its whole tree has spent.

    Computed on read rather than mirrored onto the row: a child that reported its
    spend upward would make its own `cost_usd_cents` untrue, and that column is
    what a person reads when asking where the money went.
    """
    return _run_response(session, run).model_copy(
        update={"subtree_cost_usd_cents": agent_runs.tree_cost_usd_cents(session, run)}
    )


def _require_run(session: Session, run_id: uuid.UUID, user: User) -> CopilotAgentRun:
    run = agent_runs.require_run(session, run_id)
    require_project(session, run.project_id, user)
    return run


@router.post(
    "/agent-runs",
    response_model=AgentRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={"x-permission": "copilot.agent.start"},
)
def start_agent_run(
    payload: AgentRunCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> AgentRunAccepted:
    project = require_project(session, payload.project_id, user)
    run, operation = start_agent_run_service(session, project, user, payload)
    return AgentRunAccepted(
        run=_run_response(session, run), operation_id=operation.id
    )


@router.get("/projects/{project_id}/agent-runs", response_model=AgentRunPage)
def list_agent_runs(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> AgentRunPage:
    require_project(session, project_id, user)
    rows = CopilotRepository(session).list_agent_runs(project_id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return AgentRunPage(
        items=[_run_response(session, item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get("/agent-runs/{run_id}", response_model=AgentRunResponse)
def get_agent_run(
    run_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> AgentRunResponse:
    run = _require_run(session, run_id, user)
    response.headers["ETag"] = etag(run.version)
    return _run_response(session, run)


@router.get("/agent-runs/{run_id}/turns", response_model=AgentTurnPage)
def list_agent_turns(
    run_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> AgentTurnPage:
    run = _require_run(session, run_id, user)
    rows = CopilotRepository(session).agent_turns(run.id, decode_cursor(cursor), limit)
    page = rows[:limit]
    return AgentTurnPage(
        items=[AgentTurnResponse.model_validate(item) for item in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.post(
    "/agent-runs/{run_id}/cancellations",
    response_model=AgentRunCancelled,
    openapi_extra={"x-permission": "copilot.agent.cancel"},
)
def cancel_agent_run(
    run_id: uuid.UUID,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> AgentRunCancelled:
    run = _require_run(session, run_id, user)
    expected = parse_if_match(if_match)
    if expected is not None and expected != run.version:
        raise DomainError(
            "version_conflict",
            "The agent run changed since it was read",
            status_code=412,
        )
    cancelled = agent_runs.cancel(session, run, reason=f"cancelled by {user.username}")
    response.headers["ETag"] = etag(run.version)
    return AgentRunCancelled(run=_run_response(session, run), cancelled_runs=cancelled)
