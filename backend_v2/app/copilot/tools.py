"""The copilot's tool catalogue.

Every tool the agent can reach is declared here once - schema, capability,
execution mode, and handler together. Registering a new capability is adding a
`_register(...)` call; the capability manifest, the schemas sent to the model,
and the dispatch all derive from it.

The bench tools at the end are what let the agent work on wet-lab data instead
of only reading about it: it can look up a construct, quantify a sample, and
plan a dilution series without a human relaying numbers through the UI. This is
the platform's own principle that AI is a first-class user, applied to the half
of the loop that only just arrived.
"""

from __future__ import annotations

import uuid
from typing import Any

from .registry import REGISTRY, ToolContext, ToolSpec

_EMPTY_OBJECT: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}


def _limit(maximum: int = 50, default_max: int = 50) -> dict[str, Any]:
    return {"type": "integer", "minimum": 1, "maximum": maximum, "default": default_max}


def _register(spec: ToolSpec) -> ToolSpec:
    return REGISTRY.register(spec)


def _arg_str(arguments: dict[str, Any], key: str, fallback: str = "") -> str:
    return str(arguments.get(key) or fallback)


def _arg_int(arguments: dict[str, Any], key: str, fallback: int) -> int:
    try:
        return int(arguments.get(key) or fallback)
    except (TypeError, ValueError):
        return fallback


def _project_of(context: ToolContext) -> uuid.UUID:
    """The turn's project, or a clear failure.

    `requires` guards the service objects; a tool that also needs a project
    identity has to say so, because a chat session without one would otherwise
    reach the repository with `None` and query across every project.
    """
    if context.project_id is None:
        raise ValueError("copilot_project_context_required")
    return context.project_id


def _user_of(context: ToolContext) -> uuid.UUID:
    """The acting user, for anything that writes a row someone owns."""
    if context.user_id is None:
        raise ValueError("copilot_user_context_required")
    return context.user_id


def _kind_allowed(context: ToolContext, kind: str) -> None:
    if context.allowed_kinds is not None and kind not in context.allowed_kinds:
        raise ValueError("research_kind_not_enabled")


# --- Project data (read) -----------------------------------------------------

_register(
    ToolSpec(
        id="list_project_targets",
        citation="project_items",
        description="List the project's targets with their readiness state.",
        parameters={
            "type": "object",
            "properties": {"limit": _limit(50, 20)},
            "additionalProperties": False,
        },
        capability="project-read",
        execution_mode="read",
        requires="project",
        handler=lambda ctx, args: ctx.project.list_targets(limit=_arg_int(args, "limit", 20)),
    )
)

_register(
    ToolSpec(
        id="list_project_candidates",
        citation="project_items",
        description="List design candidates, optionally filtered by status.",
        parameters={
            "type": "object",
            "properties": {"status": {"type": "string"}, "limit": _limit(50, 20)},
            "additionalProperties": False,
        },
        capability="project-read",
        execution_mode="read",
        requires="project",
        handler=lambda ctx, args: ctx.project.list_candidates(
            status=_arg_str(args, "status") or None, limit=_arg_int(args, "limit", 20)
        ),
    )
)

_register(
    ToolSpec(
        id="list_experiment_results",
        citation="project_items",
        description="List recorded experiment results, optionally for one candidate.",
        parameters={
            "type": "object",
            "properties": {"candidate_id": {"type": "string"}, "limit": _limit(50, 20)},
            "additionalProperties": False,
        },
        capability="project-read",
        execution_mode="read",
        requires="project",
        handler=lambda ctx, args: ctx.project.list_experiment_results(
            candidate_id=_arg_str(args, "candidate_id") or None, limit=_arg_int(args, "limit", 20)
        ),
    )
)

