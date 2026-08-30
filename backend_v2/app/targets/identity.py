"""What it means for a target to be identified, and what it still needs to be usable.

Asked separately for each kind of target, because the honest answer differs. A protein is
identified by an accession or a sequence and needs coordinates before anything can be
designed against it. A small molecule is identified by a chemical identifier, and its
coordinates are generated from that identifier by the model's component library when the
job runs - Boltz resolves `ligand_ccd: TCI` against its own CCD, and no file is uploaded or
consulted. Demanding a structure artifact for a ligand asks for something that does not
exist and would never be read.
"""

from __future__ import annotations

from typing import Any

PROTEIN = "protein"
SMALL_MOLECULE = "small_molecule"

# Any one of these resolves a molecule to a definite chemical entity.
CHEMICAL_IDENTIFIERS = ("ccd", "inchikey", "smiles")


def is_identified(target: Any) -> bool:
    """Whether the target names a definite thing, by the standard for its kind."""
    if getattr(target, "target_kind", PROTEIN) == SMALL_MOLECULE:
        identity = getattr(target, "chemical_identity", None) or {}
        return any(str(identity.get(key) or "").strip() for key in CHEMICAL_IDENTIFIERS)
    return bool(getattr(target, "uniprot_accession", None) or getattr(target, "sequence", None))


def requires_structure_artifact(target: Any) -> bool:
    """Whether a usable target must also carry uploaded coordinates.

    Only a protein does. This is the distinction that lets a ligand-target project reach
    the workflow at all.
    """
    return getattr(target, "target_kind", PROTEIN) != SMALL_MOLECULE


def readiness_blockers(target: Any) -> list[str]:
    """Everything standing between this target and a runnable workflow."""
    blockers: list[str] = []
    if getattr(target, "identity_status", None) != "confirmed":
        blockers.append("target_identity_unconfirmed")
    if requires_structure_artifact(target):
        status = getattr(target, "structure_status", None)
        if status not in {"available", "approved"} or not getattr(target, "structure_artifact_id", None):
            blockers.append("target_structure_unavailable")
    return blockers
