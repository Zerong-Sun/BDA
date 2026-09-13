"""Pure functions over PDB and mmCIF text.

No database, no object storage, no network: everything here takes structure
text and returns plain JSON-able data, which is what makes the geometry
testable without a fixture stack.

Two decisions run through the whole module.

**Measurements, not conclusions.** Every function reports what is in the file -
which residues, at which distance, with which confidence - and none of them
name a site, a pocket or an epitope. The naming is a scientific claim and needs
evidence the file does not contain; a function that returned "active site"
would put that claim beyond review.

**Gaps are reported, never closed.** A chain whose numbering jumps from 52 to
61 is missing eight residues, and the sequence this module returns is the
sequence that is *present*. Concatenating across the break would produce a
string that looks continuous and is not, and every downstream residue index
computed from it would be wrong.
"""

from __future__ import annotations

import io
import re
import warnings
from typing import Any

import numpy as np
from Bio.PDB import MMCIFParser, NeighborSearch, PDBParser
from Bio.PDB.Polypeptide import protein_letters_3to1

#: Non-polymer residues that are solvent or cryoprotectant rather than ligand.
#: Listing them keeps `analyse` from reporting three hundred waters as ligands;
#: they are still counted, just not itemised.
SOLVENT_COMPONENTS = frozenset({"HOH", "DOD", "WAT", "SOL"})

#: Distances beyond this are not contacts by any convention in use here, and a
#: larger cutoff turns the pair search into a quadratic scan of the whole
#: structure. Callers asking for more are told no rather than served slowly.
MAX_CUTOFF_ANGSTROM = 12.0

#: An interface list longer than this is not an interface; it is a mis-specified
#: chain pair. Truncating silently would hide that, so the result says it was
#: truncated and how many pairs were found.
MAX_CONTACT_PAIRS = 400

#: S-S distance for a disulfide. Real bonds sit near 2.05 A; 2.5 A is loose
#: enough for a mediocre model and tight enough to exclude two cysteines that
#: merely face each other.
DISULFIDE_MAX_ANGSTROM = 2.5


class StructureFormatError(ValueError):
    """The text is not a structure this module can read."""


_MMCIF_HINT = re.compile(r"^(data_|loop_|_atom_site\.)", re.MULTILINE)
_PDB_HINT = re.compile(r"^(ATOM  |HETATM|HEADER|MODEL |CRYST1|SEQRES)", re.MULTILINE)
_RESOLUTION_PDB = re.compile(r"^REMARK\s+2\s+RESOLUTION\.\s+([0-9.]+)\s+ANGSTROMS", re.MULTILINE)
_RESOLUTION_CIF = re.compile(r"^_refine\.ls_d_res_high\s+([0-9.]+)", re.MULTILINE)


def detect_format(text: str) -> str:
    """"pdb" or "mmcif", decided by markers rather than by file extension.

    The extension travels with the upload and is whatever the person typed; the
    markers are in the bytes we are about to parse.
    """
    if _MMCIF_HINT.search(text):
        return "mmcif"
    if _PDB_HINT.search(text):
        return "pdb"
    raise StructureFormatError(
        "The file does not look like a PDB or mmCIF structure: no ATOM/HETATM "
        "records and no mmCIF data block were found."
    )


def _parse(text: str) -> tuple[Any, str]:
    """First model of the structure, plus the format it was read as.

    Only the first model: an NMR ensemble's twentieth model is a different set
    of coordinates, and silently mixing models would make every distance an
    average of things that never coexisted. `analyse` reports the model count so
    the caller knows the rest exist.
    """
    fmt = detect_format(text)
    handle = io.StringIO(text)
    parser: Any = MMCIFParser(QUIET=True) if fmt == "mmcif" else PDBParser(QUIET=True)
    with warnings.catch_warnings():
        # Discontinuous chains and duplicate atom names are exactly what this
        # module is here to report; a warning stream would say it to nobody.
        warnings.simplefilter("ignore")
        try:
            structure = parser.get_structure("structure", handle)
        except Exception as exc:  # noqa: BLE001 - biopython raises many types
            raise StructureFormatError(f"The structure could not be parsed: {exc}") from exc
    models = list(structure)
    if not models:
        raise StructureFormatError("The structure contains no model.")
    return structure, fmt


def _is_amino_acid(residue: Any) -> bool:
    return residue.get_resname().strip().upper() in protein_letters_3to1


def _one_letter(residue: Any) -> str:
    return protein_letters_3to1.get(residue.get_resname().strip().upper(), "X")