_register(
    ToolSpec(
        id="get_workflow_status",
        citation="project_items",
        description="Read workflow run state, optionally for one workflow.",
        parameters={
            "type": "object",
            "properties": {"workflow_id": {"type": "string"}, "limit": _limit(50, 10)},
            "additionalProperties": False,
        },
        capability="project-read",
        execution_mode="read",
        requires="project",
        handler=lambda ctx, args: ctx.project.workflow_status(
            workflow_id=_arg_str(args, "workflow_id") or None, limit=_arg_int(args, "limit", 10)
        ),
    )
)

_register(
    ToolSpec(
        id="get_compute_status",
        citation="project_compute",
        description="Read compute drafts and job state for the project.",
        parameters={
            "type": "object",
            "properties": {"limit": _limit(50, 20)},
            "additionalProperties": False,
        },
        capability="project-read",
        execution_mode="read",
        requires="project",
        handler=lambda ctx, args: ctx.project.compute_status(limit=_arg_int(args, "limit", 20)),
    )
)

_register(
    ToolSpec(
        id="search_project_knowledge",
        citation="project_items",
        description="Search the project's knowledge entries.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": _limit(50, 12)},
            "required": ["query"],
            "additionalProperties": False,
        },
        capability="knowledge-authoring",
        execution_mode="read",
        requires="project",
        handler=lambda ctx, args: ctx.project.search_knowledge(
            _arg_str(args, "query"), limit=_arg_int(args, "limit", 12)
        ),
    )
)


# --- Research workspace (read) ----------------------------------------------

_register(
    ToolSpec(
        id="research_overview",
        description="Project identity, review metadata, category counts, and available kinds.",
        parameters=_EMPTY_OBJECT,
        capability="research-read",
        execution_mode="read",
        requires="research",
        handler=lambda ctx, args: ctx.research.research_overview(),
    )
)

_register(
    ToolSpec(
        id="search_research",
        citation="research_items",
        description="Search the project's Research workspace and return entity-level results.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": _limit(50, 12)},
            "required": ["query"],
            "additionalProperties": False,
        },
        capability="research-read",
        execution_mode="read",
        requires="research",
        handler=lambda ctx, args: ctx.research.search_research(
            _arg_str(args, "query"),
            limit=_arg_int(args, "limit", 12),
            allowed_kinds=ctx.allowed_kinds,
        ),
    )
)


def _get_research_items(ctx: ToolContext, args: dict[str, Any]) -> Any:
    kind = _arg_str(args, "kind")
    _kind_allowed(ctx, kind)
    return ctx.research.get_research_items(
        kind,
        ids=[str(item) for item in args.get("ids", [])],
        offset=_arg_int(args, "offset", 0),
        limit=_arg_int(args, "limit", 20),
    )


_register(
    ToolSpec(
        id="get_research_items",
        citation="research_items",
        description="Page through Research entities of one kind, optionally by exact ids.",
        parameters={
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
                "ids": {"type": "array", "items": {"type": "string"}, "maxItems": 50},
                "offset": {"type": "integer", "minimum": 0},
                "limit": _limit(50, 20),
            },
            "required": ["kind"],
            "additionalProperties": False,
        },
        capability="research-read",
        execution_mode="read",
        requires="research",
        handler=_get_research_items,
    )
)


def _get_dataset_slice(ctx: ToolContext, args: dict[str, Any]) -> Any:
    _kind_allowed(ctx, "dataset")
    return ctx.research.get_dataset_slice(
        _arg_str(args, "dataset_id"),
        offset=_arg_int(args, "offset", 0),
        limit=_arg_int(args, "limit", 25),
    )


_register(
    ToolSpec(
        id="get_dataset_slice",
        citation="research_dataset",
        description="Read a page of rows from a research dataset.",
        parameters={
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string"},
                "offset": {"type": "integer", "minimum": 0},
                "limit": _limit(100, 25),
            },
            "required": ["dataset_id"],
            "additionalProperties": False,
        },
        capability="research-read",
        execution_mode="read",
        requires="research",
        handler=_get_dataset_slice,
    )
)


