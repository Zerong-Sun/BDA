"""DSSP assignments from coordinates, restricted to the explicitly selected design region."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

from .gate_schemas import StructurePolicy


def count_helices(assignments: Sequence[tuple[str, int | tuple[int, str], str]], policy: StructurePolicy) -> int:
    count = 0
    run = 0
    previous = None
    for chain, residue_id, code in assignments:
        residue, insertion = residue_id if isinstance(residue_id, tuple) else (residue_id, " ")
        inside = (
            chain in policy.chains
            and (policy.start is None or residue >= policy.start)
            and (policy.end is None or residue <= policy.end)
        )
        continuous = (
            previous is not None
            and chain == previous[0]
            and (
                (residue == previous[1] + 1 and insertion == " ")
                or (residue == previous[1] and insertion != " " and insertion > previous[2])
            )
        )
        if not inside or code != "H" or not continuous:
            count += int(run >= policy.min_helix_length)
            run = 0
        if inside and code == "H":
            run += 1
        previous = chain, residue, insertion
    return count + int(run >= policy.min_helix_length)


def structure_metrics(filename: str, data: bytes, policy: StructurePolicy) -> dict:
    from Bio.PDB import MMCIFParser, PDBParser
    from Bio.PDB.DSSP import make_dssp_dict

    with tempfile.TemporaryDirectory(prefix="bda-dssp-") as folder:
        path = Path(folder) / ("structure" + Path(filename).suffix)
        path.write_bytes(data)
        parser = PDBParser(QUIET=True) if path.suffix.lower() == ".pdb" else MMCIFParser(QUIET=True)
        structure = parser.get_structure("gate", str(path))
        if len(structure) != 1:
            raise ValueError("structure_requires_one_model")
        model = structure[0]
        expected: set[tuple[str, tuple[str, int, str]]] = set()
        for chain in policy.chains:
            if chain not in model:
                raise ValueError(f"design_chain_missing:{chain}")
            residues = [
                r
                for r in model[chain]
                if r.id[0] == " "
                and (policy.start is None or r.id[1] >= policy.start)
                and (policy.end is None or r.id[1] <= policy.end)
            ]
            expected.update((chain, r.id) for r in residues)
            if not residues or any(not all(atom in r for atom in ("N", "CA", "C", "O")) for r in residues):
                raise ValueError(f"backbone_atoms_missing:{chain}")
        output = Path(folder) / "assignment.dssp"
        completed = subprocess.run(
            ["mkdssp", "--output-format=dssp", str(path), str(output)], capture_output=True, timeout=120
        )
        if completed.returncode:
            raise RuntimeError("dssp_calculation_failed: " + completed.stderr.decode(errors="replace")[-500:])
        table, keys = make_dssp_dict(str(output))
        assignments = [(chain, (residue[1], residue[2]), table[(chain, residue)][1]) for chain, residue in keys]
        if not expected <= set(keys):
            raise ValueError("dssp_design_residues_unassigned")
        version = subprocess.run(["mkdssp", "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
        selected = [
            (chain, residue, code)
            for chain, residue, code in assignments
            if chain in policy.chains
            and (policy.start is None or residue[0] >= policy.start)
            and (policy.end is None or residue[0] <= policy.end)
        ]
        strand_assignments = [(chain, residue, "H" if code == "E" else "-") for chain, residue, code in selected]
        dictionary_hash = Path("/usr/share/libcifpp/components.cif.source-sha256")
        return {
            "helix_count": count_helices(assignments, policy),
            "strand_count": count_helices(strand_assignments, policy.model_copy(update={"min_helix_length": 2})),
            "structured_residue_count": sum(code in {"H", "G", "I", "E", "B"} for _, _, code in selected),
            "helix_fraction": sum(code == "H" for _, _, code in selected) / len(selected),
            "strand_fraction": sum(code == "E" for _, _, code in selected) / len(selected),
            "method": "DSSP",
            "method_version": version,
            "dictionary_source_sha256": dictionary_hash.read_text().strip() if dictionary_hash.exists() else None,
        }