def _residue_label(residue: Any) -> dict[str, Any]:
    """How one residue is named everywhere in this module's output.

    Chain, sequence number, insertion code and component name together, because
    a residue number alone identifies nothing: two chains reuse the numbers, and
    an insertion code is part of the number in antibody numbering schemes.
    """
    _, seq, icode = residue.get_id()
    return {
        "chain": residue.get_parent().get_id(),
        "seq": int(seq),
        "insertion_code": icode.strip() or None,
        "name": residue.get_resname().strip(),
    }


def _heavy_atoms(residue: Any) -> list[Any]:
    return [atom for atom in residue if atom.element != "H"]


def _numbering_gaps(residues: list[Any]) -> list[dict[str, Any]]:
    """Breaks in the author numbering of one chain.

    A break is evidence of unmodelled residues, which is why it is returned
    rather than smoothed: a loop that was too disordered to model is exactly the
    region where a contact computed from neighbouring residues would mislead.
    """
    gaps: list[dict[str, Any]] = []
    for previous, current in zip(residues, residues[1:], strict=False):
        before = int(previous.get_id()[1])
        after = int(current.get_id()[1])
        if after > before + 1:
            gaps.append({"after_seq": before, "before_seq": after, "missing": after - before - 1})
    return gaps


def _confidence(atoms: list[Any], *, has_resolution: bool) -> dict[str, Any]:
    """B-factor statistics, and whether they are plausibly pLDDT.

    AlphaFold and Boltz write per-atom pLDDT into the B-factor column, so the
    same numbers mean opposite things: high is good for pLDDT and bad for a
    crystallographic B-factor. The file does not say which it is, so this
    returns the statistics under a neutral name and a separate, explicitly
    stated test - values inside [0, 100] and no refinement resolution - rather
    than labelling the column and being confidently wrong on one of the two.
    """
    values = np.array([float(atom.get_bfactor()) for atom in atoms], dtype=float)
    if values.size == 0:
        return {"available": False}
    inside_plddt_range = bool(values.min() >= 0.0 and values.max() <= 100.0)
    return {
        "available": True,
        "mean": round(float(values.mean()), 2),
        "min": round(float(values.min()), 2),
        "max": round(float(values.max()), 2),
        "looks_like_plddt": bool(inside_plddt_range and not has_resolution),
        "interpretation": (
            "Values are in [0, 100] and the file declares no refinement "
            "resolution, which is consistent with a predicted model writing "
            "pLDDT into the B-factor column; higher is more confident."
            if inside_plddt_range and not has_resolution
            else "Treated as crystallographic B-factors; higher is less ordered."
        ),
    }


def _resolution(text: str, fmt: str) -> float | None:
    match = (_RESOLUTION_CIF if fmt == "mmcif" else _RESOLUTION_PDB).search(text)
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def analyse(text: str) -> dict[str, Any]:
    """Everything about the file that does not need a question first."""
    structure, fmt = _parse(text)
    models = list(structure)
    model = models[0]
    resolution = _resolution(text, fmt)

    chains: list[dict[str, Any]] = []
    ligands: list[dict[str, Any]] = []
    solvent_count = 0
    all_atoms: list[Any] = []

    for chain in model:
        polymer = [residue for residue in chain if _is_amino_acid(residue)]
        hetero = [residue for residue in chain if not _is_amino_acid(residue)]
        for residue in hetero:
            name = residue.get_resname().strip().upper()
            if name in SOLVENT_COMPONENTS:
                solvent_count += 1
                continue
            ligands.append(
                {**_residue_label(residue), "atom_count": len(_heavy_atoms(residue))}
            )
        all_atoms.extend(atom for residue in chain for atom in residue if atom.element != "H")
        if not polymer:
            continue
        chains.append(
            {
                "chain": chain.get_id(),
                "residue_count": len(polymer),
                "first_seq": int(polymer[0].get_id()[1]),
                "last_seq": int(polymer[-1].get_id()[1]),
                "sequence": "".join(_one_letter(residue) for residue in polymer),
                "numbering_gaps": _numbering_gaps(polymer),
                # Split, because one number covering both is read as ligands and
                # a crystal structure carries hundreds of ordered waters. The
                # sibling fields `ligands` and `solvent_residue_count` already
                # draw this line; this one used to cross it.
                "ligand_count": len([r for r in hetero if r.get_resname().strip().upper() not in SOLVENT_COMPONENTS]),
                "solvent_count": len([r for r in hetero if r.get_resname().strip().upper() in SOLVENT_COMPONENTS]),
            }
        )

    return {
        "format": fmt,
        "model_count": len(models),
        "analysed_model": model.get_id(),
        "resolution_angstrom": resolution,
        "chains": chains,
        "chain_ids": [entry["chain"] for entry in chains],
        "residue_total": sum(entry["residue_count"] for entry in chains),
        "ligands": ligands,
        "solvent_residue_count": solvent_count,
        "disulfides": _disulfides(model),
        "confidence": _confidence(all_atoms, has_resolution=resolution is not None),
        "notes": (
            ["Only the first model was analysed; the file contains more."]
            if len(models) > 1
            else []
        ),
    }