def _get_reference(ctx: ToolContext, args: dict[str, Any]) -> Any:
    _kind_allowed(ctx, "reference")
    return ctx.research.get_reference(_arg_str(args, "reference_id"))


_register(
    ToolSpec(
        id="get_reference",
        citation="research_reference",
        description="Read one bibliographic reference.",
        parameters={
            "type": "object",
            "properties": {"reference_id": {"type": "string"}},
            "required": ["reference_id"],
            "additionalProperties": False,
        },
        capability="research-read",
        execution_mode="read",
        requires="research",
        handler=_get_reference,
    )
)


def _get_reference_content(ctx: ToolContext, args: dict[str, Any]) -> Any:
    if ctx.allowed_kinds is not None and not (
        {"literature_evidence", "literature_excerpt", "reference"} & ctx.allowed_kinds
    ):
        raise ValueError("research_kind_not_enabled")
    return ctx.research.get_reference_content(
        _arg_str(args, "reference_id"),
        offset=_arg_int(args, "offset", 0),
        limit=_arg_int(args, "limit", 12),
    )


_register(
    ToolSpec(
        id="get_reference_content",
        citation="research_items",
        description="Read saved excerpts and evidence for one reference.",
        parameters={
            "type": "object",
            "properties": {
                "reference_id": {"type": "string"},
                "offset": {"type": "integer", "minimum": 0},
                "limit": _limit(50, 12),
            },
            "required": ["reference_id"],
            "additionalProperties": False,
        },
        capability="research-read",
        execution_mode="read",
        requires="research",
        handler=_get_reference_content,
    )
)


# --- Writes ------------------------------------------------------------------
# Each requires the user to have asked, in their own words, this turn.


def _resolve_research_gaps(ctx: ToolContext, args: dict[str, Any]) -> Any:
    _kind_allowed(ctx, "research_target")
    return ctx.actions.resolve_research_gaps(
        _arg_str(args, "research_target_id"),
        resolve_references=bool(args.get("resolve_references", True)),
        resolve_structure=bool(args.get("resolve_structure", True)),
    )


_register(
    ToolSpec(
        id="resolve_research_gaps",
        description="Fill missing references or structure for one research target.",
        parameters={
            "type": "object",
            "properties": {
                "research_target_id": {"type": "string"},
                "resolve_references": {"type": "boolean"},
                "resolve_structure": {"type": "boolean"},
            },
            "required": ["research_target_id"],
            "additionalProperties": False,
        },
        capability="research-gap-repair",
        execution_mode="queue",
        requires="actions",
        # Awaitable inside a run, ordinary in chat: a chat turn has no run to
        # suspend and never reads `awaits`, so the same tool serves both.
        awaits="operation",
        audit=True,
        handler=_resolve_research_gaps,
    )
)

_register(
    ToolSpec(
        id="start_literature_search",
        description="Queue an auditable Europe PMC search and save retrievable content.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": _limit(25, 5)},
            "required": ["query"],
            "additionalProperties": False,
        },
        capability="literature-search",
        execution_mode="queue",
        requires="actions",
        # Awaitable inside a run, ordinary in chat: a chat turn has no run to
        # suspend and never reads `awaits`, so the same tool serves both.
        awaits="operation",
        audit=True,
        handler=lambda ctx, args: ctx.actions.start_literature_search(
            _arg_str(args, "query"), limit=_arg_int(args, "limit", 5)
        ),
    )
)

_register(
    ToolSpec(
        id="start_target_intelligence",
        description="Queue a target intelligence run.",
        parameters={
            "type": "object",
            "properties": {"target_id": {"type": "string"}, "query": {"type": "string"}},
            "required": ["target_id"],
            "additionalProperties": False,
        },
        capability="target-intelligence",
        execution_mode="queue",
        requires="actions",
        # Awaitable inside a run, ordinary in chat: a chat turn has no run to
        # suspend and never reads `awaits`, so the same tool serves both.
        awaits="operation",
        audit=True,
        handler=lambda ctx, args: ctx.actions.start_target_intelligence(
            _arg_str(args, "target_id"), query=_arg_str(args, "query")
        ),
    )
)

