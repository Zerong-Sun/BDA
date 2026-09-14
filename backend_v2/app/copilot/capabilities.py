"""What the platform can grant, as one row per capability.

A capability is what this repository calls a "skill": it is what grants tools,
and `copilot_configs.enabled_skills` is a set of these ids. Who is accountable
for using one - and what they must refuse - is a level up, in `bots.py`.

Adding a row here means two other edits in the same change: a bot in `bots.py`
must own it (a test fails otherwise, because an unowned capability is one no
charter constrains), and `docs/COPILOT_BOT_ROSTER.md`'s inventory table lists
it with its tools.
"""

from __future__ import annotations

from typing import Any

COPILOT_CAPABILITIES: list[dict[str, Any]] = [
    {
        "id": "project-read",
        "title": "Project data",
        "description": "Read project targets, candidates, workflows, compute state, and experiment results",
        "async_execution": False,
        "execution_mode": "read",
        "chat_tools": [
            "list_project_targets",
            "list_project_candidates",
            "list_experiment_results",
            "get_workflow_status",
            "get_compute_status",
        ],
    },
    {
        "id": "research-read",
        "title": "Research evidence",
        "description": "Read canonical Research entities, datasets, references, and saved paper excerpts",
        "async_execution": False,
        "execution_mode": "read",
        "chat_tools": [
            "research_overview",
            "search_research",
            "get_research_items",
            "get_dataset_slice",
            "get_reference",
            "get_reference_content",
            "list_research_goals",
        ],
    },
    {
        "id": "result-interpretation",
        "title": "Result interpretation",
        "description": "Interpret recorded candidate and experiment results without changing them",
        "async_execution": False,
        "execution_mode": "read",
        "chat_tools": ["list_project_candidates", "list_experiment_results"],
    },
    {
        "id": "structure-analysis",
        "title": "Structure analysis",
        "description": (
            "Read an uploaded structure artifact at residue level: chains, "
            "sequences, numbering gaps, ligands, disulfides, interface contacts "
            "and per-site neighbourhoods. Reports measurements, never function."
        ),
        "async_execution": False,
        "execution_mode": "read",
        "chat_tools": [
            "analyse_structure",
            "list_structure_contacts",
            "describe_structure_site",
        ],
    },
    {
        "id": "structure-interaction",
        "title": "Structure interaction",
        "description": (
            "Show a structure with named residues picked out, propose a hotspot "
            "set for review, and ask a person to choose residues on the model. "
            "Proposing is not choosing: a set an operator wrote stays pending "
            "until a person confirms it."
        ),
        "async_execution": False,
        "execution_mode": "draft",
        "chat_tools": [
            "render_structure_view",
            "propose_hotspot_set",
            "request_residue_selection",
        ],
    },
    {
        "id": "failure-diagnosis",
        "title": "Failure diagnosis",
        "description": (
            "Explain a failed compute job from its recorded evidence: error, "
            "attempt history, events and the runtime spec it declared."
        ),
        "async_execution": False,
        "execution_mode": "read",
        "chat_tools": ["get_compute_status", "diagnose_compute_failure"],
    },
    {
        "id": "knowledge-authoring",
        "title": "Knowledge drafting",
        "description": "Search project knowledge and create pending-review Copilot notes",
        "async_execution": False,
        "execution_mode": "draft",
        "chat_tools": ["search_project_knowledge", "create_knowledge_draft"],
        "requires_explicit_request": True,
    },
    {
        "id": "literature-search",
        "title": "Literature search",
        "description": "Queue an auditable Europe PMC search and save retrievable content",
        "execution_mode": "queue",
        "chat_tools": ["start_literature_search"],
        "requires_explicit_request": True,
    },
    {
        "id": "target-intelligence",
        "title": "Target intelligence",
        "description": "Queue target intelligence for one exact project Target",
        "execution_mode": "queue",
        "chat_tools": ["start_target_intelligence"],
        "requires_explicit_request": True,
    },
    {
        "id": "research-gap-repair",
        "title": "Research gap repair",
        "description": "Queue retrievable reference and predicted-structure repairs for one Research target",
        "execution_mode": "queue",
        "chat_tools": ["resolve_research_gaps"],
        "requires_explicit_request": True,
    },
    {
        "id": "workflow-planning",
        "title": "Workflow planning",
        "description": "Plan routes and inspect workflows; applying a route remains a user-confirmed action",
        "async_execution": False,
        "execution_mode": "draft",
        "chat_tools": ["get_workflow_status", "plan_workflow_route"],
        "requires_confirmation": True,
    },
    {
        "id": "wetlab-read",
        "title": "Wet-lab bench",
        "description": (
            "Read the protein library and run bench calculations. Constructs are "
            "returned by fingerprint; sequences never leave the server."
        ),
        "async_execution": False,
        "execution_mode": "read",
        "chat_tools": ["list_proteins", "compute_concentration", "plan_dilution_series"],
    },
    {
        "id": "wetlab-authoring",
        "title": "Bench authoring",
        "description": (
            "Register a designed candidate as a construct on the bench, and analyse "
            "uploaded instrument files into recorded experiment results"
        ),
        "async_execution": False,
        "execution_mode": "draft",
        "chat_tools": [
            "promote_candidate_to_bench",
            "analyse_bli_run",
            "analyse_akta_run",
            "analyse_enzyme_plate",
        ],
        "requires_explicit_request": True,
    },
    {
        "id": "research-trace-authoring",
        "title": "Research trace",
        "description": "Attach results, candidates and constructs to a research goal",
        "async_execution": False,
        "execution_mode": "draft",
        "chat_tools": ["attach_to_research_goal"],
        "requires_explicit_request": True,
    },
    {
        "id": "agent-orchestration",
        "title": "Agent orchestration",
        "description": (
            "Inside a durable agent run: wait for a compute job to settle, and "
            "delegate part of the goal to a child run. Unavailable in chat, which "
            "has no run to suspend."
        ),
        "async_execution": True,
        "execution_mode": "read",
        "chat_tools": ["await_compute_job", "spawn_subagent"],
    },
    {
        "id": "chain-messaging",
        "title": "Chain handover",
        "description": (
            "Leave a structured handover for the next operator, read the ones "
            "addressed to you, and ask the person to settle a choice you may not "
            "settle yourself. Copilot bookkeeping: it changes no research record, "
            "which is why its write does not need the user to ask for it by name."
        ),
        "async_execution": False,
        "execution_mode": "draft",
        "chat_tools": ["post_handoff", "read_handoffs", "request_decision"],
    },
    {
        "id": "chain-orchestration",
        "title": "Chain orchestration",
        "description": (
            "Read the roster and delegate one part of a goal to a different "
            "operator. Grants no domain tool of its own: the delegated run "
            "resolves the target bot's capabilities against the project, and the "
            "director never executes them."
        ),
        "async_execution": True,
        "execution_mode": "read",
        "chat_tools": ["list_operators", "delegate_to_operator"],
    },
    {
        "id": "review-audit",
        "title": "Operator review",
        "description": (
            "Read what another operator actually called and what came back, and "
            "the charter it was working under. Read-only by construction: a "
            "reviewer that can repair what it found is a second producer."
        ),
        "async_execution": False,
        "execution_mode": "read",
        "chat_tools": [
            "list_operator_charters",
            "read_operator_work",
            "review_compute_declaration",
        ],
    },
    {
        "id": "compute-drafting",
        "title": "Compute drafting",
        "description": "Create a reviewable compute draft without confirming or submitting it",
        "async_execution": False,
        "execution_mode": "draft",
        "chat_tools": ["get_compute_status", "create_compute_draft"],
        "requires_explicit_request": True,
        "requires_confirmation": True,
    },
]


