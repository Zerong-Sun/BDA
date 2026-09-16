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

from sqlalchemy import select

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
        id="start_patent_search",
        description=(
            "Queue an audited patent search and save each hit with its retrieval trace. "
            "database 'europe_pmc' (the default) searches Europe PMC's patent index - "
            "Chinese (CN), US, European (EP), PCT (WO), Japanese and Korean publications - "
            "with the query in Europe PMC syntax. 'epo_ops' searches EPO Open Patent "
            "Services, the worldwide DOCDB collection with a patent family id on every "
            "record; write its query as OPS CQL - every value after all/any/within must be "
            "quoted, for example: ta all \"PD-1 antibody\" and pa all \"merck\" - or as plain "
            "words, which become an all-words title/abstract search. "
            "jurisdictions restricts either one to those offices. Report it as queued: it "
            "is not done until the results are saved, and only saved patents can be cited. "
            "A search returns the most relevant publications, not every one, and finding "
            "none does not show that none exist."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": _limit(25, 10),
                "database": {"type": "string", "enum": ["europe_pmc", "epo_ops"]},
                "jurisdictions": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["CN", "US", "EP", "WO", "JP", "KR"]},
                    "maxItems": 6,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        capability="patent-search",
        execution_mode="queue",
        requires="actions",
        awaits="operation",
        audit=True,
        handler=lambda ctx, args: ctx.actions.start_patent_search(
            _arg_str(args, "query"),
            limit=_arg_int(args, "limit", 10),
            database=_arg_str(args, "database", "europe_pmc"),
            jurisdictions=tuple(str(code) for code in (args.get("jurisdictions") or [])),
        ),
    )
)

_register(
    ToolSpec(
        id="start_patent_legal_status_lookup",
        description=(
            "Queue an audited EPO Open Patent Services lookup of up to 25 patents this "
            "project has already saved: each one's DOCDB patent family (its publications "
            "by office) and the INPADOC legal events of its application, per country, with "
            "dates. Use document_id values from summarise_patent_landscape. Report it as "
            "queued; once it has run, summarise_patent_landscape shows the events. An "
            "event is not a status: report the event, its country and its date, never call "
            "a patent in force, lapsed, expired or valid from events, and never present "
            "them as a freedom-to-operate opinion."
        ),
        parameters={
            "type": "object",
            "properties": {
                "document_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 25},
            },
            "required": ["document_ids"],
            "additionalProperties": False,
        },
        capability="patent-search",
        execution_mode="queue",
        requires="actions",
        awaits="operation",
        audit=True,
        handler=lambda ctx, args: ctx.actions.start_patent_legal_status_lookup(
            [str(item) for item in (args.get("document_ids") or [])]
        ),
    )
)


def _summarise_patent_landscape(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..literature import patent_service

    raw_run = _arg_str(args, "search_run_id")
    jurisdictions = args.get("jurisdictions") or []
    return patent_service.project_landscape(
        ctx.session,
        _project_of(ctx),
        search_run_id=uuid.UUID(raw_run) if raw_run else None,
        jurisdictions=tuple(str(code) for code in jurisdictions),
    )


_register(
    ToolSpec(
        id="summarise_patent_landscape",
        description=(
            "Summarise the patents this project has already saved: publications by office "
            "(CN, US, EP, WO, JP, KR), by stage (application, granted, PCT, utility model), "
            "top applicants, IPC subclasses, priority years and an estimated-term count, "
            "distinct patent families, with each listed record's document and retrieval "
            "trace. A publication saved by both indexes is counted once. It reads saved "
            "patents only and runs no search. Legal events appear only for records looked "
            "up with start_patent_legal_status_lookup, as the latest event per country: "
            "never call a patent in force, expired or granted-and-valid from this result, "
            "and never present it as a freedom-to-operate opinion."
        ),
        parameters={
            "type": "object",
            "properties": {
                "search_run_id": {"type": "string"},
                "jurisdictions": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["CN", "US", "EP", "WO", "JP", "KR"]},
                    "maxItems": 6,
                },
            },
            "additionalProperties": False,
        },
        capability="patent-search",
        execution_mode="read",
        requires="session",
        handler=_summarise_patent_landscape,
    )
)

_register(
    ToolSpec(
        id="start_druggability_assessment",
        description=(
            "Queue a druggability assessment of one exact project Target (it must have a "
            "UniProt accession): Open Targets tractability by modality with the evidence "
            "behind each, drugs and clinical candidates with their furthest stage, recorded "
            "safety liabilities, and ClinicalTrials.gov registrations by phase for a search "
            "term (default: the target's name). Every call is audited and saved with the "
            "report. It gives evidence and named gaps, never a druggability probability, and "
            "no market size. Optional candidate_id adds measured sequence liabilities with a digest; no sequence is returned. Report it as queued until it finishes."
        ),
        parameters={
            "type": "object",
            "properties": {
                "target_id": {"type": "string"},
                "candidate_id": {"type": "string"},
                "trial_term": {"type": "string", "maxLength": 200},
            },
            "required": ["target_id"],
            "additionalProperties": False,
        },
        capability="druggability-assessment",
        execution_mode="queue",
        requires="actions",
        awaits="operation",
        audit=True,
        handler=lambda ctx, args: ctx.actions.start_druggability_assessment(
            _arg_str(args, "target_id"), trial_term=str(args.get("trial_term") or ""),
            candidate_id=str(args["candidate_id"]) if args.get("candidate_id") else None
        ),
    )
)