_register(
    ToolSpec(
        id="create_knowledge_draft",
        description="Create a pending-review knowledge note.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
            },
            "required": ["title", "content"],
            "additionalProperties": False,
        },
        capability="knowledge-authoring",
        execution_mode="draft",
        requires="actions",
        audit=True,
        handler=lambda ctx, args: ctx.actions.create_knowledge_draft(
            _arg_str(args, "title"),
            _arg_str(args, "content"),
            tags=[str(item) for item in args.get("tags", [])],
        ),
    )
)


def _create_compute_draft(ctx: ToolContext, args: dict[str, Any]) -> Any:
    specification = args.get("specification")
    if not isinstance(specification, dict):
        raise ValueError("compute_specification_not_object")
    return ctx.actions.create_compute_draft(
        _arg_str(args, "name"), _arg_str(args, "backend"), specification
    )


_register(
    ToolSpec(
        id="create_compute_draft",
        description="Draft a compute submission for a human to confirm.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "backend": {"type": "string"},
                "specification": {"type": "object"},
            },
            "required": ["name", "backend", "specification"],
            "additionalProperties": True,
        },
        capability="compute-drafting",
        execution_mode="draft",
        requires="actions",
        audit=True,
        handler=_create_compute_draft,
    )
)


# --- Wet-lab bench -----------------------------------------------------------
# The agent can work the bench rather than only read about it. Sequences are not
# reachable from here: `list_proteins` returns the same redacted projection the
# API does, so no tool result can carry plaintext into a model prompt.


