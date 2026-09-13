"""Geometry, against a structure whose answers are known by construction.

The fixture is built rather than downloaded, which is the point: every distance
below is a number placed on purpose, so a test failing means the kernel moved
and not that a deposited entry was revised. The same structure is emitted as
both PDB and mmCIF so the two readers can be held to the same answer - a format
difference that changed a residue number would otherwise only surface as a
contact list nobody could reconcile.

Layout, all coordinates in angstroms:

    chain A   residues 1 ALA, 2 GLY, 3 CYS, then a gap, 8 LEU, 9 VAL
    chain B   residues 1 CYS, 2 TRP, ligand LIG 101, water HOH 201
    A:CYS3 SG  <-> B:CYS1 SG    2.05 A   (a disulfide)
    A:GLY2 CA  <-> B:TRP2 CA    3.50 A   (a contact, not a bond)
    LIG C1     <-> A:LEU8 N     2.00 A   (a site neighbour)
"""

from __future__ import annotations

import pytest
from backend_v2.app.structures import kernels

# --- Fixture ----------------------------------------------------------------

#: (chain, resseq, resname, [(atom, element, x, y, z)])
_RESIDUES: list[tuple[str, int, str, list[tuple[str, str, float, float, float]]]] = [
    ("A", 1, "ALA", [("N", "N", 0.0, 0.0, 0.0), ("CA", "C", 0.5, 0.0, 0.0), ("C", "C", 1.0, 0.0, 0.0)]),
    ("A", 2, "GLY", [("N", "N", 4.0, 0.0, 0.0), ("CA", "C", 4.5, 0.0, 0.0), ("C", "C", 5.0, 0.0, 0.0)]),
    (
        "A",
        3,
        "CYS",
        [
            ("N", "N", 8.0, 0.0, 0.0),
            ("CA", "C", 8.5, 0.0, 0.0),
            ("C", "C", 9.0, 0.0, 0.0),
            ("SG", "S", 8.0, 2.0, 0.0),
        ],
    ),
    ("A", 8, "LEU", [("N", "N", 12.0, 0.0, 0.0), ("CA", "C", 12.5, 0.0, 0.0), ("C", "C", 13.0, 0.0, 0.0)]),
    ("A", 9, "VAL", [("N", "N", 16.0, 0.0, 0.0), ("CA", "C", 16.5, 0.0, 0.0), ("C", "C", 17.0, 0.0, 0.0)]),
    (
        "B",
        1,
        "CYS",
        [
            ("N", "N", 8.0, 9.0, 0.0),
            ("CA", "C", 8.5, 9.0, 0.0),
            ("SG", "S", 8.0, 4.05, 0.0),
        ],
    ),
    ("B", 2, "TRP", [("N", "N", 4.0, 3.5, 0.0), ("CA", "C", 4.5, 3.5, 0.0)]),
]

_HETERO: list[tuple[str, int, str, list[tuple[str, str, float, float, float]]]] = [
    ("B", 101, "LIG", [("C1", "C", 12.0, 2.0, 0.0), ("O1", "O", 12.0, 3.0, 0.0)]),
    ("B", 201, "HOH", [("O", "O", 50.0, 50.0, 50.0)]),
]

_B_FACTOR = 85.0


def _pdb(*, with_resolution: bool = False) -> str:
    lines: list[str] = ["HEADER    TEST STRUCTURE"]
    if with_resolution:
        lines.append("REMARK   2 RESOLUTION.    1.80 ANGSTROMS.")
    serial = 1
    for record, rows in (("ATOM  ", _RESIDUES), ("HETATM", _HETERO)):
        for chain, seq, resname, atoms in rows:
            for name, element, x, y, z in atoms:
                lines.append(
                    # Columns matter: name 13-16, altLoc 17, resName 18-20,
                    # chain 22, resSeq 23-26, coordinates from 31.
                    f"{record}{serial:>5} {name:<4} {resname:>3} {chain}{seq:>4}    "
                    f"{x:>8.3f}{y:>8.3f}{z:>8.3f}{1.0:>6.2f}{_B_FACTOR:>6.2f}"
                    f"{'':>10}{element:>2}"
                )
                serial += 1
    lines.append("END")
    return "\n".join(lines) + "\n"


