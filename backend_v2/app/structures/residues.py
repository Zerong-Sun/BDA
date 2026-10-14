"""Residue inventory and charge conventions, linked to measured contacts.

These are descriptions of residues actually present in the first model. A
charge convention is not a protonation calculation, and geometric contact is
not evidence of an experimentally validated energetic hotspot.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from . import kernels

MAX_RESIDUES = 200
PROPERTIES = ("all", "positive", "negative", "titratable", "interface")
_POSITIVE = frozenset({"LYS", "ARG"})
_NEGATIVE = frozenset({"ASP", "GLU"})
_TITRATABLE = _POSITIVE | _NEGATIVE | {"HIS", "CYS", "TYR"}


def _charge(name: str) -> str:
    if name in _POSITIVE:
        return "typically_positive"
    if name in _NEGATIVE:
        return "typically_negative"
    if name == "HIS":
        return "histidine_protonation_dependent"
    if name in {"CYS", "TYR"}:
        return "typically_neutral_titratable"
    return "typically_neutral"


def inventory(
    text: str,
    *,
    chain: str | None = None,
    residue_property: str = "all",
    partner_chain: str | None = None,
    interface_only: bool = False,
    cutoff_angstrom: float = 4.5,
    limit: int = MAX_RESIDUES,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if residue_property not in PROPERTIES:
        raise kernels.StructureFormatError(f"residue_property must be one of {PROPERTIES}.")
    if not 1 <= limit <= MAX_RESIDUES:
        raise kernels.StructureFormatError(f"limit must be between 1 and {MAX_RESIDUES}.")
    if not 0 < cutoff_angstrom <= kernels.MAX_CUTOFF_ANGSTROM:
        raise kernels.StructureFormatError(f"cutoff_angstrom must be greater than 0 and at most {kernels.MAX_CUTOFF_ANGSTROM}.")
    interface_only = interface_only or residue_property == "interface"
    if (partner_chain is not None or interface_only) and chain is None:
        raise kernels.StructureFormatError("Name chain and partner_chain for interface observations.")
    if interface_only and partner_chain is None:
        raise kernels.StructureFormatError("interface_only requires partner_chain.")

    structure, fmt = kernels._parse(text)
    models = list(structure)
    model = models[0]
    selected_chains = [kernels._chain_or_error(model, chain)] if chain is not None else list(model)
    contact_details: dict[tuple[int, str, str], dict[str, Any]] = {}
    if partner_chain is not None:
        measured = kernels.contacts(text, chain_a=str(chain), chain_b=partner_chain, cutoff_angstrom=cutoff_angstrom)
        contact_details = {
            (row["seq"], row["insertion_code"] or "", row["name"]): row
            for row in measured["interface_residue_details_a"]
        }

    rows: list[dict[str, Any]] = []
    charge_counts: Counter[str] = Counter()
    for selected_chain in selected_chains:
        for residue in selected_chain:
            if not kernels._is_amino_acid(residue):
                continue
            label = kernels._residue_label(residue)
            name = label["name"].upper()
            charge = _charge(name)
            charge_counts[charge] += 1
            contact = contact_details.get((label["seq"], label["insertion_code"] or "", label["name"]))
            if residue_property == "positive" and name not in _POSITIVE:
                continue
            if residue_property == "negative" and name not in _NEGATIVE:
                continue
            if residue_property == "titratable" and name not in _TITRATABLE:
                continue
            if interface_only and contact is None:
                continue
            rows.append({
                **label,
                "one_letter": kernels._one_letter(residue),
                "charge_classification": charge,
                "in_geometric_interface": bool(contact) if partner_chain is not None else None,
                "contact_pair_count": contact["contact_pair_count"] if contact else (0 if partner_chain is not None else None),
                "minimum_distance_angstrom": contact["minimum_distance_angstrom"] if contact else None,
            })
    rows.sort(key=lambda row: (row["chain"], row["seq"], row["insertion_code"] or "", row["name"]))
    shown = rows[:limit]
    atoms = [atom for selected_chain in selected_chains for residue in selected_chain for atom in kernels._heavy_atoms(residue)]
    return {
        "format": fmt,
        "analysed_model": model.get_id(),
        "model_count": len(models),
        "residue_numbering": "author chain and residue numbering; insertion_code is part of the identity",
        "chain": chain,
        "partner_chain": partner_chain,
        "residue_property": residue_property,
        "interface_only": interface_only,
        "cutoff_angstrom": cutoff_angstrom if partner_chain is not None else None,
        "selected_chain_residue_count": sum(charge_counts.values()),
        "selected_chain_charge_counts": dict(sorted(charge_counts.items())),
        "matched_residue_count": len(rows),
        "returned_residue_count": len(shown),
        "truncated": len(rows) > limit,
        "residues": shown,
        "confidence": kernels._confidence(
            atoms, has_resolution=kernels._resolution(text, fmt) is not None, text=text, provenance=provenance or {},
        ),
        "evidence_type": "residue_identity_and_geometric_contact",
        "hotspot_status": "not_assessed_requires_independent_experimental_evidence",
        "charge_definition": (
            "Conventional side-chain classification near neutral pH: LYS/ARG typically positive; ASP/GLU typically negative. "
            "HIS can be neutral or positive depending on protonation, pH and local environment and is excluded from the positive filter. "
            "CYS/TYR are typically neutral but titratable. Actual protonation states, termini and net protein charge are not calculated."
        ),
        "interface_definition": (
            "At least one non-hydrogen atom within cutoff_angstrom of a non-solvent residue in the explicitly selected partner chain. "
            "Contact counts and distances measure geometry, not energetic importance, affinity or experimentally validated hotspots."
        ),
        "limitations": [
            "Only standard amino-acid residues present in the first coordinate model are listed; missing residues are not reconstructed.",
            "Residue numbers refer to the source file, not a canonical sequence or antibody numbering scheme.",
            "Coordinate identity determines the charge convention; no pH, pKa, protonation or electrostatic calculation was performed.",
            *(["The result is truncated; narrow the chain/property selection before treating it as a complete list."] if len(rows) > limit else []),
        ],
    }