def _get_druggability_assessment(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..intelligence import druggability_service

    return druggability_service.read_assessment(
        ctx.session, _project_of(ctx), uuid.UUID(_arg_str(args, "intelligence_run_id"))
    )


_register(
    ToolSpec(
        id="get_druggability_assessment",
        description=(
            "Read a saved druggability assessment by its intelligence run id: tractability, "
            "clinical candidates, safety liabilities, trial activity, the gaps and limits, and "
            "the audited retrieval behind each section. An empty safety list means none "
            "recorded in Open Targets, never that a target is safe."
        ),
        parameters={
            "type": "object",
            "properties": {"intelligence_run_id": {"type": "string"}},
            "required": ["intelligence_run_id"],
            "additionalProperties": False,
        },
        capability="druggability-assessment",
        execution_mode="read",
        requires="session",
        handler=_get_druggability_assessment,
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
    agent_runs.enqueue_first_step(ctx.session, child)
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


# --- Structure (read) --------------------------------------------------------
# Residue-level reads over an uploaded structure artifact. All three are
# measurements: they report what the coordinates say and never what it means.
# `structures.service` does the artifact lookup and the project check, so these
# handlers stay as thin as the rest of the catalogue.


def _structure_handler(kind: str):
    def handler(ctx: ToolContext, args: dict[str, Any]) -> Any:
        from ..structures import service as structures

        artifact_id = uuid.UUID(_arg_str(args, "artifact_id"))
        project_id = _project_of(ctx)
        if kind == "analyse":
            return structures.analyse(ctx.session, project_id, artifact_id)
        if kind == "contacts":
            return structures.contacts(
                ctx.session,
                project_id,
                artifact_id,
                chain_a=_arg_str(args, "chain_a"),
                chain_b=_arg_str(args, "chain_b"),
                cutoff_angstrom=float(args.get("cutoff_angstrom") or 4.5),
            )
        if kind == "interface":
            return structures.interface(
                ctx.session,
                project_id,
                artifact_id,
                chain_a=_arg_str(args, "chain_a"),
                chain_b=_arg_str(args, "chain_b"),
                cutoff_angstrom=float(args.get("cutoff_angstrom") or 4.5),
            )
        residue = args.get("residue_seq")
        return structures.site(
            ctx.session,
            project_id,
            artifact_id,
            chain=_arg_str(args, "chain") or None,
            residue_seq=int(residue) if residue is not None else None,
            ligand=_arg_str(args, "ligand") or None,
            radius_angstrom=float(args.get("radius_angstrom") or 5.0),
        )

    return handler


_register(
    ToolSpec(
        id="analyse_structure",
        description=(
            "Read a PDB or mmCIF artifact: chains, residue counts, per-chain "
            "sequence, numbering gaps, ligands, disulfides and B-factor/pLDDT "
            "statistics. Start here before asking about any residue, because the "
            "chain ids and numbering this returns are what the other structure "
            "tools take as arguments."
        ),
        parameters={
            "type": "object",
            "properties": {"artifact_id": {"type": "string"}},
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
        capability="structure-analysis",
        execution_mode="read",
        requires="session",
        handler=_structure_handler("analyse"),
    )
)

_register(
    ToolSpec(
        id="list_structure_contacts",
        coerce_numeric_strings=True,
        description=(
            "Residue pairs across two chains within a heavy-atom cutoff, each with "
            "its closest atom pair and distance in angstroms. This is the interface "
            "as measurement; it does not identify an epitope or a binding site."
        ),
        parameters={
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "chain_a": {"type": "string"},
                "chain_b": {"type": "string"},
                "cutoff_angstrom": {"type": "number", "minimum": 0.5, "maximum": 12, "default": 4.5},
            },
            "required": ["artifact_id", "chain_a", "chain_b"],
            "additionalProperties": False,
        },
        capability="structure-analysis",
        execution_mode="read",
        requires="session",
        handler=_structure_handler("contacts"),
    )
)

def _compare_structures(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..structures import service as structures

    return structures.superpose(
        ctx.session,
        _project_of(ctx),
        uuid.UUID(_arg_str(args, "reference_artifact_id")),
        uuid.UUID(_arg_str(args, "mobile_artifact_id")),
        reference_chain=_arg_str(args, "reference_chain"),
        mobile_chain=_arg_str(args, "mobile_chain"),
    )


_register(
    ToolSpec(
        id="compare_structures",
        description=(
            "Fit one structure onto another and report how far off it lands: "
            "RMSD over C-alpha atoms before and after the fit, the residues "
            "that moved most, and a TM-score when the chain is long enough for "
            "its formula. Residues are paired by author numbering, so the two "
            "files must use the same numbering; a file missing a loop still "
            "compares correctly. Use it for a design against its prediction, or "
            "a prediction against a solved structure. The TM-score is evaluated "
            "on this superposition and is not a TM-align result."
        ),
        parameters={
            "type": "object",
            "properties": {
                "reference_artifact_id": {"type": "string"},
                "mobile_artifact_id": {"type": "string"},
                "reference_chain": {"type": "string"},
                "mobile_chain": {"type": "string"},
            },
            "required": [
                "reference_artifact_id",
                "mobile_artifact_id",
                "reference_chain",
                "mobile_chain",
            ],
            "additionalProperties": False,
        },
        capability="structure-analysis",
        execution_mode="read",
        requires="session",
        handler=_compare_structures,
    )
)

_register(
    ToolSpec(
        id="measure_structure_interface",
        coerce_numeric_strings=True,
        description=(
            "How much surface two chains bury and what the contact is made of: "
            "buried area per side and the conventional interface area, per-residue "
            "burial, hydrogen bonds, salt bridges and the hydrophobic fraction. "
            "Use it to judge a complex that has not been scored by a design tool. "
            "Hydrogens are absent from most of these files, so a hydrogen bond is "
            "a donor/acceptor distance with no angle term, and the result says so. "
            "Buried area is not an affinity."
        ),
        parameters={
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "chain_a": {"type": "string"},
                "chain_b": {"type": "string"},
                "cutoff_angstrom": {"type": "number", "minimum": 0.5, "maximum": 12, "default": 4.5},
            },
            "required": ["artifact_id", "chain_a", "chain_b"],
            "additionalProperties": False,
        },
        capability="structure-analysis",
        execution_mode="read",
        requires="session",
        handler=_structure_handler("interface"),
    )
)

_register(
    ToolSpec(
        id="describe_structure_site",
        coerce_numeric_strings=True,
        description=(
            "Residues within a radius of one named centre - a residue given as "
            "chain plus residue_seq, or a ligand given by its component code. "
            "Name exactly one; the tool will not choose a centre for you."
        ),
        parameters={
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "chain": {"type": "string"},
                "residue_seq": {"type": "integer"},
                "ligand": {"type": "string"},
                "radius_angstrom": {"type": "number", "minimum": 0.5, "maximum": 12, "default": 5.0},
            },
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
        capability="structure-analysis",
        execution_mode="read",
        requires="session",
        handler=_structure_handler("site"),
    )
)


# --- Failure diagnosis (read) ------------------------------------------------


def _diagnose_compute_failure(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..compute import diagnosis

    return diagnosis.diagnose(
        ctx.session, _project_of(ctx), uuid.UUID(_arg_str(args, "job_id"))
    )


_register(
    ToolSpec(
        id="diagnose_compute_failure",
        description=(
            "Gather one job's recorded evidence - status, error, attempt history, "
            "events and the runtime spec it declared - and report the failure "
            "causes that evidence supports, each marked confirmed or possible. "
            "An empty finding list means the evidence determines no cause; do not "
            "supply one."
        ),
        parameters={
            "type": "object",
            "properties": {"job_id": {"type": "string"}},
            "required": ["job_id"],
            "additionalProperties": False,
        },
        capability="failure-diagnosis",
        execution_mode="read",
        requires="session",
        handler=_diagnose_compute_failure,
    )
)


# --- Chain: how operators talk, and how one directs another ------------------
# The roster's `handoff` tuple named a successor and carried nothing across the
# boundary. These tools are the channel. `post_handoff` writes the copilot's own
# transcript and changes no research record, which is why it declares
# `intent="internal"` - see `registry.ToolSpec.intent`; it is still audited, and
# it is still a write in every other sense.


def _bot_of(ctx: ToolContext) -> str:
    """The operator making this call.

    An unowned turn cannot hand over: a note whose sender is "the assistant"
    names nobody accountable, and the reviewer would have no charter to check it
    against. Refused rather than defaulted for that reason.
    """
    run = getattr(ctx, "agent_run", None)
    bot = getattr(run, "bot", None) or getattr(ctx, "bot", None)
    if not bot:
        raise ValueError("copilot_bot_context_required")
    return str(bot)


def _post_handoff(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from . import handoffs

    run = getattr(ctx, "agent_run", None)
    row = handoffs.record(
        ctx.session,
        project_id=_project_of(ctx),
        user_id=_user_of(ctx),
        from_bot=_bot_of(ctx),
        to_bot=_arg_str(args, "to_bot"),
        summary=_arg_str(args, "summary"),
        claims=args.get("claims"),
        open_questions=args.get("open_questions"),
        refs=args.get("refs"),
        produced_by_run=getattr(run, "id", None),
    )
    result = handoffs.to_json(row)
    # Reported back rather than rejected: `normalise_claims` downgrades a claim
    # with no reference to "unsupported", and an operator that believes it cited
    # something should be told it did not while it can still fix the note.
    result["unsupported_claims"] = sum(
        1 for claim in result["claims"] if claim.get("confidence") == "unsupported"
    )
    result["off_chain"] = handoffs.is_off_chain(row.from_bot, row.to_bot)
    return result


def _read_handoffs(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from . import handoffs

    rows = handoffs.inbox(
        ctx.session,
        project_id=_project_of(ctx),
        to_bot=_arg_str(args, "to_bot") or None,
        from_bot=_arg_str(args, "from_bot") or None,
        limit=_arg_int(args, "limit", handoffs.DEFAULT_LIMIT),
    )
    return [handoffs.to_json(row) for row in rows]


_CLAIM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "statement": {"type": "string"},
        "evidence_ref": {
            "type": "string",
            "description": (
                "The artifact, job, result, reference or goal id this rests on. "
                "A claim with none is recorded as unsupported."
            ),
        },
        "confidence": {"type": "string", "enum": ["stated", "consistent", "unsupported"]},
    },
    "required": ["statement"],
    "additionalProperties": False,
}

_register(
    ToolSpec(
        id="post_handoff",
        description=(
            "Leave a structured handover for the next operator: what you did, the "
            "claims you are making with the evidence behind each one, what you "
            "could not settle, and the ids the next operator needs. Append-only."
        ),
        parameters={
            "type": "object",
            "properties": {
                "to_bot": {"type": "string"},
                "summary": {"type": "string"},
                "claims": {"type": "array", "items": _CLAIM_SCHEMA, "maxItems": 20},
                "open_questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 20,
                },
                "refs": {"type": "array", "items": {"type": "string"}, "maxItems": 40},
            },
            "required": ["to_bot", "summary"],
            "additionalProperties": False,
        },
        capability="chain-messaging",
        execution_mode="draft",
        requires="session",
        intent="internal",
        needs_operator=True,
        audit=True,
        handler=_post_handoff,
    )
)

_register(
    ToolSpec(
        id="read_handoffs",
        description=(
            "Read handovers recorded in this project, newest first. Filter by "
            "`to_bot` for your own inbox or by `from_bot` to read what one "
            "operator has been claiming."
        ),
        parameters={
            "type": "object",
            "properties": {
                "to_bot": {"type": "string"},
                "from_bot": {"type": "string"},
                "limit": _limit(100, 20),
            },
            "additionalProperties": False,
        },
        capability="chain-messaging",
        execution_mode="read",
        requires="session",
        handler=_read_handoffs,
    )
)


def _list_operator_charters(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """The charters a reviewer rules against.

    Returned as data rather than assumed known, because `outside_charter` is a
    verdict about a specific sentence and a reviewer quoting a charter from
    memory is inventing the standard it is applying.
    """
    from . import bots as roster

    wanted = _arg_str(args, "bot")
    specs = [roster.require(wanted)] if wanted else roster.producers()
    return [
        {
            "id": bot.id,
            "title": bot.title,
            "stance": bot.stance,
            "summary": bot.summary,
            "charter": bot.charter,
            "reviewed_by": [other.id for other in roster.reviewers_of(bot.id)],
        }
        for bot in specs
    ]


def _read_operator_work(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """What an operator actually called, not what it said it did.

    The gap between the two is the whole subject of review, so this returns the
    recorded tool calls rather than the assistant text around them.
    """
    from . import agent_runs

    run = agent_runs.require_run(ctx.session, uuid.UUID(_arg_str(args, "run_id")))
    if run.project_id != _project_of(ctx):
        # Same shape as a missing run: whether a run exists in another project
        # is not this project's to learn.
        raise ValueError("copilot_agent_run_not_found")

    turns = agent_runs.turns_for(ctx.session, run, limit=_arg_int(args, "limit", 40))
    calls: list[dict[str, Any]] = []
    for turn in turns:
        for call in turn.tool_calls or []:
            calls.append({"sequence": turn.sequence, "role": turn.role, **dict(call)})
    return {
        "run_id": str(run.id),
        "bot": run.bot,
        "goal": run.goal,
        "status": run.status,
        "turn_count": run.turn_count,
        "allowed_tools": list(run.allowed_tools or []),
        "tool_calls": calls,
    }


_register(
    ToolSpec(
        id="list_operator_charters",
        description=(
            "The charter each operator works under, and who reviews it. This is "
            "the standard an `outside_charter` verdict is measured against."
        ),
        parameters={
            "type": "object",
            "properties": {"bot": {"type": "string"}},
            "additionalProperties": False,
        },
        capability="review-audit",
        execution_mode="read",
        requires="session",
        handler=_list_operator_charters,
    )
)

_register(
    ToolSpec(
        id="read_operator_work",
        description=(
            "What an operator's run actually called and what came back, turn by "
            "turn. Use this rather than its summary: the summary is the thing "
            "under review."
        ),
        parameters={
            "type": "object",
            "properties": {"run_id": {"type": "string"}, "limit": _limit(100, 40)},
            "required": ["run_id"],
            "additionalProperties": False,
        },
        capability="review-audit",
        execution_mode="read",
        requires="session",
        handler=_read_operator_work,
    )
)


def _list_operators(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """The roster as a director sees it: who exists and who is reachable now.

    `reachable` is the project's enabled skills intersected with each bot's
    capabilities. A director that delegates to an operator with nothing enabled
    produces a child run with no tools, which looks like the operator failing
    rather than the project not granting it anything.
    """
    from . import bots as roster

    enabled = set(getattr(ctx, "allowed_capabilities", None) or ())
    # Not `_bot_of`: reading the roster is the same for everyone, and a turn that
    # has not chosen an operator is exactly the one most likely to be asking who
    # the operators are. Without a director, nothing is delegable.
    me = str(getattr(getattr(ctx, "agent_run", None), "bot", None) or getattr(ctx, "bot", None) or "")
    return [
        {
            "id": bot.id,
            "title": bot.title,
            "title_zh": bot.title_zh,
            "stance": bot.stance,
            "summary": bot.summary,
            "capabilities": list(bot.capabilities),
            "resolved_capabilities": sorted(set(bot.capabilities) & enabled) if enabled else None,
            "may_delegate_to": roster.may_direct(me, bot.id),
            "handoff": list(bot.handoff),
        }
        for bot in roster.all_bots()
    ]


def _delegate_to_operator(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """Open a child run owned by a different operator, and wait for it.

    Two properties make this routing rather than an escalation, and both are
    enforced here because a charter asking for them would be a request:

    * the child resolves the *target* bot's capabilities against the project and
      is then intersected with this run's tools by `create_run`, so delegating
      can only ever narrow;
    * the child inherits the originating user's request text, never the
      director's instruction. The write-intent gate reads the user's own words,
      so a director able to supply them could write "please submit this job" and
      unlock every write in the project. The instruction steers the work; it
      cannot authorise it.
    """
    from . import agent_runs
    from . import bots as roster
    from .capabilities import tools_for_capabilities

    parent = ctx.agent_run
    # Read leniently so an undifferentiated run fails the *delegation* check
    # rather than a missing-context one: "this run is not a director" is the
    # accurate reason, and `may_direct` says exactly that for an empty id.
    director = str(getattr(parent, "bot", None) or getattr(ctx, "bot", None) or "")
    target = _arg_str(args, "bot")
    if not roster.may_direct(director, target):
        raise ValueError("copilot_delegation_not_allowed")

    enabled = getattr(ctx, "allowed_capabilities", None)
    if enabled is None:
        # Refused rather than defaulted to the target's full declaration. This
        # is the one value that bounds the child, so a missing one has to stop
        # the call: falling back would hand a delegated operator every
        # capability it declares regardless of what the project enabled.
        raise ValueError("copilot_project_capabilities_required")
    resolved = roster.capabilities_for_bot(target, set(enabled))
    if not resolved:
        raise ValueError("copilot_delegate_no_capabilities")

    child = agent_runs.create_run(
        ctx.session,
        project_id=parent.project_id,
        user_id=parent.created_by,
        goal=_arg_str(args, "instruction"),
        allowed_tools=sorted(tools_for_capabilities(resolved)),
        conversation_id=parent.conversation_id,
        parent_run_id=parent.id,
        max_turns=min(_arg_int(args, "max_turns", 8), parent.max_turns),
        bot=target,
    )
    agent_runs.enqueue_first_step(ctx.session, child)
    return {
        "resource_id": str(child.id),
        "run_id": str(child.id),
        "bot": child.bot,
        "goal": child.goal,
        "allowed_tools": list(child.allowed_tools),
        "waiting": True,
    }


_register(
    ToolSpec(
        id="list_operators",
        description=(
            "The roster: every operator, what it is for, and whether this "
            "project has enabled what it needs. Read this before delegating."
        ),
        parameters=_EMPTY_OBJECT,
        capability="chain-orchestration",
        execution_mode="read",
        requires="session",
        handler=_list_operators,
    )
)

_register(
    ToolSpec(
        id="delegate_to_operator",
        description=(
            "Hand one step to a different operator and wait for it. The child "
            "runs under that operator's charter and resolves that operator's "
            "capabilities, never yours, and it cannot perform a write the user "
            "did not ask for - your instruction steers the work and does not "
            "authorise it."
        ),
        parameters={
            "type": "object",
            "properties": {
                "bot": {"type": "string"},
                "instruction": {
                    "type": "string",
                    "description": "What to produce, and what would make the step finished.",
                },
                "max_turns": {"type": "integer", "minimum": 1, "maximum": 24},
            },
            "required": ["bot", "instruction"],
            "additionalProperties": False,
        },
        capability="chain-orchestration",
        execution_mode="read",
        requires="agent_run",
        needs_operator=True,
        awaits="subagent",
        handler=_delegate_to_operator,
    )
)


def _review_compute_declaration(ctx: ToolContext, args: dict[str, Any]) -> Any:
    """What a plugin declares against what the cluster will give it.

    Added because `auditor`'s resource-review charter named a comparison no tool could make.
    `get_compute_status` returns a draft's free-form specification, while the
    numbers that reach LSF live on the plugin registry row and on the queue - so
    the reviewer was being asked to check four things it could not see, which is
    the same defect the roster already fixed once in `archivist` (now part of `analyst`).
    """
    from ..compute import declarations
    from ..registry.models import ComputeNode, ModelPlugin
    from ..workflows.models import WorkflowNode

    plugin_id = _arg_str(args, "plugin_id")
    node_id = _arg_str(args, "node_id")
    if not plugin_id and not node_id:
        raise ValueError("copilot_plugin_or_node_required")
    if node_id:
        # A reviewer reads the route before it reads the plugin, so a workflow
        # node is the identifier it actually has. Resolved here rather than left
        # to the model to look up, which would be a second chance to pick the
        # wrong plugin by name.
        node = ctx.session.get(WorkflowNode, uuid.UUID(node_id))
        if node is None or node.model_plugin_id is None:
            raise ValueError("workflow_node_has_no_plugin")
        plugin_id = str(node.model_plugin_id)

    plugin = ctx.session.get(ModelPlugin, uuid.UUID(plugin_id))
    if plugin is None:
        raise ValueError("registry_plugin_not_found")

    queue = _arg_str(args, "queue") or None
    backend = _arg_str(args, "backend") or "lsf"
    if queue is None:
        # The queue is chosen at submission and is what merges a GPU request in,
        # so a review with no queue named is a review of half the question. The
        # project's own node is the honest default; when there is none the
        # finding set simply cannot include the queue rules, and says so through
        # a null `queue` rather than by assuming a safe one.
        node = ctx.session.scalars(
            select(ComputeNode).where(ComputeNode.backend == backend, ComputeNode.enabled.is_(True))
        ).first()
        if node is not None:
            queue = node.queue

    return declarations.review(
        plugin_key=plugin.plugin_key,
        plugin_version=plugin.plugin_version,
        resources=dict(plugin.resources or {}),
        backend=backend,
        queue=queue,
    )


_register(
    ToolSpec(
        id="review_compute_declaration",
        description=(
            "Compare what a compute plugin declares it needs - slots, per-host "
            "span, GPU - against what the chosen queue will actually give it. "
            "Returns the directives that would be submitted and the "
            "disagreements, and says plainly when the declaration is sound."
        ),
        parameters={
            "type": "object",
            "properties": {
                "plugin_id": {"type": "string"},
                "node_id": {
                    "type": "string",
                    "description": "A workflow node, whose plugin is read from it. Use this or plugin_id.",
                },
                "queue": {
                    "type": "string",
                    "description": "The queue this would be submitted to. Omitted, the project's enabled node is used.",
                },
                "backend": {"type": "string", "enum": ["lsf", "docker"]},
            },
            "additionalProperties": False,
        },
        capability="review-audit",
        execution_mode="read",
        requires="session",
        handler=_review_compute_declaration,
    )
)


def _plan_workflow_route(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..projects.models import Project
    from .schemas import RoutePlanCreate
    from .service import create_route_plan

    project = ctx.session.get(Project, _project_of(ctx))
    if project is None:
        raise ValueError("project_not_found")
    # Deterministic catalog generation; this agent compares the returned choices.
    return create_route_plan(ctx.session, project, RoutePlanCreate(project_id=project.id, goal=args["goal"])).model_dump(mode="json")


_register(ToolSpec(
    id="plan_workflow_route", description="Compare registered workflow routes and missing inputs. Does not create or submit a workflow.",
    parameters={"type": "object", "properties": {"goal": {"type": "string", "minLength": 1, "maxLength": 5000}}, "required": ["goal"], "additionalProperties": False},
    capability="workflow-planning", execution_mode="read", requires="session", handler=_plan_workflow_route,
))


def _request_decision(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from . import decisions

    run = getattr(ctx, "agent_run", None)
    row = decisions.record(
        ctx.session,
        project_id=_project_of(ctx),
        user_id=_user_of(ctx),
        asked_by=_bot_of(ctx),
        question=_arg_str(args, "question"),
        options=args.get("options"),
        recommended=_arg_str(args, "recommended") or None,
        run_id=getattr(run, "id", None),
    )
    return decisions.to_json(row)


_DECISION_OPTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "key": {"type": "string", "maxLength": 80, "description": "Short id for this option; generated if omitted."},
        "label": {"type": "string", "description": "The option, as the person will read it."},
        "rationale": {
            "type": "string",
            "description": "Why this option, and what it costs. Recorded as absent when omitted.",
        },
        "evidence_refs": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 20,
            "description": "Ids this option rests on: an artifact, job, result, reference or goal.",
        },
    },
    "required": ["label"],
    "additionalProperties": False,
}

_register(
    ToolSpec(
        id="request_decision",
        description=(
            "Ask the person to settle one choice you may not settle yourself. "
            "State the question, two to six options, and what each rests on. "
            "Use it when the choice is irreversible or is a matter of value "
            "rather than of method - spending cluster budget, putting material "
            "on a bench, choosing which residues a design will target. Do not "
            "use it for a question the record already answers, and do not use "
            "it to ask permission for something you were already asked to do."
        ),
        parameters={
            "type": "object",
            "properties": {
                "question": {"type": "string", "minLength": 1, "maxLength": 2000},
                "options": {
                    "type": "array",
                    "items": _DECISION_OPTION_SCHEMA,
                    "minItems": 2,
                    "maxItems": 6,
                },
                "recommended": {
                    "type": "string",
                    "maxLength": 80,
                    "description": "The key of the option you would pick, if you have one.",
                },
            },
            "required": ["question", "options"],
            "additionalProperties": False,
        },
        capability="chain-messaging",
        execution_mode="draft",
        requires="session",
        # Copilot bookkeeping, like a handover: it changes no research record,
        # and asking a person a question is not an action taken on their behalf.
        intent="internal",
        needs_operator=True,
        audit=True,
        handler=_request_decision,
    )
)


# --- Structure interaction (draft) -------------------------------------------
#
# Reading a structure says what is there; these three are how an operator points
# at part of it and how a person answers. The split between them is the design:
# `render_structure_view` shows, `propose_hotspot_set` writes something pending,
# and `request_residue_selection` hands the choice to a person. None of them can
# confirm a set - that is a REST endpoint behind `require_command`, because a
# confirmed set is what reaches a design job.


def _residue_list(args: dict[str, Any], field: str) -> list[dict[str, Any]]:
    raw = args.get(field)
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field}_must_be_a_list")
    return [entry for entry in raw if isinstance(entry, dict)]


def _render_structure_view(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..structures import service as structures_service

    return structures_service.view(
        ctx.session,
        _project_of(ctx),
        uuid.UUID(_arg_str(args, "artifact_id")),
        residues=_residue_list(args, "residues"),
        title=_arg_str(args, "title"),
        label=_arg_str(args, "label"),
    )


def _propose_hotspot_set(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..targets import hotspots
    from ..targets.models import Target

    target_id = uuid.UUID(_arg_str(args, "target_id"))
    target = ctx.session.get(Target, target_id)
    if target is None or target.project_id != _project_of(ctx):
        # Same answer for "no such target" and "another project's target": the
        # difference would tell a caller which ids exist elsewhere.
        raise ValueError("target_not_found")
    structure = _arg_str(args, "structure_artifact_id")
    row = hotspots.record(
        ctx.session,
        project_id=_project_of(ctx),
        target_id=target.id,
        user_id=_user_of(ctx),
        label=_arg_str(args, "label"),
        residues=_residue_list(args, "residues"),
        # Not a parameter. A tool that could send `origin="human"` could mint a
        # confirmed set, which is the one thing this table exists to prevent.
        origin="agent",
        structure_artifact_id=uuid.UUID(structure) if structure else None,
        rationale=_arg_str(args, "rationale"),
        evidence_refs=args.get("evidence_refs"),
    )
    result = hotspots.to_json(row)
    result["next_step"] = (
        "Pending. A person confirms it before any design job can use it; say what "
        "you would run with it and why, rather than assuming it is settled."
    )
    return result


def _request_residue_selection(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from . import decisions

    run = getattr(ctx, "agent_run", None)
    candidates = args.get("candidate_sets")
    if not isinstance(candidates, list) or not (2 <= len(candidates) <= 6):
        raise ValueError("candidate_sets_must_offer_between_two_and_six_options")
    options = []
    # The option key is generated by `decisions.normalise_options` when absent,
    # so the position is not needed here.
    for entry in candidates:
        if not isinstance(entry, dict):
            raise ValueError("each_candidate_set_must_be_an_object")
        residues = [item for item in (entry.get("residues") or []) if isinstance(item, dict)]
        listed = ", ".join(
            f"{residue.get('chain')}{residue.get('seq')}" for residue in residues
        )
        options.append(
            {
                "key": str(entry.get("key") or "")[:80],
                "label": f"{entry.get('label') or 'Option'}: {listed}" if listed else str(entry.get("label") or "Option"),
                "rationale": str(entry.get("rationale") or ""),
                "evidence_refs": [
                    str(ref) for ref in (entry.get("evidence_refs") or []) if str(ref).strip()
                ],
            }
        )
    row = decisions.record(
        ctx.session,
        project_id=_project_of(ctx),
        user_id=_user_of(ctx),
        asked_by=_bot_of(ctx),
        question=_arg_str(args, "question"),
        options=options,
        recommended=_arg_str(args, "recommended") or None,
        run_id=getattr(run, "id", None),
    )
    return decisions.to_json(row)


_RESIDUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "chain": {"type": "string", "maxLength": 4, "description": "Author chain id, as the file writes it."},
        "seq": {"type": "integer", "description": "Author residue number, as the viewer shows it."},
        "name": {"type": "string", "maxLength": 8},
    },
    "required": ["chain", "seq"],
    "additionalProperties": False,
}

_register(
    ToolSpec(
        id="render_structure_view",
        description=(
            "Show a structure with named residues picked out, as a MolViewSpec "
            "scene the viewer renders. Use it to make 'the interface I mean' "
            "unambiguous before arguing about it. It shows; it concludes "
            "nothing - the residues you pass are the ones you already measured."
        ),
        parameters={
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "residues": {"type": "array", "items": _RESIDUE_SCHEMA, "maxItems": 200},
                "title": {"type": "string", "maxLength": 200},
                "label": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "One label for the highlighted set, drawn in the scene.",
                },
            },
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
        capability="structure-interaction",
        execution_mode="read",
        requires="session",
        handler=_render_structure_view,
    )
)

_register(
    ToolSpec(
        id="propose_hotspot_set",
        description=(
            "Propose the residues a design should target, with the reason and "
            "the evidence behind them. The set is recorded as pending: a person "
            "confirms it, and only a confirmed set can reach a design job. Do "
            "not describe it as decided."
        ),
        parameters={
            "type": "object",
            "properties": {
                "target_id": {"type": "string"},
                "label": {"type": "string", "minLength": 1, "maxLength": 200},
                "residues": {
                    "type": "array",
                    "items": _RESIDUE_SCHEMA,
                    "minItems": 1,
                    "maxItems": 40,
                },
                "structure_artifact_id": {
                    "type": "string",
                    "description": "The structure the residues were read off.",
                },
                "rationale": {"type": "string", "maxLength": 2000},
                "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
            },
            "required": ["target_id", "label", "residues"],
            "additionalProperties": False,
        },
        capability="structure-interaction",
        execution_mode="draft",
        requires="session",
        needs_operator=True,
        audit=True,
        handler=_propose_hotspot_set,
    )
)

_register(
    ToolSpec(
        id="request_residue_selection",
        description=(
            "Ask the person to choose between residue sets on the structure. "
            "Offer two to six, each with the residues it contains and why. Use "
            "this when the choice is a matter of value rather than of method - "
            "which face to design against is not a question the record answers."
        ),
        parameters={
            "type": "object",
            "properties": {
                "question": {"type": "string", "minLength": 1, "maxLength": 2000},
                "candidate_sets": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 6,
                    "items": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "maxLength": 80},
                            "label": {"type": "string", "maxLength": 200},
                            "residues": {"type": "array", "items": _RESIDUE_SCHEMA, "maxItems": 40},
                            "rationale": {"type": "string", "maxLength": 2000},
                            "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                        },
                        "required": ["label", "residues"],
                        "additionalProperties": False,
                    },
                },
                "recommended": {"type": "string", "maxLength": 80},
            },
            "required": ["question", "candidate_sets"],
            "additionalProperties": False,
        },
        capability="structure-interaction",
        execution_mode="draft",
        requires="session",
        intent="internal",
        needs_operator=True,
        audit=True,
        handler=_request_residue_selection,
    )
)


def _analyse_sequence(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..sequences import service as sequences_service

    def _uuid(field: str) -> uuid.UUID | None:
        raw = _arg_str(args, field)
        return uuid.UUID(raw) if raw else None

    # Ids only. `test_sequences_are_unreachable_through_any_tool` forbids a
    # `sequence` argument on any tool, and the reason is stronger than the
    # parameter list: a tool call's arguments are persisted into the transcript
    # (`copilot_messages.tool_calls`, `copilot_agent_turns`), so accepting
    # residues here would write the second plaintext copy that
    # `wetlab.models.Protein` exists to prevent. The service keeps its
    # `sequence=` path for callers that already hold the text.
    return sequences_service.analyse(
        ctx.session,
        _project_of(ctx),
        candidate_id=_uuid("candidate_id"),
        target_id=_uuid("target_id"),
        protein_id=_uuid("protein_id"),
        window=_arg_int(args, "patch_window", 9),
        threshold=float(args.get("patch_threshold") or 1.5),
    )


_register(
    ToolSpec(
        id="analyse_sequence",
        coerce_numeric_strings=True,
        description=(
            "What a sequence will do before anyone expresses it: glycosylation "
            "sequons, deamidation and isomerisation sites, oxidation-prone "
            "residues, unpaired cysteines, hydrophobic patches, pI, charge at "
            "two pH values, molecular weight and extinction coefficient. Name "
            "exactly one of candidate_id, target_id or protein_id - the "
            "sequence is read from the record, never pasted in. Positions are "
            "1-based. It reports measurements, not a verdict, and it does not "
            "return the sequence: a construct's plaintext stays in the library."
        ),
        parameters={
            "type": "object",
            "properties": {
                "candidate_id": {"type": "string"},
                "target_id": {"type": "string"},
                "protein_id": {"type": "string"},
                "patch_window": {"type": "integer", "minimum": 3, "maximum": 40, "default": 9},
                "patch_threshold": {"type": "number", "minimum": 0, "maximum": 4.5, "default": 1.5},
            },
            "additionalProperties": False,
        },
        capability="sequence-analysis",
        execution_mode="read",
        requires="session",
        handler=_analyse_sequence,
    )
)


def _analyse_conservation(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..sequences import service as sequences_service

    # An artifact id, not an alignment: the argument list is written into the
    # transcript, and an alignment pasted there would carry the query sequence
    # with it - the same rule that keeps `analyse_sequence` to ids.
    return sequences_service.conservation_from_artifact(
        ctx.session,
        _project_of(ctx),
        artifact_id=uuid.UUID(value) if (value := _arg_str(args, "artifact_id")) else None,
        target_id=uuid.UUID(value) if (value := _arg_str(args, "target_id")) else None,
        weighting=_arg_str(args, "weighting") or "henikoff",
        limit=_arg_int(args, "limit", 25),
    )


_register(
    ToolSpec(
        id="analyse_conservation",
        coerce_numeric_strings=True,
        description=(
            "Which positions of a protein its homologues have not changed, read "
            "from an uploaded or collected alignment (FASTA, a3m or "
            "Stockholm; the first sequence is taken as the query). Returns the "
            "most conserved and most variable positions with per-column entropy, "
            "gap fraction and effective depth. Redundancy is corrected with "
            "Henikoff weights by default, because an alignment of near-identical "
            "orthologues otherwise reads as conserved everywhere. Positions are "
            "1-based in the query's numbering. Conservation is evidence about "
            "what relatives tolerate, not a prediction that a substitution fails."
        ),
        parameters={
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "target_id": {"type": "string", "description": "Alternatively resolve a unique collected AF3 unpaired alignment by the target sequence digest."},
                "weighting": {"type": "string", "enum": ["henikoff", "none"], "default": "henikoff"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 25},
            },
            "additionalProperties": False,
        },
        capability="sequence-analysis",
        execution_mode="read",
        requires="session",
        handler=_analyse_conservation,
    )
)


def _triage_candidates(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..candidates.service import triage_candidate
    from ..projects.models import Project
    from .route_catalog import declared_tiers, route_by_id

    route_id = _arg_str(args, "route_id")
    route = route_by_id(route_id)
    if route is None:
        raise ValueError("route_not_found")
    tiers = declared_tiers(route)
    if not tiers:
        # A route that sets no bar cannot be one a design "passes". Saying so
        # is the answer; returning an empty verdict would read as a clean pass.
        raise ValueError(f"route_declares_no_acceptance_tiers:{route_id}")

    raw_ids = args.get("candidate_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise ValueError("candidate_ids_required")
    if len(raw_ids) > 25:
        # A tool result a person has to read; a hundred verdicts is a file, not
        # an answer.
        raise ValueError("too_many_candidates_at_once")

    project = ctx.session.get(Project, _project_of(ctx))
    if project is None:
        raise ValueError("project_not_found")
    verdicts = [
        triage_candidate(ctx.session, project, uuid.UUID(str(identifier)), tiers)
        for identifier in raw_ids
    ]
    return {
        "route_id": route_id,
        "route_label": route.label,
        "tiers": tiers,
        "tier_order": list(tiers),
        "verdicts": verdicts,
        "reading_note": (
            "A criterion is pass, fail or missing. Missing means nothing has "
            "measured it - not that the design failed - so a design with "
            "missing criteria has not been rejected by this route."
        ),
    }


_register(
    ToolSpec(
        id="triage_candidates",
        description=(
            "Judge named candidates against a design route's declared "
            "acceptance tiers and say, per criterion, whether the recorded "
            "metrics pass, fail, or were never measured. The thresholds are "
            "the route's own; this applies them rather than inventing any. "
            "A missing measurement is reported as missing and blocks a tier "
            "without condemning the design. Up to 25 candidates per call."
        ),
        parameters={
            "type": "object",
            "properties": {
                "route_id": {
                    "type": "string",
                    "description": "A route from plan_workflow_route, e.g. de-novo-binder-pooled.",
                },
                "candidate_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 25,
                },
            },
            "required": ["route_id", "candidate_ids"],
            "additionalProperties": False,
        },
        capability="result-interpretation",
        execution_mode="read",
        requires="session",
        handler=_triage_candidates,
    )
)
