"""Focused residue inventory registration shared by chat and MCP."""

from __future__ import annotations

import uuid
from typing import Any

from .registry import REGISTRY, ToolContext, ToolSpec


def _list_residues(ctx: ToolContext, args: dict[str, Any]) -> Any:
    from ..structures import service

    if ctx.project_id is None:
        raise ValueError("copilot_project_context_required")
    return service.residues(
        ctx.session,
        ctx.project_id,
        uuid.UUID(str(args["artifact_id"])),
        chain=args.get("chain"),
        residue_property=str(args.get("residue_property", "all")),
        partner_chain=args.get("partner_chain"),
        interface_only=bool(args.get("interface_only", False)),
        cutoff_angstrom=float(args.get("cutoff_angstrom", 4.5)),
        limit=int(args.get("limit", 200)),
    )


REGISTRY.register(ToolSpec(
    id="list_structure_residues",
    coerce_numeric_strings=True,
    description=(
        "List actual residues with author chain, residue number and insertion code, side-chain charge conventions, "
        "source provenance and a viewer selection. Use residue_property=positive for LYS/ARG; histidine is protonation-dependent "
        "and only appears under all or titratable. Supply chain and partner_chain to measure contact count and closest distance; "
        "interface_only=true restricts any property to that geometric interface. Interface/important residue claims are "
        "geometry only; experimentally validated hotspots require independent evidence. Start with analyse_structure to identify chains."
    ),
    parameters={
        "type": "object",
        "properties": {
            "artifact_id": {"type": "string"},
            "chain": {"type": "string", "description": "Author chain ID; omit to inventory all chains."},
            "residue_property": {"type": "string", "enum": ["all", "positive", "negative", "titratable", "interface"], "default": "all"},
            "partner_chain": {"type": "string", "description": "Explicit other author chain ID for geometric contacts."},
            "interface_only": {"type": "boolean", "default": False},
            "cutoff_angstrom": {"type": "number", "minimum": 0.5, "maximum": 12, "default": 4.5},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 200},
        },
        "required": ["artifact_id"],
        "additionalProperties": False,
    },
    capability="structure-analysis",
    execution_mode="read",
    requires="session",
    handler=_list_residues,
))
