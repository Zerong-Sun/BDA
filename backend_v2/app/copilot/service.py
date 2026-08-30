import os
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..candidates.models import Candidate
from ..core.config import get_settings
from ..core.problem import DomainError
from ..experiments.models import ExperimentResult
from ..identity.models import User
from ..knowledge.models import KnowledgeEntry
from ..platform.models import Operation
from ..platform.operations import enqueue_operation
from ..projects.models import Project
from ..registry.models import LLMProvider, ModelPlugin
from ..targets.repository import TargetRepository
from . import agent_runs
from .capabilities import (
    configurable_capability_ids,
    normalize_capabilities,
    tools_for_capabilities,
)
from .models import CopilotAgentRun, CopilotConfig, CopilotConversation, CopilotMessage
from .route_catalog import DesignRoute, recommended_parameters, routes_for
from .schemas import (
    AgentRunCreate,
    CopilotConfigUpdate,
    InterpretationCreate,
    InterpretationResponse,
    RoutePlanCreate,
    RoutePlanKnowledgeRef,
    RoutePlanModule,
    RoutePlanOption,
    RoutePlanResponse,
)


def _store_local_secret(secret_root: Path, project_id: uuid.UUID, value: str) -> Path:
    temporary = secret_root / f".project-{project_id}.{uuid.uuid4().hex}.tmp"
    try:
        secret_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(secret_root, 0o700)
        secret_path = secret_root / f"project-{project_id}.key"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, secret_path)
        os.chmod(secret_path, 0o600)
        return secret_path
    except OSError as exc:
        raise DomainError(
            "credential_store_unavailable",
            "The local credential store is not writable",
            status_code=503,
        ) from exc
    finally:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass


def submit_chat(
    session: Session,
    project: Project,
    conversation_id,
    content: str,
    user: User,
    *,
    context: dict | None = None,
    intent: str = "chat",
):
    conversation = session.get(CopilotConversation, conversation_id) if conversation_id else None
    if conversation and conversation.project_id != project.id:
        raise DomainError("conversation_not_found", "Conversation does not belong to this project", status_code=404)
    if conversation is None:
        conversation = CopilotConversation(project_id=project.id, created_by=user.id, title=content[:120])
        session.add(conversation)
        session.flush()
    message = CopilotMessage(
        conversation_id=conversation.id,
        role="user",
        content=content,
        context={
            **(context or {}),
            "intent": intent,
            "_requested_by": str(user.id),
        },
    )
    session.add(message)
    session.flush()
    operation = enqueue_operation(
        session,
        topic="copilot.respond",
        resource_type="copilot_message",
        resource_id=message.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"message_id": str(message.id)},
    )
    return conversation, message, operation


def put_config(
    session: Session,
    row: CopilotConfig | None,
    project_id: uuid.UUID,
    payload: CopilotConfigUpdate,
    expected_version: int | None,
) -> CopilotConfig:
    unknown_capabilities = sorted(
        set(payload.enabled_skills) - configurable_capability_ids()
    )
    if unknown_capabilities:
        raise DomainError(
            "copilot_capability_not_found",
            "Unknown Copilot capabilities: "
            + ", ".join(unknown_capabilities),
            status_code=422,
        )
    settings_payload = dict(payload.settings)
    raw_api_key = str(settings_payload.pop("llm_api_key", "")).strip()
    endpoint = str(settings_payload.get("llm_api_base", "")).strip()
    model = str(settings_payload.get("llm_model", "")).strip()
    if row is None:
        row = CopilotConfig(project_id=project_id, version=1)
        session.add(row)
    else:
        if row.version != expected_version:
            raise DomainError("version_conflict", "Copilot config was modified", status_code=412)
        row.version += 1
    provider_id = payload.llm_provider_id if payload.llm_provider_id is not None else row.llm_provider_id
    provider = session.get(LLMProvider, provider_id) if provider_id else None
    if payload.llm_provider_id is not None and provider is None:
        raise DomainError("llm_provider_not_found", "LLM provider was not found", status_code=404)
    if raw_api_key:
        runtime = get_settings()
        if runtime.is_production:
            raise DomainError(
                "browser_api_key_forbidden",
                "Production API keys must be configured through a secret reference, not submitted by the browser",
                status_code=422,
            )
        secret_root = Path(runtime.llm_local_secret_dir).expanduser().resolve()
        secret_path = _store_local_secret(secret_root, project_id, raw_api_key)
        provider_name = f"Project {project_id} BYOK"
        if provider is None or provider.name != provider_name:
            provider = session.scalar(select(LLMProvider).where(LLMProvider.name == provider_name))
        if provider is None:
            provider = LLMProvider(
                name=provider_name,
                provider_type="openai_compatible",
                endpoint=endpoint,
                model=model,
                credential_ref=f"file:{secret_path}",
                config={},
                enabled=True,
            )
            session.add(provider)
            session.flush()
        else:
            provider.endpoint = endpoint or provider.endpoint
            provider.model = model or provider.model
            provider.credential_ref = f"file:{secret_path}"
            provider.enabled = True
            provider.version += 1
        row.llm_provider_id = provider.id
        settings_payload["api_key_preview"] = f"••••{raw_api_key[-4:]}"
    elif provider is not None:
        if endpoint:
            provider.endpoint = endpoint
        if model:
            provider.model = model
    row.settings = settings_payload
    row.enabled_skills = payload.enabled_skills
    if payload.llm_provider_id is not None and not raw_api_key:
        row.llm_provider_id = payload.llm_provider_id
    session.flush()
    return row