def _disulfides(model: Any) -> list[dict[str, Any]]:
    """Cysteine pairs whose SG atoms are within bonding distance.

    Derived from coordinates rather than read from SSBOND records, because a
    predicted model has no SSBOND records and a deposited one can carry records
    that its coordinates do not support.
    """
    sulfurs = [
        (residue, residue["SG"])
        for chain in model
        for residue in chain
        if residue.get_resname().strip().upper() == "CYS" and "SG" in residue
    ]
    if len(sulfurs) < 2:
        return []
    search = NeighborSearch([atom for _, atom in sulfurs])
    seen: set[tuple[Any, Any]] = set()
    bonds: list[dict[str, Any]] = []
    for left, right in search.search_all(DISULFIDE_MAX_ANGSTROM, level="A"):
        a_res, b_res = left.get_parent(), right.get_parent()
        if a_res is b_res:
            continue
        key = tuple(sorted((a_res.get_full_id(), b_res.get_full_id())))
        if key in seen:
            continue
        seen.add(key)
        bonds.append(
            {
                "a": _residue_label(a_res),
                "b": _residue_label(b_res),
                "distance_angstrom": round(float(left - right), 2),
            }
        )
    return sorted(bonds, key=lambda bond: (bond["a"]["chain"], bond["a"]["seq"]))


def _chain_or_error(model: Any, chain_id: str) -> Any:
    for chain in model:
        if chain.get_id() == chain_id:
            return chain
    available = [chain.get_id() for chain in model]
    raise StructureFormatError(f"No chain {chain_id!r} in this structure; it has {available}.")


def contacts(
    text: str,
    *,
    chain_a: str,
    chain_b: str,
    cutoff_angstrom: float = 4.5,
    max_pairs: int = MAX_CONTACT_PAIRS,
) -> dict[str, Any]:
    """Residue pairs across two chains within a heavy-atom cutoff.

    Heavy atoms only: hydrogens are absent from most deposited structures and
    present in most predicted ones, so including them would make the same
    interface measure differently depending on where the file came from.

    The pair is reported by its *closest* atoms. A residue-centroid distance
    would call a long arginine reaching across a gap non-contacting, which is
    the opposite of what an interface list is for.
    """
    if chain_a == chain_b:
        raise StructureFormatError("Contacts are between two different chains.")
    if not 0 < cutoff_angstrom <= MAX_CUTOFF_ANGSTROM:
        raise StructureFormatError(
            f"cutoff_angstrom must be greater than 0 and at most {MAX_CUTOFF_ANGSTROM}."
        )
    structure, _ = _parse(text)
    model = list(structure)[0]
    left_chain = _chain_or_error(model, chain_a)
    right_chain = _chain_or_error(model, chain_b)

    right_atoms = [
        atom
        for residue in right_chain
        if residue.get_resname().strip().upper() not in SOLVENT_COMPONENTS
        for atom in _heavy_atoms(residue)
    ]
    if not right_atoms:
        return _contact_result(chain_a, chain_b, cutoff_angstrom, [], truncated=False)
    search = NeighborSearch(right_atoms)

    closest: dict[tuple[Any, Any], dict[str, Any]] = {}
    for residue in left_chain:
        if residue.get_resname().strip().upper() in SOLVENT_COMPONENTS:
            continue
        for atom in _heavy_atoms(residue):
            for other in search.search(atom.coord, cutoff_angstrom, level="A"):
                partner = other.get_parent()
                key = (residue.get_full_id(), partner.get_full_id())
                distance = float(atom - other)
                current = closest.get(key)
                if current is None or distance < current["distance_angstrom"]:
                    closest[key] = {
                        "a": _residue_label(residue),
                        "b": _residue_label(partner),
                        "distance_angstrom": round(distance, 2),
                        "a_atom": atom.get_id(),
                        "b_atom": other.get_id(),
                    }

    pairs = sorted(
        closest.values(),
        key=lambda pair: (pair["distance_angstrom"], pair["a"]["seq"], pair["b"]["seq"]),
    )
    truncated = len(pairs) > max_pairs
    return _contact_result(chain_a, chain_b, cutoff_angstrom, pairs, truncated=truncated, cap=max_pairs)