CAPABILITY_ALIASES = {
    "research": {
        "project-read",
        "research-read",
        "result-interpretation",
        "knowledge-authoring",
        "literature-search",
        "target-intelligence",
        "research-gap-repair",
        "workflow-planning",
        "compute-drafting",
        "wetlab-read",
        "wetlab-authoring",
        "research-trace-authoring",
        "agent-orchestration",
        "structure-analysis",
        "failure-diagnosis",
        "chain-messaging",
        "chain-orchestration",
        "review-audit",
    },
    "knowledge": {"project-read", "research-read", "knowledge-authoring"},
    "literature": {"research-read", "literature-search"},
    "intelligence": {
        "project-read",
        "research-read",
        "target-intelligence",
        "research-gap-repair",
    },
    "structure": {"project-read", "structure-analysis"},
    "diagnosis": {"project-read", "failure-diagnosis"},
    "route-planning": {"project-read", "workflow-planning"},
    "orchestration": {
        "project-read",
        "research-read",
        "chain-orchestration",
        "chain-messaging",
    },
    "review": {"project-read", "research-read", "review-audit", "chain-messaging"},
    "interpretation": {"project-read", "result-interpretation"},
}


def normalize_capabilities(enabled: list[str] | None) -> set[str]:
    if enabled is None:
        return set(CAPABILITY_ALIASES["research"])
    known = {item["id"] for item in COPILOT_CAPABILITIES}
    result: set[str] = set()
    for item in enabled:
        if item in known:
            result.add(item)
        result.update(CAPABILITY_ALIASES.get(item, set()))
    return result


def capability_ids() -> set[str]:
    return {str(item["id"]) for item in COPILOT_CAPABILITIES}


def configurable_capability_ids() -> set[str]:
    return capability_ids() | set(CAPABILITY_ALIASES)


def tools_for_capabilities(capabilities: set[str]) -> set[str]:
    return {
        str(tool) for item in COPILOT_CAPABILITIES if item["id"] in capabilities for tool in item.get("chat_tools", [])
    }


def capabilities_for_turn(
    enabled_capabilities: set[str],
    skill_hint: str | None,
) -> set[str]:
    """Narrow a turn without allowing a client hint to grant a capability."""
    if skill_hint is None:
        return set(enabled_capabilities)
    if skill_hint not in enabled_capabilities:
        return set()
    return {skill_hint}


def research_kinds_for_capabilities(
    capabilities: set[str],
) -> set[str] | None:
    if "research-read" in capabilities:
        return None
    if "research-gap-repair" in capabilities:
        return {"research_target"}
    return set()