def _knowledge_summary(entry: KnowledgeEntry) -> str:
    """First meaningful line of an entry, for the plan's knowledge panel."""
    for line in str(entry.content or "").splitlines():
        text = line.strip().lstrip("#").strip()
        if text:
            return text[:280]
    return ""


def _route_option(
    route: DesignRoute,
    rank: int,
    plugins_by_key: dict[str, ModelPlugin],
    goal: str,
) -> tuple[RoutePlanOption, list[str]]:
    modules: list[RoutePlanModule] = []
    nodes: list[dict] = []
    notes: list[str] = []
    for step in route.steps:
        plugin = plugins_by_key.get(step.plugin_key)
        if plugin is None:
            notes.append(f"{route.label}: no enabled '{step.plugin_key}' plugin is registered.")
            continue
        parameters, dropped = recommended_parameters(step, plugin.parameter_schema)
        notes.extend(dropped)
        # Numbered over the steps that survived, so a missing plugin does not
        # leave a gap in the node keys the user sees on the canvas.
        key = f"{plugin.plugin_key.lower()}-{len(nodes) + 1}"
        nodes.append(
            {
                "key": key,
                "node_type": plugin.plugin_key,
                "model_plugin": plugin.name,
                "model_plugin_id": str(plugin.id),
                "container_image": plugin.container_image,
                "command": plugin.command,
                "parameters": parameters,
                "plugin_version": plugin.plugin_version,
                "parameter_schema": plugin.parameter_schema,
                "available": plugin.enabled,
            }
        )
        modules.append(
            RoutePlanModule(
                module_id=str(plugin.id),
                model_plugin_id=plugin.id,
                model_name=plugin.name,
                node_type=plugin.plugin_key,
                available=plugin.enabled,
                summary=step.purpose,
                default_parameters=parameters,
                parameter_schema=plugin.parameter_schema if isinstance(plugin.parameter_schema, dict) else {},
            )
        )
    edges = [
        {"source": nodes[index]["key"], "target": nodes[index + 1]["key"]}
        for index in range(len(nodes) - 1)
    ]
    option = RoutePlanOption(
        route_id=route.route_id,
        label=route.label,
        rank=rank,
        recommended=rank == 1,
        summary=route.summary,
        rationale=list(route.rationale),
        risks=list(route.risks),
        constraints=dict(route.constraints),
        modules=modules,
        estimated_steps=len(modules),
        workflow_spec={
            "name": goal[:200],
            "nodes": nodes,
            "edges": edges,
            "route": route.route_id,
        },
    )
    return option, notes


def create_route_plan(session: Session, project: Project, payload: RoutePlanCreate) -> RoutePlanResponse:
    target = TargetRepository(session).get(project.primary_target_id) if project.primary_target_id else None
    evidence = list(
        session.scalars(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.project_id == project.id)
            .order_by(KnowledgeEntry.created_at.desc())
            .limit(10)
        )
    )
    routes = routes_for(has_structure=bool(target and target.structure_artifact_id))
    plugins_by_key = {
        plugin.plugin_key: plugin
        for plugin in session.scalars(
            select(ModelPlugin).where(
                ModelPlugin.enabled.is_(True),
                ModelPlugin.plugin_key.in_([step.plugin_key for route in routes for step in route.steps]),
            )
        )
    }
    rationale = [
        "A confirmed primary target is required before compute submission.",
        "Runtime plugins are snapshotted when the workflow is submitted.",
    ]
    if evidence:
        rationale.append(f"The plan references {len(evidence)} project knowledge entries.")

    options: list[RoutePlanOption] = []
    for rank, route in enumerate(routes, start=1):
        option, notes = _route_option(route, rank, plugins_by_key, payload.goal)
        options.append(option)
        rationale.extend(notes)
    recommended = next((option for option in options if option.modules), options[0] if options else None)
    if recommended is not None and not recommended.recommended:
        # The first-ranked route has no registered plugins; promote the first that does
        # so the UI preselects a route the user can actually create.
        for option in options:
            option.recommended = option is recommended
    if recommended is None or not recommended.modules:
        rationale.append("No enabled model plugins are available for the recommended route.")

    return RoutePlanResponse(
        project_id=project.id,
        goal=payload.goal,
        recommended_route=recommended.route_id if recommended else "",
        rationale=rationale,
        workflow_spec=recommended.workflow_spec if recommended else {},
        evidence_refs=[item.id for item in evidence],
        route_options=options,
        knowledge_context=[
            RoutePlanKnowledgeRef(
                knowledge_entry_id=entry.id,
                title=entry.title,
                category=entry.entry_type,
                summary=_knowledge_summary(entry),
            )
            for entry in evidence
        ],
    )