def _contact_result(
    chain_a: str,
    chain_b: str,
    cutoff: float,
    pairs: list[dict[str, Any]],
    *,
    truncated: bool,
    cap: int = MAX_CONTACT_PAIRS,
) -> dict[str, Any]:
    shown = pairs[:cap] if truncated else pairs
    return {
        "chain_a": chain_a,
        "chain_b": chain_b,
        "cutoff_angstrom": cutoff,
        "pair_count": len(pairs),
        "returned_pair_count": len(shown),
        "truncated": truncated,
        "interface_residues_a": sorted(
            {(pair["a"]["seq"], pair["a"]["name"]) for pair in pairs}
        ),
        "interface_residues_b": sorted(
            {(pair["b"]["seq"], pair["b"]["name"]) for pair in pairs}
        ),
        "pairs": shown,
    }


def site(
    text: str,
    *,
    chain: str | None = None,
    residue_seq: int | None = None,
    ligand: str | None = None,
    radius_angstrom: float = 5.0,
) -> dict[str, Any]:
    """Residues within a radius of one residue or one ligand.

    The centre is named by the caller and reported back verbatim, because this
    function will not decide which ligand is "the" ligand. Naming the wrong
    centre is a mistake the caller can see; having one chosen silently is not.
    """
    if not 0 < radius_angstrom <= MAX_CUTOFF_ANGSTROM:
        raise StructureFormatError(
            f"radius_angstrom must be greater than 0 and at most {MAX_CUTOFF_ANGSTROM}."
        )
    if (residue_seq is None) == (ligand is None):
        raise StructureFormatError("Name exactly one centre: either residue_seq or ligand.")
    structure, _ = _parse(text)
    model = list(structure)[0]

    centre = _find_centre(model, chain=chain, residue_seq=residue_seq, ligand=ligand)
    centre_atoms = _heavy_atoms(centre)
    if not centre_atoms:
        raise StructureFormatError("The named centre has no heavy atoms.")

    others = [
        atom
        for other_chain in model
        for residue in other_chain
        if residue is not centre
        and residue.get_resname().strip().upper() not in SOLVENT_COMPONENTS
        for atom in _heavy_atoms(residue)
    ]
    search = NeighborSearch(others) if others else None

    nearest: dict[Any, dict[str, Any]] = {}
    if search is not None:
        for atom in centre_atoms:
            for other in search.search(atom.coord, radius_angstrom, level="A"):
                neighbour = other.get_parent()
                distance = float(atom - other)
                current = nearest.get(neighbour.get_full_id())
                if current is None or distance < current["distance_angstrom"]:
                    nearest[neighbour.get_full_id()] = {
                        **_residue_label(neighbour),
                        "distance_angstrom": round(distance, 2),
                        "centre_atom": atom.get_id(),
                        "neighbour_atom": other.get_id(),
                    }

    residues = sorted(
        nearest.values(), key=lambda entry: (entry["distance_angstrom"], entry["chain"], entry["seq"])
    )
    return {
        "centre": {**_residue_label(centre), "is_polymer": _is_amino_acid(centre)},
        "radius_angstrom": radius_angstrom,
        "residue_count": len(residues),
        "residues": residues,
    }


def _find_centre(model: Any, *, chain: str | None, residue_seq: int | None, ligand: str | None) -> Any:
    if residue_seq is not None:
        if chain is None:
            raise StructureFormatError("A residue centre needs its chain; residue numbers repeat across chains.")
        for residue in _chain_or_error(model, chain):
            if int(residue.get_id()[1]) == residue_seq:
                return residue
        raise StructureFormatError(f"No residue {residue_seq} in chain {chain!r}.")

    wanted = str(ligand).strip().upper()
    matches = [
        residue
        for model_chain in model
        for residue in model_chain
        if residue.get_resname().strip().upper() == wanted
        and (chain is None or model_chain.get_id() == chain)
    ]
    if not matches:
        raise StructureFormatError(f"No residue or ligand with component code {wanted!r} in this structure.")
    if len(matches) > 1:
        where = ", ".join(
            f"{residue.get_parent().get_id()}{int(residue.get_id()[1])}" for residue in matches
        )
        raise StructureFormatError(
            f"Component {wanted!r} occurs {len(matches)} times ({where}); "
            "name the chain and residue number of the one you mean."
        )
    return matches[0]