def _list_proteins(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..wetlab.repository import ProteinRepository
    from ..wetlab.service import to_read

    rows = ProteinRepository(ctx.session).list_project(
        _project_of(ctx),
        None,
        _arg_int(args, "limit", 25),
        search=_arg_str(args, "search") or None,
    )
    return [to_read(row).model_dump(mode="json") for row in rows]


_register(
    ToolSpec(
        id="list_proteins",
        description=(
            "List constructs in the project's protein library. Returns a "
            "fingerprint rather than a sequence; sequences never leave the server."
        ),
        parameters={
            "type": "object",
            "properties": {"search": {"type": "string"}, "limit": _limit(100, 25)},
            "additionalProperties": False,
        },
        capability="wetlab-read",
        execution_mode="read",
        requires="session",
        handler=_list_proteins,
    )
)


def _compute_concentration(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..wetlab.schemas import ConcentrationRequest
    from ..wetlab.service import concentration

    request = ConcentrationRequest(
        a280=float(args.get("a280") or 0),
        protein_id=args.get("protein_id") or None,
        ext_coeff=args.get("ext_coeff") or None,
        molecular_weight=args.get("molecular_weight") or None,
        path_length_cm=float(args.get("path_length_cm") or 1.0),
        cystines=_arg_str(args, "cystines", "reduced"),
    )
    return concentration(ctx.session, _project_of(ctx), request).model_dump(mode="json")


_register(
    ToolSpec(
        id="compute_concentration",
        description=(
            "Quantify a sample by A280 (Beer-Lambert), against a stored construct "
            "or an explicit extinction coefficient and mass."
        ),
        parameters={
            "type": "object",
            "properties": {
                "a280": {"type": "number", "minimum": 0},
                "protein_id": {"type": "string"},
                "ext_coeff": {"type": "number", "exclusiveMinimum": 0},
                "molecular_weight": {"type": "number", "exclusiveMinimum": 0},
                "path_length_cm": {"type": "number", "exclusiveMinimum": 0},
                "cystines": {"type": "string", "enum": ["reduced", "oxidized"]},
            },
            "required": ["a280"],
            "additionalProperties": False,
        },
        capability="wetlab-read",
        execution_mode="read",
        requires="session",
        handler=_compute_concentration,
    )
)


def _plan_dilution_series(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..wetlab.schemas import DilutionRequest
    from ..wetlab.service import dilution_series

    request = DilutionRequest(
        stock_conc_uM=float(args.get("stock_conc_uM") or 0),
        start_conc_uM=float(args.get("start_conc_uM") or 0),
        dilution_factor=float(args.get("dilution_factor") or 2),
        n_steps=_arg_int(args, "n_steps", 6),
        vol_per_well_uL=float(args.get("vol_per_well_uL") or 200),
        extra_dead_vol_uL=float(args.get("extra_dead_vol_uL") or 0),
    )
    return dilution_series(request).model_dump(mode="json")


_register(
    ToolSpec(
        id="plan_dilution_series",
        description="Plan a serial dilution for a BLI concentration gradient.",
        parameters={
            "type": "object",
            "properties": {
                "stock_conc_uM": {"type": "number", "exclusiveMinimum": 0},
                "start_conc_uM": {"type": "number", "exclusiveMinimum": 0},
                "dilution_factor": {"type": "number", "exclusiveMinimum": 1},
                "n_steps": {"type": "integer", "minimum": 1, "maximum": 24},
                "vol_per_well_uL": {"type": "number", "exclusiveMinimum": 0},
                "extra_dead_vol_uL": {"type": "number", "minimum": 0},
            },
            "required": ["stock_conc_uM", "start_conc_uM", "dilution_factor", "n_steps", "vol_per_well_uL"],
            "additionalProperties": False,
        },
        capability="wetlab-read",
        execution_mode="read",
        requires="session",
        handler=_plan_dilution_series,
    )
)


def _promote_candidate_to_bench(ctx: ToolContext, args: dict[str, Any]) -> Any:
    import uuid as _uuid

    from ..wetlab.service import promote_candidate, to_read

    protein = promote_candidate(
        ctx.session,
        _project_of(ctx),
        _user_of(ctx),
        _uuid.UUID(_arg_str(args, "candidate_id")),
    )
    return to_read(protein).model_dump(mode="json")


_register(
    ToolSpec(
        id="promote_candidate_to_bench",
        description=(
            "Register a designed candidate as a construct in the protein library, "
            "so a measured result can find its way back to the design that "
            "predicted it. The candidate must carry a sequence."
        ),
        parameters={
            "type": "object",
            "properties": {"candidate_id": {"type": "string"}},
            "required": ["candidate_id"],
            "additionalProperties": False,
        },
        capability="wetlab-authoring",
        execution_mode="draft",
        requires="session",
        audit=True,
        handler=_promote_candidate_to_bench,
    )
)


def _analyse_instrument_file(kind: str):
    """One handler shape for the three instrument analyses.

    They differ only in which kernel runs and which optional arguments apply;
    writing three near-identical closures would invite them to drift apart.
    """

    def handler(ctx: ToolContext, args: dict[str, Any]) -> Any:
        import uuid as _uuid

        from ..wetlab import analysis

        artifact_id = _uuid.UUID(_arg_str(args, "artifact_id"))
        project_id, user_id = _project_of(ctx), _user_of(ctx)
        candidate = args.get("candidate_id")
        candidate_id = _uuid.UUID(str(candidate)) if candidate else None

        if kind == "bli":
            row, summary = analysis.analyse_bli(
                ctx.session, project_id, user_id, artifact_id,
                sample_id=_arg_str(args, "sample_id") or None,
                t_assoc=args.get("t_assoc"),
                t_dissoc=args.get("t_dissoc"),
                candidate_id=candidate_id,
            )
        elif kind == "akta":
            row, summary = analysis.analyse_akta(
                ctx.session, project_id, user_id, artifact_id,
                channel=_arg_str(args, "channel") or None,
                candidate_id=candidate_id,
            )
        else:
            row, summary = analysis.analyse_enzyme(
                ctx.session, project_id, user_id, artifact_id,
                subtract_background=bool(args.get("subtract_background", True)),
                candidate_id=candidate_id,
            )
        return {
            "experiment_result_id": str(row.id),
            "experiment_type": row.experiment_type,
            "value": row.value,
            "unit": row.unit,
            "summary": summary,
        }

    return handler


_ARTIFACT_ARG = {"artifact_id": {"type": "string"}, "candidate_id": {"type": "string"}}

_register(
    ToolSpec(
        id="analyse_bli_run",
        description=(
            "Fit KD from an uploaded ForteBio BLI export and record the result. "
            "Pass t_assoc/t_dissoc when the run declares them; the fallback "
            "infers the phase boundary from the curve."
        ),
        parameters={
            "type": "object",
            "properties": {
                **_ARTIFACT_ARG,
                "sample_id": {"type": "string"},
                "t_assoc": {"type": "number"},
                "t_dissoc": {"type": "number"},
            },
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
        capability="wetlab-authoring",
        execution_mode="draft",
        requires="session",
        audit=True,
        handler=_analyse_instrument_file("bli"),
    )
)

_register(
    ToolSpec(
        id="analyse_akta_run",
        description="Detect peaks in an uploaded AKTA Unicorn export and record the peak table.",
        parameters={
            "type": "object",
            "properties": {**_ARTIFACT_ARG, "channel": {"type": "string"}},
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
        capability="wetlab-authoring",
        execution_mode="draft",
        requires="session",
        audit=True,
        handler=_analyse_instrument_file("akta"),
    )
)

_register(
    ToolSpec(
        id="analyse_enzyme_plate",
        description="Fit per-well rates from an uploaded TECAN plate export and record them.",
        parameters={
            "type": "object",
            "properties": {**_ARTIFACT_ARG, "subtract_background": {"type": "boolean"}},
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
        capability="wetlab-authoring",
        execution_mode="draft",
        requires="session",
        audit=True,
        handler=_analyse_instrument_file("enzyme"),
    )
)


# --- Research trace ----------------------------------------------------------
# What the project is trying to find out, which is the context that makes the
# rest of the tool results interpretable.


def _list_research_goals(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..research import goals as goal_service

    rows = goal_service.tree(ctx.session, _project_of(ctx))
    links = goal_service.links_for(ctx.session, [row.id for row in rows])
    status = _arg_str(args, "status") or None
    return [
        {
            "id": str(row.id),
            "parent_id": str(row.parent_id) if row.parent_id else None,
            "title": row.title,
            "detail": row.detail,
            "status": row.status,
            "tags": list(row.tags or []),
            "evidence": [
                {"type": link.resource_type, "id": str(link.resource_id), "note": link.note}
                for link in links.get(row.id, [])
            ],
        }
        for row in rows
        if status is None or row.status == status
    ]


_register(
    ToolSpec(
        id="list_research_goals",
        description=(
            "Read the project's research goal tree with the evidence attached to "
            "each goal. Use this to answer what is being investigated and which "
            "goals still have no supporting result."
        ),
        parameters={
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["open", "answered", "abandoned"]}},
            "additionalProperties": False,
        },
        capability="research-read",
        execution_mode="read",
        requires="session",
        handler=_list_research_goals,
    )
)


def _attach_to_research_goal(ctx: ToolContext, args: dict[str, Any]) -> Any:
    import uuid as _uuid

    from ..research import goals as goal_service

    goal = goal_service.require_goal(ctx.session, _uuid.UUID(_arg_str(args, "goal_id")))
    if goal.project_id != _project_of(ctx):
        raise ValueError("research_goal_not_in_project")
    link = goal_service.attach(
        ctx.session,
        goal,
        _user_of(ctx),
        resource_type=_arg_str(args, "resource_type"),
        resource_id=_uuid.UUID(_arg_str(args, "resource_id")),
        note=_arg_str(args, "note"),
    )
    return {"id": str(link.id), "goal_id": str(link.goal_id), "resource_type": link.resource_type}


_register(
    ToolSpec(
        id="attach_to_research_goal",
        description="Attach an existing result, candidate, job or construct to a research goal.",
        parameters={
            "type": "object",
            "properties": {
                "goal_id": {"type": "string"},
                "resource_type": {
                    "type": "string",
                    "enum": ["experiment_result", "finding", "candidate", "job", "protein"],
                },
                "resource_id": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["goal_id", "resource_type", "resource_id"],
            "additionalProperties": False,
        },
        capability="research-trace-authoring",
        execution_mode="draft",
        requires="session",
        audit=True,
        handler=_attach_to_research_goal,
    )
)


# --- Waiting -----------------------------------------------------------------
# The two tools that make a run durable rather than merely long. Both declare
# `requires="agent_run"`, so a chat turn - which has no run to suspend - never
# sees them, and `awaits`, so the loop knows the work outlives the call.


def _await_compute_job(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """Wait for a job that is already running.

    The copilot may not submit compute itself; a draft is confirmed by a human
    and only then becomes a job. What the agent can do is stop until that job
    settles, instead of answering about work that has not happened yet.
    """
    from ..compute.models import Job
    from ..core.statuses import TERMINAL_JOB_STATUSES

    job = ctx.session.get(Job, uuid.UUID(_arg_str(args, "job_id")))
    if job is None or job.project_id != _project_of(ctx):
        raise ValueError("compute_job_not_in_project")
    if job.status in TERMINAL_JOB_STATUSES:
        # Nothing to wait for. Returning without a `resource_id` is how the loop
        # is told to carry on; suspending here would park the run on a task that
        # nothing will ever settle.
        return {
            "job_id": str(job.id),
            "status": job.status,
            "error_code": job.error_code,
            "waiting": False,
        }
    return {
        "resource_id": str(job.id),
        "job_id": str(job.id),
        "status": job.status,
        "waiting": True,
    }


def _spawn_subagent(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """Split off a child run and wait for it.

    The child's tool list is intersected with this run's by `create_run`, so a
    parent cannot widen its own reach by delegating.
    """
    from . import agent_runs

    parent = ctx.agent_run
    requested = [str(item) for item in (args.get("tools") or [])]
    child = agent_runs.create_run(
        ctx.session,
        project_id=parent.project_id,
        user_id=parent.created_by,
        goal=_arg_str(args, "goal"),
        allowed_tools=requested or list(parent.allowed_tools or []),
        conversation_id=parent.conversation_id,
        parent_run_id=parent.id,
        max_turns=min(_arg_int(args, "max_turns", 8), parent.max_turns),
    )
    return {
        "resource_id": str(child.id),
        "run_id": str(child.id),
        "goal": child.goal,
        "allowed_tools": list(child.allowed_tools),
        "waiting": True,
    }


_register(
    ToolSpec(
        id="await_compute_job",
        description=(
            "Stop until a compute job of this project reaches a terminal state. "
            "Returns immediately if it has already finished."
        ),
        parameters={
            "type": "object",
            "properties": {"job_id": {"type": "string"}},
            "required": ["job_id"],
            "additionalProperties": False,
        },
        capability="agent-orchestration",
        execution_mode="read",
        requires="agent_run",
        awaits="gpu_job",
        handler=_await_compute_job,
    )
)

_register(
    ToolSpec(
        id="spawn_subagent",
        description=(
            "Delegate one self-contained part of the goal to a child run and wait "
            "for it. The child may use at most the tools this run may use."
        ),
        parameters={
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "tools": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                "max_turns": {"type": "integer", "minimum": 1, "maximum": 24},
            },
            "required": ["goal"],
            "additionalProperties": False,
        },
        capability="agent-orchestration",
        execution_mode="read",
        requires="agent_run",
        awaits="subagent",
        # Not audited: the child run is its own record, and an audit row per
        # delegation would repeat it without adding anything.
        handler=_spawn_subagent,
    )
)
