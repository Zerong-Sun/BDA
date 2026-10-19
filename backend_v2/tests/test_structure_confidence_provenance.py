"""B-column ranges never establish prediction confidence provenance."""
from __future__ import annotations

from pathlib import Path

import pytest
from backend_v2.app.structures import kernels, service
from backend_v2.tests.test_structure_kernels import CIF_TEXT, PDB_TEXT
from backend_v2.tests.test_structure_service import _stored_structure
from backend_v2.tests.test_structure_service import session as session  # noqa: F401
from backend_v2.tests.test_structure_service import stored as stored  # noqa: F401


@pytest.mark.parametrize("text", [PDB_TEXT, CIF_TEXT])
def test_unattributed_b_column_is_not_plddt_even_inside_its_range(text):
    confidence = kernels.analyse(text)["confidence"]
    assert confidence["looks_like_plddt"] is False
    assert confidence["metric"] == "unknown"
    assert confidence["numeric_range_compatible_with_plddt"] is True
    assert "do not infer" in confidence["interpretation"]


def test_public_synthetic_fragment_has_no_validated_prediction_confidence(session, stored):
    text = (Path(__file__).resolve().parents[2] / "examples/migration-fixtures/pd1/complexes/PD1Binder_a0172_complex.pdb").read_text()
    project_id, artifact = _stored_structure(session, stored, text=text)
    artifact.lineage = {"synthetic": True, "fixture_version": "test-v1", "execution": "no model or cluster execution",
                        "api_key": "must-not-be-returned", "object_key": "must-not-be-returned"}
    result = service.analyse(session, project_id, artifact.id)
    assert result["residue_total"] == 3
    assert result["confidence"]["mean"] == 21.0
    assert result["confidence"]["looks_like_plddt"] is False
    assert "not validated pLDDT" in result["confidence"]["interpretation"]
    assert result["provenance"]["synthetic"] is True
    assert "api_key" not in result["provenance"] and "object_key" not in result["provenance"]
    contacts = service.contacts(session, project_id, artifact.id, chain_a="A", chain_b="B")
    assert contacts["pair_count"] == 1
    assert contacts["provenance"]["synthetic"] is True


def test_alphafold_db_provenance_preserves_declared_plddt(session, stored):
    project_id, artifact = _stored_structure(session, stored)
    artifact.lineage = {"source": "alphafold_db", "predicted": True, "method": "AlphaFold predicted structure"}
    result = service.analyse(session, project_id, artifact.id)
    assert result["confidence"]["looks_like_plddt"] is True
    assert result["confidence"]["metric"] == "plddt"
    assert result["confidence"]["provenance_status"] == "declared"
    assert result["confidence"]["mean"] == 85.0


@pytest.mark.parametrize("container", [None, "metadata", "context"])
def test_synthetic_flag_overrides_prediction_labels(session, stored, container):
    project_id, artifact = _stored_structure(session, stored)
    synthetic = {"synthetic": True}
    artifact.lineage = {"source": "alphafold_db", "predicted": True,
                        **({container: synthetic} if container else synthetic)}
    confidence = service.analyse(session, project_id, artifact.id)["confidence"]
    assert confidence["metric"] == "unknown"
    assert confidence["provenance_status"] == "synthetic"
    assert confidence["looks_like_plddt"] is False


def test_explicit_file_b_factor_metric_declaration_can_identify_plddt():
    text = "REMARK 250 B-FACTORS REPRESENT PLDDT\n" + PDB_TEXT
    confidence = kernels.analyse(text)["confidence"]
    assert confidence["looks_like_plddt"] is True
    assert confidence["metric"] == "plddt"


@pytest.mark.parametrize("header", ["TITLE     PLDDT EXAMPLE", "REMARK 250 B-FACTORS ARE NOT PLDDT"])
def test_mentions_and_negations_are_not_metric_declarations(header):
    confidence = kernels.analyse(header + "\n" + PDB_TEXT)["confidence"]
    assert confidence["looks_like_plddt"] is False
    assert confidence["metric"] == "unknown"


def test_prediction_origin_without_a_known_metric_convention_stays_unknown():
    confidence = kernels.analyse(PDB_TEXT, provenance={"predicted": True, "source": "unknown_predictor"})["confidence"]
    assert confidence["looks_like_plddt"] is False
    assert confidence["metric"] == "unknown"