def _mmcif() -> str:
    header = [
        "data_TEST",
        "loop_",
        "_atom_site.group_PDB",
        "_atom_site.id",
        "_atom_site.type_symbol",
        "_atom_site.label_atom_id",
        "_atom_site.label_alt_id",
        "_atom_site.label_comp_id",
        "_atom_site.label_asym_id",
        "_atom_site.label_entity_id",
        "_atom_site.label_seq_id",
        "_atom_site.pdbx_PDB_ins_code",
        "_atom_site.Cartn_x",
        "_atom_site.Cartn_y",
        "_atom_site.Cartn_z",
        "_atom_site.occupancy",
        "_atom_site.B_iso_or_equiv",
        "_atom_site.auth_seq_id",
        "_atom_site.auth_comp_id",
        "_atom_site.auth_asym_id",
        "_atom_site.auth_atom_id",
        "_atom_site.pdbx_PDB_model_num",
    ]
    rows: list[str] = []
    serial = 1
    for group, source in (("ATOM", _RESIDUES), ("HETATM", _HETERO)):
        for chain, seq, resname, atoms in source:
            for name, element, x, y, z in atoms:
                rows.append(
                    f"{group} {serial} {element} {name} . {resname} {chain} 1 {seq} ? "
                    f"{x:.3f} {y:.3f} {z:.3f} 1.00 {_B_FACTOR:.2f} {seq} {resname} {chain} {name} 1"
                )
                serial += 1
    return "\n".join(header + rows) + "\n"


PDB_TEXT = _pdb()
CIF_TEXT = _mmcif()


# --- Format detection --------------------------------------------------------


def test_format_is_detected_from_content_not_extension() -> None:
    assert kernels.detect_format(PDB_TEXT) == "pdb"
    assert kernels.detect_format(CIF_TEXT) == "mmcif"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "just some prose about a protein",
        '{"chains": ["A"], "residues": 42}',
        ">sp|P12345|TEST\nMKTAYIAKQRQISFVKSHFSRQ\n",
    ],
)
def test_a_file_that_is_not_a_structure_is_refused(text: str) -> None:
    """A FASTA and a JSON both mention proteins and neither has coordinates.

    Accepting one and returning an empty analysis would read as "this structure
    has no residues", which is a wrong answer rather than a refused question.
    """
    with pytest.raises(kernels.StructureFormatError):
        kernels.analyse(text)


def test_truncated_coordinates_are_refused_rather_than_half_parsed() -> None:
    with pytest.raises(kernels.StructureFormatError):
        kernels.analyse("data_TEST\nloop_\n_atom_site.group_PDB\n_atom_site.id\nATOM\n")


# --- analyse -----------------------------------------------------------------


def test_analyse_reports_chains_sequences_and_counts() -> None:
    result = kernels.analyse(PDB_TEXT)

    chains = {entry["chain"]: entry for entry in result["chains"]}
    assert set(chains) == {"A", "B"}
    assert chains["A"]["sequence"] == "AGCLV"
    assert chains["A"]["residue_count"] == 5
    assert chains["B"]["sequence"] == "CW"
    assert result["residue_total"] == 7


def test_numbering_gaps_are_reported_not_closed() -> None:
    """The sequence is what is present; the gap is stated separately.

    Concatenating across the break would produce "AGCLV" either way, so the only
    thing that distinguishes a continuous chain from this one is the gap record.
    """
    chain_a = next(entry for entry in kernels.analyse(PDB_TEXT)["chains"] if entry["chain"] == "A")

    assert chain_a["numbering_gaps"] == [{"after_seq": 3, "before_seq": 8, "missing": 4}]
    assert chain_a["first_seq"] == 1
    assert chain_a["last_seq"] == 9


def test_pdb_and_mmcif_of_the_same_structure_agree() -> None:
    from_pdb = kernels.analyse(PDB_TEXT)
    from_cif = kernels.analyse(CIF_TEXT)

    for key in ("chain_ids", "residue_total"):
        assert from_pdb[key] == from_cif[key]
    assert [(c["chain"], c["sequence"], c["numbering_gaps"]) for c in from_pdb["chains"]] == [
        (c["chain"], c["sequence"], c["numbering_gaps"]) for c in from_cif["chains"]
    ]
    assert from_pdb["format"] == "pdb"
    assert from_cif["format"] == "mmcif"


