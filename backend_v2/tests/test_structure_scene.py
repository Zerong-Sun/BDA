"""A scene is a value, so these tests read it as one.

The module's whole claim is that a molecular view can be described rather than
performed. What could break that claim quietly:

* residues addressed in the wrong numbering, which moves every highlight in
  files where author and canonical numbering differ;
* a "highlight" so large it colours the molecule and says nothing;
* a scene that renders as a structure with nothing picked out, when the caller
  did pass residues - the failure mode of a picture that looks fine.
"""

from __future__ import annotations

import pytest
from backend_v2.app.structures import molviewspec


def _nodes(node: dict, kind: str) -> list[dict]:
    """Every node of one kind, depth first."""
    found = [node] if node.get("kind") == kind else []
    for child in node.get("children", []):
        found.extend(_nodes(child, kind))
    return found


def test_a_scene_names_its_format_version_so_a_reader_can_refuse_it() -> None:
    built = molviewspec.scene(url="https://example.test/s.pdb", fmt="pdb")

    assert built["metadata"]["version"] == molviewspec.MVS_VERSION
    assert built["root"]["kind"] == "root"


def test_the_structure_is_downloaded_parsed_and_drawn() -> None:
    built = molviewspec.scene(url="https://example.test/s.cif", fmt="mmcif", title="PD-1")

    download = _nodes(built["root"], "download")[0]
    parse = _nodes(built["root"], "parse")[0]
    assert download["params"]["url"] == "https://example.test/s.cif"
    assert parse["params"]["format"] == "mmcif"
    assert built["metadata"]["title"] == "PD-1"
    assert [node["params"]["type"] for node in _nodes(built["root"], "representation")] == ["cartoon"]


def test_highlighted_residues_are_addressed_in_the_numbering_a_person_reads() -> None:
    """Author numbering, because that is what the viewer and the design tools use."""
    built = molviewspec.scene(
        url="https://example.test/s.pdb",
        fmt="pdb",
        highlights=[{"chain": "A", "seq": 164}, {"chain": "A", "seq": 168}],
        label="Hotspots",
    )

    components = _nodes(built["root"], "component")
    picked = [node for node in components if isinstance(node["params"]["selector"], list)]
    assert picked[0]["params"]["selector"] == [
        {"auth_asym_id": "A", "auth_seq_id": 164},
        {"auth_asym_id": "A", "auth_seq_id": 168},
    ]
    assert [node["params"]["type"] for node in _nodes(picked[0], "representation")] == ["ball_and_stick"]
    assert _nodes(picked[0], "label")[0]["params"]["text"] == "Hotspots"
    assert _nodes(picked[0], "focus")


def test_a_scene_with_nothing_identified_is_the_structure_and_not_an_error() -> None:
    built = molviewspec.scene(url="https://example.test/s.pdb", fmt="pdb", highlights=[])

    selectors = [node["params"]["selector"] for node in _nodes(built["root"], "component")]
    assert selectors == ["polymer"]


def test_a_highlight_of_the_whole_molecule_is_refused_rather_than_drawn() -> None:
    too_many = [{"chain": "A", "seq": index} for index in range(molviewspec.MAX_HIGHLIGHTS + 1)]

    with pytest.raises(molviewspec.SceneError):
        molviewspec.scene(url="https://example.test/s.pdb", fmt="pdb", highlights=too_many)


@pytest.mark.parametrize(
    "residue", [{"seq": 164}, {"chain": "A"}, {"chain": "A", "seq": "the loop"}]
)
def test_a_residue_that_cannot_be_addressed_is_refused(residue: dict) -> None:
    with pytest.raises(molviewspec.SceneError):
        molviewspec.scene(url="https://example.test/s.pdb", fmt="pdb", highlights=[residue])


def test_an_unknown_format_is_refused_rather_than_guessed() -> None:
    with pytest.raises(molviewspec.SceneError):
        molviewspec.scene(url="https://example.test/s.xyz", fmt="xyz")


def test_an_interface_becomes_a_scene_from_the_same_measurement_it_was_reported_from() -> None:
    contacts = {
        "chain_a": "A",
        "chain_b": "B",
        "pairs": [
            {"residue_a": {"chain": "A", "seq": 124}, "residue_b": {"chain": "B", "seq": 31}},
            {"residue_a": {"chain": "A", "seq": 124}, "residue_b": {"chain": "B", "seq": 33}},
            {"residue_a": {"chain": "A", "seq": 126}, "residue_b": {"chain": "B", "seq": 33}},
        ],
    }

    residues = molviewspec.residues_from_contacts(contacts, chain="A")

    # De-duplicated: a residue contacting two partners is one residue.
    assert residues == [{"chain": "A", "seq": 124}, {"chain": "A", "seq": 126}]
    assert molviewspec.residues_from_contacts(contacts, chain="B") == [
        {"chain": "B", "seq": 31},
        {"chain": "B", "seq": 33},
    ]
