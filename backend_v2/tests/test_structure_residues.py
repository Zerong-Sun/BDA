"""Residue evidence must survive charge filtering, MCP and viewer selection."""

from __future__ import annotations

import io
import uuid

import pytest
from backend_v2.app.copilot import mcp
from backend_v2.app.copilot.registry import REGISTRY
from backend_v2.app.core.problem import DomainError
from backend_v2.app.structures import kernels, molviewspec, residues, service
from backend_v2.app.targets import hotspots
from backend_v2.app.targets.schemas import HotspotSetCreate
from backend_v2.tests.test_copilot_mcp import _grant, _project
from backend_v2.tests.test_structure_interface import _atom
from backend_v2.tests.test_structure_service import _artifact, _stored_structure
from backend_v2.tests.test_structure_service import session as session  # noqa: F401
from backend_v2.tests.test_structure_service import stored as stored  # noqa: F401
from Bio.PDB import MMCIFIO, PDBParser
from pydantic import ValidationError


def _pdb() -> str:
    rows = [
        _atom(1, "NZ", "LYS", "A", 52, 0, 0, 0),
        _atom(2, "NH1", "ARG", "A", 52, 2, 0, 0),
        _atom(3, "ND1", "HIS", "A", 53, 4, 0, 0),
        _atom(4, "OD1", "ASP", "A", 54, 40, 0, 0),
        _atom(5, "OD1", "ASP", "B", 10, 0, 3, 0),
        _atom(6, "OD1", "ASP", "B", 11, 1, 3, 0),
    ]
    rows[1] = rows[1][:26] + "A" + rows[1][27:]
    return "\n".join(rows) + "\nEND\n"


def _cif() -> str:
    parsed = PDBParser(QUIET=True).get_structure("test", io.StringIO(_pdb()))
    writer = MMCIFIO()
    writer.set_structure(parsed)
    stream = io.StringIO()
    writer.save(stream)
    # Author numbering differs from label numbering in this generated mmCIF.
    return stream.getvalue()


@pytest.mark.parametrize("text", [_pdb(), _cif()])
def test_charge_inventory_preserves_author_ids_and_histidine_uncertainty(text):
    result = residues.inventory(text, chain="A", residue_property="positive")
    assert [(r["seq"], r["insertion_code"], r["name"]) for r in result["residues"]] == [(52, None, "LYS"), (52, "A", "ARG")]
    assert result["selected_chain_residue_count"] == 4
    assert result["selected_chain_charge_counts"]["histidine_protonation_dependent"] == 1
    assert "HIS can be neutral or positive" in result["charge_definition"]
    assert result["confidence"]["metric"] == "unknown"
    assert result["hotspot_status"] == "not_assessed_requires_independent_experimental_evidence"
    titratable = residues.inventory(text, chain="A", residue_property="titratable")
    assert titratable["matched_residue_count"] == 4
    assert titratable["residues"][2]["charge_classification"] == "histidine_protonation_dependent"


def test_contact_residue_summaries_are_complete_even_when_pair_details_are_capped():
    result = kernels.contacts(_pdb(), chain_a="A", chain_b="B", max_pairs=1)
    assert result["truncated"] is True
    assert len(result["interface_residue_details_a"]) == 3
    assert result["interface_residue_details_a"][0]["contact_pair_count"] == 2
    assert len(molviewspec.residues_from_contacts(result, chain="A")) == 3
    positive = residues.inventory(_pdb(), chain="A", residue_property="positive", partner_chain="B", interface_only=True)
    assert positive["matched_residue_count"] == 2
    assert positive["residues"][0]["minimum_distance_angstrom"] == 3
    assert all(row["in_geometric_interface"] for row in positive["residues"])
    negative = residues.inventory(_pdb(), chain="A", residue_property="negative", partner_chain="B", interface_only=True)
    assert negative["matched_residue_count"] == 0


def test_full_contact_identity_reaches_molviewspec():
    result = kernels.contacts(_pdb(), chain_a="A", chain_b="B")
    selection = molviewspec.residues_from_contacts(result, chain="A")
    assert [(r["seq"], r["insertion_code"]) for r in selection] == [(52, None), (52, "A"), (53, None)]
    assert molviewspec._residue_selector(selection[1])["pdbx_PDB_ins_code"] == "A"
    assert molviewspec._residue_selector(selection[0])["pdbx_PDB_ins_code"] == ""
    with pytest.raises(molviewspec.SceneError):
        molviewspec.residues_from_contacts(result, chain="C")


