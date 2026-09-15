"""Interface metrics on structures small enough to reason about by hand.

`contacts` already said which residues touch. These tests are about the numbers
that say how much that touching is worth, and each one targets a way the
calculation is usually wrong:

* buried area computed against the wrong reference (the complex minus itself,
  or one chain measured while the other still occludes it) - caught by a pair
  that is far apart burying nothing;
* a salt bridge counted between atoms that are merely close, rather than
  between a carboxylate and an ammonium;
* double counting the two sides of one interface.

The fixtures are hand-written PDB text with coordinates chosen so the distances
are exact, because a test whose expected value came from the code it tests
proves only that the code did not change.
"""

from __future__ import annotations

import pytest
from backend_v2.app.structures import kernels


def _atom(serial: int, name: str, resname: str, chain: str, resseq: int, x: float, y: float, z: float) -> str:
    element = name[0]
    return (
        f"ATOM  {serial:>5} {name:<4}{resname:>4} {chain}{resseq:>4}    "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}  1.00 20.00          {element:>2}"
    )


def _pair_structure(separation: float) -> str:
    """Chain A aspartate facing chain B lysine, `separation` angstroms apart.

    Each residue carries a backbone plus the side-chain atom that matters, so
    SASA has something to measure and the charged pair is unambiguous.
    """
    lines = [
        _atom(1, "N", "ASP", "A", 1, 0.000, 0.000, 0.000),
        _atom(2, "CA", "ASP", "A", 1, 1.458, 0.000, 0.000),
        _atom(3, "C", "ASP", "A", 1, 2.009, 1.420, 0.000),
        _atom(4, "O", "ASP", "A", 1, 1.251, 2.390, 0.000),
        _atom(5, "CB", "ASP", "A", 1, 1.988, -0.773, 1.200),
        _atom(6, "OD1", "ASP", "A", 1, 3.200, -0.500, 1.500),
        _atom(7, "N", "LYS", "B", 1, 3.200 + separation, -0.500, 1.500),
        _atom(8, "CA", "LYS", "B", 1, 4.658 + separation, -0.500, 1.500),
        _atom(9, "C", "LYS", "B", 1, 5.209 + separation, 0.920, 1.500),
        _atom(10, "O", "LYS", "B", 1, 4.451 + separation, 1.890, 1.500),
        _atom(11, "CB", "LYS", "B", 1, 5.188 + separation, -1.273, 2.700),
        _atom(12, "NZ", "LYS", "B", 1, 3.500 + separation, -0.500, 1.500),
    ]
    return "\n".join(lines) + "\nEND\n"


TOUCHING = _pair_structure(3.0)
APART = _pair_structure(25.0)


def test_two_chains_in_contact_bury_surface_on_both_sides() -> None:
    result = kernels.interface(TOUCHING, chain_a="A", chain_b="B")

    assert result["buried_area_a2"]["A"] > 0
    assert result["buried_area_a2"]["B"] > 0
    assert result["interface_residue_count"] == {"A": 1, "B": 1}


def test_the_interface_area_is_half_the_total_buried_and_not_the_sum() -> None:
    """Both sides bury each other; reporting the sum double-counts one interface."""
    result = kernels.interface(TOUCHING, chain_a="A", chain_b="B")

    total = result["buried_area_a2"]["total"]
    assert result["interface_area_a2"] == pytest.approx(total / 2, abs=0.1)
    assert total == pytest.approx(
        result["buried_area_a2"]["A"] + result["buried_area_a2"]["B"], abs=0.1
    )


def test_chains_that_do_not_touch_bury_nothing() -> None:
    """The reference state is each chain alone - so separation must give zero."""
    result = kernels.interface(APART, chain_a="A", chain_b="B")

    assert result["buried_area_a2"]["total"] == 0.0
    assert result["interface_residues"] == []
    assert result["hydrogen_bond_count"] == 0
    assert result["salt_bridge_count"] == 0


def test_a_carboxylate_facing_an_ammonium_is_a_salt_bridge() -> None:
    result = kernels.interface(TOUCHING, chain_a="A", chain_b="B")

    assert result["salt_bridge_count"] >= 1
    bridge = result["salt_bridges"][0]
    assert {bridge["atom_a"], bridge["atom_b"]} == {"OD1", "NZ"}
    assert bridge["distance_angstrom"] <= kernels.SALT_BRIDGE_MAX_ANGSTROM


def test_closeness_alone_is_not_a_salt_bridge() -> None:
    """Backbone carbons sit well within 4 A of each other across this interface."""
    result = kernels.interface(TOUCHING, chain_a="A", chain_b="B")

    for bridge in result["salt_bridges"]:
        assert bridge["atom_a"].startswith(("O", "N"))
        assert bridge["atom_b"].startswith(("O", "N"))


def test_the_hydrogen_bond_count_says_what_it_means_by_one() -> None:
    """A proxy that does not announce itself gets quoted as if it were geometry."""
    result = kernels.interface(TOUCHING, chain_a="A", chain_b="B")

    assert "no angle term" in result["hydrogen_bond_definition"]
    assert str(kernels.HBOND_MAX_ANGSTROM) in result["hydrogen_bond_definition"]


def test_the_probe_radius_travels_with_the_area() -> None:
    """A buried area whose probe is unstated cannot be compared with a published one."""
    result = kernels.interface(TOUCHING, chain_a="A", chain_b="B")

    assert result["probe_radius_angstrom"] == kernels.SASA_PROBE_RADIUS


def test_the_hydrophobic_fraction_describes_the_interface_residues() -> None:
    result = kernels.interface(TOUCHING, chain_a="A", chain_b="B")

    # ASP and LYS are both polar, so this interface is entirely non-hydrophobic.
    assert result["hydrophobic_residue_fraction"] == 0.0


def test_an_interface_with_itself_is_refused() -> None:
    with pytest.raises(kernels.StructureFormatError):
        kernels.interface(TOUCHING, chain_a="A", chain_b="A")


def test_an_absent_chain_is_refused_rather_than_measured_as_empty() -> None:
    with pytest.raises(kernels.StructureFormatError):
        kernels.interface(TOUCHING, chain_a="A", chain_b="Z")


@pytest.mark.parametrize("cutoff", [0, -1, kernels.MAX_CUTOFF_ANGSTROM + 1])
def test_an_unusable_cutoff_is_refused(cutoff: float) -> None:
    with pytest.raises(kernels.StructureFormatError):
        kernels.interface(TOUCHING, chain_a="A", chain_b="B", cutoff_angstrom=cutoff)