def test_water_is_counted_but_not_itemised_as_a_ligand() -> None:
    result = kernels.analyse(PDB_TEXT)

    assert [entry["name"] for entry in result["ligands"]] == ["LIG"]
    assert result["solvent_residue_count"] == 1


def test_disulfides_come_from_coordinates() -> None:
    bonds = kernels.analyse(PDB_TEXT)["disulfides"]

    assert len(bonds) == 1
    assert {bonds[0]["a"]["chain"], bonds[0]["b"]["chain"]} == {"A", "B"}
    assert bonds[0]["distance_angstrom"] == pytest.approx(2.05, abs=0.01)


def test_confidence_is_labelled_plddt_only_when_the_file_supports_it() -> None:
    """The same column means opposite things in the two cases.

    A predicted model writes pLDDT here (high is good); a refined structure
    writes a B-factor (high is bad). Guessing wrong inverts every judgement made
    from it, so the test pins both branches.
    """
    predicted = kernels.analyse(PDB_TEXT)["confidence"]
    refined = kernels.analyse(_pdb(with_resolution=True))["confidence"]

    assert predicted["looks_like_plddt"] is True
    assert predicted["mean"] == pytest.approx(_B_FACTOR)
    assert refined["looks_like_plddt"] is False
    assert "B-factors" in refined["interpretation"]


# --- contacts ----------------------------------------------------------------


def test_contacts_are_symmetric_between_the_two_chains() -> None:
    """(A, B) transposed must equal (B, A).

    An interface that changes when you name the chains the other way round is
    not an interface; it is an artefact of which chain the search tree was built
    from.
    """
    forward = kernels.contacts(PDB_TEXT, chain_a="A", chain_b="B")
    backward = kernels.contacts(PDB_TEXT, chain_a="B", chain_b="A")

    assert forward["pair_count"] == backward["pair_count"]
    assert forward["interface_residues_a"] == backward["interface_residues_b"]
    assert forward["interface_residues_b"] == backward["interface_residues_a"]
    assert sorted(pair["distance_angstrom"] for pair in forward["pairs"]) == sorted(
        pair["distance_angstrom"] for pair in backward["pairs"]
    )


def test_contacts_report_the_closest_atom_pair_not_a_residue_centre() -> None:
    result = kernels.contacts(PDB_TEXT, chain_a="A", chain_b="B", cutoff_angstrom=4.5)

    pair = next(p for p in result["pairs"] if p["a"]["seq"] == 3 and p["b"]["seq"] == 1)
    assert pair["a_atom"] == "SG"
    assert pair["b_atom"] == "SG"
    assert pair["distance_angstrom"] == pytest.approx(2.05, abs=0.01)


def test_a_tighter_cutoff_can_only_remove_pairs() -> None:
    wide = kernels.contacts(PDB_TEXT, chain_a="A", chain_b="B", cutoff_angstrom=6.0)
    tight = kernels.contacts(PDB_TEXT, chain_a="A", chain_b="B", cutoff_angstrom=2.5)

    def keys(result: dict) -> set[tuple[int, int]]:
        return {(pair["a"]["seq"], pair["b"]["seq"]) for pair in result["pairs"]}

    assert keys(tight) <= keys(wide)
    assert (3, 1) in keys(tight)
    assert (2, 2) in keys(wide)


def test_water_does_not_appear_in_an_interface() -> None:
    result = kernels.contacts(PDB_TEXT, chain_a="A", chain_b="B", cutoff_angstrom=12.0)

    assert all(pair["b"]["name"] != "HOH" for pair in result["pairs"])


def test_contacts_refuse_a_chain_against_itself_and_an_absent_chain() -> None:
    with pytest.raises(kernels.StructureFormatError):
        kernels.contacts(PDB_TEXT, chain_a="A", chain_b="A")
    with pytest.raises(kernels.StructureFormatError):
        kernels.contacts(PDB_TEXT, chain_a="A", chain_b="Z")


@pytest.mark.parametrize("cutoff", [0.0, -1.0, 12.1, 1000.0])
def test_contacts_refuse_a_cutoff_outside_the_supported_range(cutoff: float) -> None:
    with pytest.raises(kernels.StructureFormatError):
        kernels.contacts(PDB_TEXT, chain_a="A", chain_b="B", cutoff_angstrom=cutoff)