def create_interpretation(
    session: Session, project: Project, payload: InterpretationCreate
) -> InterpretationResponse:
    observations: list[str] = []
    evidence_refs: list[uuid.UUID] = []
    if payload.subject == "candidate":
        candidate = session.get(Candidate, payload.candidate_id) if payload.candidate_id else None
        if candidate is None or candidate.project_id != project.id:
            raise DomainError("candidate_not_found", "Candidate was not found", status_code=404)
        observations.append(f"Candidate status is {candidate.status}.")
        if candidate.score is not None:
            observations.append(f"Recorded aggregate score is {candidate.score:g}.")
        evidence_refs.extend(
            item for item in (candidate.structure_artifact_id, candidate.complex_artifact_id) if item is not None
        )
        summary = "Candidate interpretation is based on recorded computational metadata."
    else:
        total = int(
            session.scalar(select(func.count(ExperimentResult.id)).where(ExperimentResult.project_id == project.id))
            or 0
        )
        passed = int(
            session.scalar(
                select(func.count(ExperimentResult.id)).where(
                    ExperimentResult.project_id == project.id,
                    ExperimentResult.pass_status == "pass",
                )
            )
            or 0
        )
        observations.extend([f"{total} experiment results are recorded.", f"{passed} are marked pass."])
        summary = "Result interpretation summarizes recorded experimental outcomes."
    return InterpretationResponse(
        project_id=project.id,
        subject=payload.subject,
        summary=summary,
        observations=observations,
        limitations=[
            "Predicted scores are not experimental evidence.",
            "A researcher must review provenance and assay context before decisions.",
        ],
        evidence_refs=evidence_refs,
    )


def start_agent_run(
    session: Session,
    project: Project,
    user: User,
    payload: AgentRunCreate,
) -> tuple[CopilotAgentRun, Operation]:
    """Create a durable run and hand it to a worker.

    The run's tool vocabulary is derived from capabilities the project has
    enabled, never from a list the caller supplies. A client that could name
    tools directly would be able to reach past the project's own configuration,
    and `allowed_tools` is the restriction a subagent is intersected against.
    """
    config = session.scalar(select(CopilotConfig).where(CopilotConfig.project_id == project.id))
    enabled = normalize_capabilities(list(config.enabled_skills) if config and config.enabled_skills else None)
    if payload.skills:
        requested = normalize_capabilities(payload.skills)
        unknown = sorted(set(payload.skills) - configurable_capability_ids())
        if unknown:
            raise DomainError(
                "copilot_capability_not_found",
                "Unknown Copilot capabilities: " + ", ".join(unknown),
                status_code=422,
            )
        disabled = sorted(requested - enabled)
        if disabled:
            raise DomainError(
                "copilot_capability_disabled",
                "Capabilities disabled for this project: " + ", ".join(disabled),
                status_code=422,
            )
        capabilities = requested
    else:
        capabilities = enabled
    allowed_tools = sorted(tools_for_capabilities(capabilities))
    if not allowed_tools:
        raise DomainError(
            "copilot_agent_run_without_tools",
            "An agent run with no tools cannot make progress; enable a capability first.",
            status_code=422,
        )
    run = agent_runs.create_run(
        session,
        project_id=project.id,
        user_id=user.id,
        goal=payload.goal,
        allowed_tools=allowed_tools,
        conversation_id=payload.conversation_id,
        max_turns=payload.max_turns,
        max_cost_usd_cents=payload.max_cost_usd_cents,
    )
    operation = enqueue_operation(
        session,
        topic="copilot.agent_step",
        resource_type="copilot_agent_run",
        resource_id=run.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"run_id": str(run.id)},
    )
    return run, operation