def test_site_refuses_ambiguous_number_and_resolves_explicit_insertion():
    with pytest.raises(kernels.StructureFormatError, match="ambiguous"):
        kernels.site(_pdb(), chain="A", residue_seq=52)
    assert kernels.site(_pdb(), chain="A", residue_seq=52, insertion_code="A")["centre"]["name"] == "ARG"
    assert kernels.site(_pdb(), chain="A", residue_seq=52, insertion_code="")["centre"]["name"] == "LYS"


def test_histidine_does_not_establish_a_salt_bridge_without_protonation_evidence():
    text = "\n".join([_atom(1, "ND1", "HIS", "A", 1, 0, 0, 0), _atom(2, "OD1", "ASP", "B", 1, 0, 3, 0)])
    result = kernels.interface(text, chain_a="A", chain_b="B")
    assert result["salt_bridge_count"] == 0
    assert "Histidine is excluded" in result["salt_bridge_definition"]


@pytest.mark.parametrize("kwargs", [
    {"residue_property": "hotspot"}, {"residue_property": "interface"},
    {"chain": "A", "interface_only": True}, {"chain": "A", "partner_chain": "A"},
    {"chain": "Z"}, {"limit": 0}, {"limit": 201}, {"cutoff_angstrom": 0},
])
def test_invalid_or_ambiguous_inventory_questions_fail(kwargs):
    with pytest.raises(kernels.StructureFormatError):
        residues.inventory(_pdb(), **kwargs)


def test_truncation_is_explicit_without_changing_total():
    result = residues.inventory(_pdb(), chain="A", limit=1)
    assert result["truncated"] is True
    assert result["matched_residue_count"] == 4
    assert result["returned_residue_count"] == 1
    assert len(result["limitations"]) == 4


def test_project_scope_and_provenance_reach_report_and_viewer(session, stored):
    project_id, artifact = _stored_structure(session, stored, text=_pdb())
    artifact.lineage = {"synthetic": True, "token": "private"}
    result = service.residues(session, project_id, artifact.id, chain="A", residue_property="positive")
    assert result["checksum_sha256"] == artifact.checksum_sha256
    assert result["provenance"] == {"synthetic": True}
    assert result["confidence"]["provenance_status"] == "synthetic"
    assert result["viewer_selection"] == {
        "artifact_id": str(artifact.id), "truncated": False,
        "residues": [{"chain": "A", "seq": 52, "insertion_code": None, "name": "LYS"},
                     {"chain": "A", "seq": 52, "insertion_code": "A", "name": "ARG"}],
    }
    with pytest.raises(DomainError):
        service.residues(session, uuid.uuid4(), artifact.id)


def test_mcp_grant_exposes_and_executes_same_project_scoped_tool(session, stored):
    project, user = _project(session)
    artifact = _artifact(session, project.id, user.id, "test.pdb", _pdb().encode())
    stored[artifact.object_key] = _pdb().encode()
    grant, _ = _grant(session, project, user, capabilities=["structure-analysis"])
    listing = {row["name"]: row for row in mcp.tool_listing(mcp.available_tools(session, grant))}
    assert listing["list_structure_residues"]["annotations"]["readOnlyHint"] is True
    result = mcp.call_tool(session, grant, "list_structure_residues", {
        "artifact_id": str(artifact.id), "chain": "A", "residue_property": "positive", "limit": "1",
    }).result
    assert result["matched_residue_count"] == 2
    assert result["truncated"] is True
    with pytest.raises(DomainError):
        other, _ = _project(session)
        other_grant, _ = _grant(session, other, user, capabilities=["structure-analysis"])
        mcp.call_tool(session, other_grant, "list_structure_residues", {"artifact_id": str(artifact.id)})
    assert "list_structure_residues" in REGISTRY.get("render_structure_view").defer_with


@pytest.mark.parametrize("key", ["insertion_code", "insertionCode"])
def test_design_hotspots_refuse_unsupported_insertion_instead_of_retargeting(key):
    with pytest.raises(DomainError, match="insertion codes"):
        hotspots.normalise_residues([{"chain": "A", "seq": 52, key: "A"}])
    with pytest.raises(ValidationError, match="insertion codes"):
        HotspotSetCreate.model_validate({"label": "test", "residues": [{"chain": "A", "seq": 52, key: "A"}]})