def test_contacts_agree_between_pdb_and_mmcif() -> None:
    from_pdb = kernels.contacts(PDB_TEXT, chain_a="A", chain_b="B")
    from_cif = kernels.contacts(CIF_TEXT, chain_a="A", chain_b="B")

    assert from_pdb["interface_residues_a"] == from_cif["interface_residues_a"]
    assert from_pdb["pair_count"] == from_cif["pair_count"]


# --- site --------------------------------------------------------------------


def test_site_around_a_ligand_lists_neighbours_with_distances() -> None:
    result = kernels.site(PDB_TEXT, ligand="LIG", radius_angstrom=5.0)

    assert result["centre"]["name"] == "LIG"
    assert result["centre"]["is_polymer"] is False
    neighbours = {(entry["chain"], entry["seq"]): entry for entry in result["residues"]}
    assert ("A", 8) in neighbours
    assert neighbours[("A", 8)]["distance_angstrom"] == pytest.approx(2.0, abs=0.01)


def test_site_around_a_residue_requires_its_chain() -> None:
    """Residue numbers repeat across chains, so a bare number names two residues.

    Picking the first would answer a question the caller did not ask, and the
    answer would look right.
    """
    with pytest.raises(kernels.StructureFormatError):
        kernels.site(PDB_TEXT, residue_seq=1, radius_angstrom=5.0)

    result = kernels.site(PDB_TEXT, chain="A", residue_seq=3, radius_angstrom=5.0)
    assert result["centre"]["chain"] == "A"
    assert result["centre"]["name"] == "CYS"


def test_site_refuses_zero_or_two_centres() -> None:
    with pytest.raises(kernels.StructureFormatError):
        kernels.site(PDB_TEXT, radius_angstrom=5.0)
    with pytest.raises(kernels.StructureFormatError):
        kernels.site(PDB_TEXT, chain="A", residue_seq=3, ligand="LIG")


def test_an_ambiguous_component_code_is_refused_with_its_occurrences() -> None:
    """Two copies of the same ligand is the normal case in a real structure.

    Choosing one silently produces a pocket description for a site the caller
    never named.
    """
    doubled = PDB_TEXT.replace("END\n", "")
    doubled += (
        "HETATM  900  C1  LIG C 101      30.000  30.000  30.000  1.00 85.00           C\n"
        "END\n"
    )

    with pytest.raises(kernels.StructureFormatError) as error:
        kernels.site(doubled, ligand="LIG", radius_angstrom=5.0)

    assert "B101" in str(error.value) and "C101" in str(error.value)


def test_site_excludes_the_centre_itself() -> None:
    result = kernels.site(PDB_TEXT, chain="A", residue_seq=3, radius_angstrom=6.0)

    assert all(
        not (entry["chain"] == "A" and entry["seq"] == 3) for entry in result["residues"]
    )


def test_site_is_monotonic_in_radius() -> None:
    near = kernels.site(PDB_TEXT, ligand="LIG", radius_angstrom=2.5)
    far = kernels.site(PDB_TEXT, ligand="LIG", radius_angstrom=6.0)

    def keys(result: dict) -> set[tuple[str, int]]:
        return {(entry["chain"], entry["seq"]) for entry in result["residues"]}

    assert keys(near) <= keys(far)


def test_an_unknown_residue_or_component_is_refused() -> None:
    with pytest.raises(kernels.StructureFormatError):
        kernels.site(PDB_TEXT, chain="A", residue_seq=999)
    with pytest.raises(kernels.StructureFormatError):
        kernels.site(PDB_TEXT, ligand="ZZZ")


# --- Degenerate inputs -------------------------------------------------------


def test_a_malformed_resolution_is_treated_as_absent_not_as_zero() -> None:
    """And therefore the B-factor column is still read as possible pLDDT.

    A resolution that cannot be parsed is not evidence of a refined structure,
    so inferring one from it would mislabel a predicted model's confidence.
    """
    text = PDB_TEXT.replace(
        "HEADER    TEST STRUCTURE",
        "HEADER    TEST STRUCTURE\nREMARK   2 RESOLUTION.    1.8.0 ANGSTROMS.",
    )

    result = kernels.analyse(text)

    assert result["resolution_angstrom"] is None
    assert result["confidence"]["looks_like_plddt"] is True


def test_a_chain_holding_only_a_ligand_is_not_reported_as_a_polymer_chain() -> None:
    ligand_only = PDB_TEXT.replace("END\n", "") + (
        "HETATM  901  C1  LIG D 101      40.000  40.000  40.000  1.00 85.00           C\n"
        "END\n"
    )

    result = kernels.analyse(ligand_only)

    assert "D" not in result["chain_ids"]
    assert any(entry["chain"] == "D" for entry in result["ligands"])


def test_a_structure_with_one_cysteine_reports_no_disulfide() -> None:
    single = "\n".join(
        line for line in PDB_TEXT.splitlines() if not (line.startswith("ATOM") and " CYS B " in line)
    ) + "\n"

    assert kernels.analyse(single)["disulfides"] == []


def test_an_interface_against_a_chain_of_only_water_is_empty_not_an_error() -> None:
    water_only = "\n".join(
        line
        for line in PDB_TEXT.splitlines()
        if not (line.startswith(("ATOM", "HETATM")) and line[21] == "B")
    )
    water_only = water_only.replace(
        "END", "HETATM  902  O   HOH B 201      50.000  50.000  50.000  1.00 85.00           O\nEND"
    )

    result = kernels.contacts(water_only, chain_a="A", chain_b="B", cutoff_angstrom=4.5)

    assert result["pair_count"] == 0
    assert result["pairs"] == []


@pytest.mark.parametrize("radius", [0.0, -2.0, 20.0])
def test_site_refuses_a_radius_outside_the_supported_range(radius: float) -> None:
    with pytest.raises(kernels.StructureFormatError):
        kernels.site(PDB_TEXT, ligand="LIG", radius_angstrom=radius)


def test_a_centre_with_only_hydrogens_is_refused() -> None:
    """Heavy atoms are what the distances are measured between.

    A centre with none would silently return an empty neighbourhood, which reads
    as "nothing is nearby" rather than "this centre cannot be measured from".
    """
    hydrogen_only = PDB_TEXT.replace("END\n", "") + (
        "HETATM  903  H1  HYD E 301      12.000   2.000   0.000  1.00 85.00           H\n"
        "END\n"
    )

    with pytest.raises(kernels.StructureFormatError, match="no heavy atoms"):
        kernels.site(hydrogen_only, ligand="HYD", radius_angstrom=5.0)


def test_a_truncated_interface_says_so_and_still_reports_the_full_residue_set() -> None:
    """Truncation is about the pair list, never about the answer.

    The residue set is what an interface question is asking for; the pair list is
    detail. Capping the detail silently would make a long interface look short,
    so the count of pairs found is reported next to the count returned, and the
    residues are complete either way.
    """
    full = kernels.contacts(PDB_TEXT, chain_a="A", chain_b="B", cutoff_angstrom=12.0)
    capped = kernels.contacts(PDB_TEXT, chain_a="A", chain_b="B", cutoff_angstrom=12.0, max_pairs=1)

    assert full["truncated"] is False
    assert capped["truncated"] is True
    assert capped["pair_count"] == full["pair_count"]
    assert capped["returned_pair_count"] == 1
    assert capped["interface_residues_a"] == full["interface_residues_a"]
    assert capped["interface_residues_b"] == full["interface_residues_b"]
    # The pair kept is the closest one, not an arbitrary one.
    assert capped["pairs"][0]["distance_angstrom"] == min(
        pair["distance_angstrom"] for pair in full["pairs"]
    )


def test_solvent_is_not_folded_into_a_single_hetero_count() -> None:
    """One number covering both reads as ligands.

    A crystal structure carries hundreds of ordered waters, and a chain
    reporting `hetero_count: 300` beside an empty ligand list is a number that
    will be quoted as a ligand count.
    """
    chain_b = next(entry for entry in kernels.analyse(PDB_TEXT)["chains"] if entry["chain"] == "B")

    assert chain_b["ligand_count"] == 1
    assert chain_b["solvent_count"] == 1
    assert "hetero_count" not in chain_b
