"""Independent dimensional examples, numerical boundaries and read-only HTTP policy."""
from __future__ import annotations

import math
import uuid

import pytest
from backend_v2.app import main
from backend_v2.app.core.database import get_session
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.deps import current_user
from backend_v2.app.identity.models import User
from backend_v2.app.wetlab.bench import AVOGADRO, calculate
from backend_v2.app.wetlab.bench_schemas import BenchCalculationInput
from backend_v2.app.wetlab.kernels.calculators import calc_dilution_series
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

INPUT = TypeAdapter(BenchCalculationInput)


def run(kind, **kwargs):
    return calculate(INPUT.validate_python({"kind": kind, **kwargs}))


def values(result):
    return {item.key: item.value for item in result.values}


def test_protein_mass_extinction_and_no_sequence_echo():
    result = run("protein-properties", sequence=" w y c c \n")
    actual = values(result)
    assert actual["epsilon_reduced"] == 6990
    assert actual["epsilon_cystines"] == 7115
    assert values(run("protein-properties", sequence="GG"))["molecular_weight_g_mol"] == pytest.approx(132.1179)
    assert actual["a280_1mg_mL_reduced"] == pytest.approx(6990 / actual["molecular_weight_g_mol"])
    assert "WYCC" not in result.model_dump_json() and '"sequence"' not in result.model_dump_json()
    zero = run("protein-properties", sequence="AGG")
    assert values(zero)["epsilon_reduced"] == 0 and zero.warnings_zh
    assert "unpaired" in " ".join(run("protein-properties", sequence="WYC").warnings)


@pytest.mark.parametrize("sequence", ["", "  ", "ACD*", "XACD", ">protein\nACD", ">first\nACD\n>second\nWYC", "ACD1", "A" * 100001])
def test_protein_rejects_ambiguity_headers_and_unknown_characters(sequence):
    with pytest.raises(ValidationError):
        run("protein-properties", sequence=sequence)


@pytest.mark.parametrize("molecule,sequence,expected", [("DNA", "ACGT", 1253.8027), ("RNA", "ACGU", 1303.7737)])
def test_nucleic_mass_chain_and_topology_semantics(molecule, sequence, expected):
    single = run("nucleic-properties", sequence=sequence, molecule=molecule, strandedness="ss", topology="linear")
    double = run("nucleic-properties", sequence=sequence, molecule=molecule, strandedness="ds", topology="linear")
    circular = run("nucleic-properties", sequence=sequence, molecule=molecule, strandedness="ds", topology="circular")
    assert values(single)["molecular_weight_g_mol"] == pytest.approx(expected)
    assert values(double)["molecular_weight_g_mol"] == pytest.approx(2 * expected)
    assert values(double)["molecular_weight_g_mol"] - values(circular)["molecular_weight_g_mol"] == pytest.approx(36.0306)
    assert values(single)["gc_percent"] == 50
    assert "5′ phosphate" in " ".join(single.assumptions)
    assert "both strands" in " ".join(circular.assumptions)


@pytest.mark.parametrize("molecule,sequence", [("DNA", "ACGU"), ("RNA", "ACGT"), ("DNA", "ACGN"), ("RNA", "")])
def test_nucleic_canonical_alphabet_is_not_silently_repaired(molecule, sequence):
    with pytest.raises(ValidationError):
        run("nucleic-properties", sequence=sequence, molecule=molecule, strandedness="ss", topology="linear")


def test_protein_absorbance_blank_path_and_dilution_are_applied_once():
    result = values(run("protein-a280", sample_absorbance=1.2, blank_absorbance=.2,
        epsilon_M_inv_cm_inv=50000, molecular_weight_g_mol=25000, path_length_cm=.5, dilution_factor=10))
    assert result["concentration_uM"] == pytest.approx(400)
    assert result["concentration_mg_mL"] == pytest.approx(10)
    raw = run("protein-a280", sample_absorbance=.1, epsilon_M_inv_cm_inv=10000,
              molecular_weight_g_mol=12000, path_length_cm=.1)
    normalized = run("protein-a280", sample_absorbance=1, epsilon_M_inv_cm_inv=10000,
                     molecular_weight_g_mol=12000, absorbance_basis="normalized-1cm")
    assert values(raw)["concentration_M"] == values(normalized)["concentration_M"]
    with pytest.raises(ValidationError, match="twice"):
        run("protein-a280", sample_absorbance=1, epsilon_M_inv_cm_inv=10000,
            molecular_weight_g_mol=12000, absorbance_basis="normalized-1cm", path_length_cm=.1)


@pytest.mark.parametrize("material,factor", [("dsDNA", 50), ("ssDNA", 33), ("RNA", 40)])
def test_nucleic_absorbance_uses_declared_approximation(material, factor):
    result = run("nucleic-a260", material=material, sample_absorbance=.8, blank_absorbance=.05,
                 path_length_cm=.5, dilution_factor=4)
    assert values(result)["concentration_ng_uL"] == pytest.approx(6 * factor)
    assert result.warnings and result.assumptions_zh


@pytest.mark.parametrize("source,target,value,mw,expected", [
    ("mg/L", "ng/uL", 5, None, 5), ("mM", "pM", 2, None, 2e9),
    ("M", "mg/mL", 1e-6, 50000, .05), ("mg/L", "nM", 50, 50000, 1000),
    ("ng/uL", "g/L", 3, None, .003), ("ug/mL", "mg/mL", 1, None, .001),
])
def test_concentration_dimensions(source, target, value, mw, expected):
    actual = run("concentration", value=value, from_unit=source, to_unit=target, molecular_weight_g_mol=mw)
    assert values(actual)["converted_value"] == pytest.approx(expected)
    assert actual.values[0].unit == target


def test_concentration_requires_mass_for_cross_conversion_and_preserves_small_values():
    with pytest.raises(DomainError, match="requires"):
        run("concentration", value=1, from_unit="nM", to_unit="mg/mL")
    result = values(run("concentration", value=1e-9, from_unit="pM", to_unit="M"))
    assert 0 < result["converted_value"] == pytest.approx(1e-21, rel=1e-12, abs=0)


def test_solution_and_dilution_conserve_amount_and_volume():
    solution = run("solution", concentration_mM=2, volume_mL=10, molecular_weight_g_mol=500)
    assert values(solution) == {"mass_mg": 10, "amount_umol": 20}
    assert "FINAL" in " ".join(solution.assumptions)
    dilution = values(run("dilution", stock_concentration=100, target_concentration=2,
                           concentration_unit="mM", final_volume_uL=500))
    assert dilution == {"stock_volume_uL": 10, "diluent_volume_uL": 490, "final_volume_uL": 500}
    assert values(run("dilution", stock_concentration=1, target_concentration=0,
        concentration_unit="mg/mL", final_volume_uL=10))["stock_volume_uL"] == 0
    with pytest.raises(ValidationError, match="higher"):
        run("dilution", stock_concentration=1, target_concentration=2, concentration_unit="M", final_volume_uL=10)


def test_dna_insert_ratio_and_copy_number_have_correct_molecular_units():
    insert = run("dna-ratio", vector_mass_ng=50, vector_length_bp=4000, insert_length_bp=1000,
                 insert_to_vector_molar_ratio=3)
    assert values(insert)["insert_mass_ng"] == pytest.approx(37.5)
    explicit = run("copy-number", mass_ng=660, molecular_weight_g_mol=660000)
    estimate = run("copy-number", mass_ng=660, material="dsDNA", length=1000)
    assert values(explicit) == values(estimate)
    assert values(estimate)["copy_number"] == pytest.approx(AVOGADRO * 1e-12)
    assert values(run("copy-number", mass_ng=340, material="RNA", length=1000))["amount_mol"] == pytest.approx(1e-12, rel=1e-12, abs=0)
    assert estimate.warnings and not explicit.warnings
    for kwargs in ({}, {"material": "dsDNA"}, {"length": 10}, {"length": 10, "molecular_weight_g_mol": 100}):
        with pytest.raises(ValidationError):
            run("copy-number", mass_ng=10, **kwargs)


def test_centrifuge_bidirectional_formula():
    assert values(run("centrifuge", radius_cm=10, from_unit="rpm", value=1000))["rcf"] == pytest.approx(111.8)
    assert values(run("centrifuge", radius_cm=10, from_unit="rcf", value=111.8))["rpm"] == pytest.approx(1000)
    assert values(run("centrifuge", radius_cm=10, from_unit="rpm", value=0))["rcf"] == 0


@pytest.mark.parametrize("factor,steps,well,dead", [(1.01, 24, 200, 20), (2, 4, 200, 20), (10, 8, .1, 0), (2, 1, 100, 10)])
def test_serial_dilution_retains_well_and_dead_volume_after_each_transfer(factor, steps, well, dead):
    rows = calc_dilution_series(100, 50, factor, steps, well, dead)
    previous_concentration = 100.0
    for index, row in enumerate(rows):
        next_transfer = rows[index + 1].stock_vol_uL if index < len(rows) - 1 else 0
        assert row.total_vol_uL - next_transfer >= well + dead - 1e-10
        assert row.stock_vol_uL + row.buffer_vol_uL == pytest.approx(row.total_vol_uL)
        assert previous_concentration * row.stock_vol_uL == pytest.approx(row.conc_uM * row.total_vol_uL)
        previous_concentration = row.conc_uM
    tiny = calc_dilution_series(1, 1e-8, 10, 12, 1)
    assert tiny[-1].conc_uM > 0


def test_serial_calculation_exposes_actual_plan_without_rounding_low_concentration():
    result = run("serial-dilution", stock_conc_uM=1, start_conc_uM=1e-8,
                 dilution_factor=2, n_steps=3, vol_per_well_uL=200, extra_dead_vol_uL=20)
    assert len(result.steps) == 3 and result.steps[-1].conc_uM == 2.5e-9
    assert values(result)["initial_stock_uL"] == result.steps[0].stock_vol_uL
    assert values(result)["total_buffer_uL"] == sum(row.buffer_vol_uL for row in result.steps)
    assert len(result.assumptions) == len(result.assumptions_zh) == 2
    assert result.warnings_zh


@pytest.mark.parametrize("field,value", [("extra_dead_vol_uL", -1), ("stock_conc_uM", float("inf")), ("dilution_factor", float("nan")), ("n_steps", 25)])
def test_existing_serial_kernel_rejects_impossible_or_nonfinite_parameters(field, value):
    payload = dict(stock_conc_uM=100, start_conc_uM=50, dilution_factor=2, n_steps=3, vol_per_well_uL=200, extra_dead_vol_uL=0)
    payload[field] = value
    with pytest.raises(ValueError):
        calc_dilution_series(**payload)


@pytest.mark.parametrize("invalid", [None, "", "1", True, -1, float("nan"), float("inf"), 1e16])
def test_numeric_input_is_finite_typed_nonnegative_and_bounded(invalid):
    with pytest.raises(ValidationError):
        run("concentration", value=invalid, from_unit="M", to_unit="nM")


def test_absorbance_negative_correction_zero_epsilon_and_underflow_are_explicit():
    with pytest.raises(ValidationError, match="negative"):
        run("nucleic-a260", material="dsDNA", sample_absorbance=.1, blank_absorbance=.2)
    with pytest.raises(ValidationError):
        run("protein-a280", sample_absorbance=1, epsilon_M_inv_cm_inv=0, molecular_weight_g_mol=1000)
    with pytest.raises(DomainError):
        run("protein-a280", sample_absorbance=1, epsilon_M_inv_cm_inv=1e-300,
            molecular_weight_g_mol=1000, path_length_cm=1e-300)
    with pytest.raises(DomainError):
        run("concentration", value=1e-320, from_unit="pM", to_unit="M")


@pytest.fixture
def api():
    previous = dict(main.app.dependency_overrides)
    main.app.dependency_overrides[current_user] = lambda: User(id=uuid.uuid4(), username="viewer", role="viewer", enabled=True)

    def no_database_needed():
        yield None

    main.app.dependency_overrides[get_session] = no_database_needed
    try:
        yield TestClient(main.app)
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(previous)


def test_calculator_http_allows_viewer_without_project_or_database_write(api, monkeypatch):
    monkeypatch.setattr(main.settings, "writes_enabled", False)
    response = api.post("/api/v2/wetlab/calculations", json={"kind": "protein-properties", "sequence": "WYC"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["calculation_version"] == "bench-v1"
    assert result["assumptions_zh"] and len(result["assumptions_zh"]) == len(result["assumptions"])
    assert all(v["label_zh"] and math.isfinite(v["value"]) for v in result["values"])
    assert len(result["warnings_zh"]) == len(result["warnings"])
    for path in ("/api/v2/projects", "/api/v2/wetlab/calculations/other", "/api/v2/wetlab/calculations/"):
        assert api.post(path, json={}).status_code == 503
    assert api.patch("/api/v2/wetlab/calculations", json={}).status_code == 503
    main.app.dependency_overrides.pop(current_user)
    assert api.post("/api/v2/wetlab/calculations", json={"kind": "protein-properties", "sequence": "ACD"}).status_code == 401


@pytest.mark.parametrize("body", [
    {"kind": "unknown"}, {"kind": "protein-properties", "sequence": "ACD*"},
    {"kind": "centrifuge", "radius_cm": 0, "from_unit": "rpm", "value": 1},
    {"kind": "concentration", "value": 1, "from_unit": "M", "to_unit": "ng/uL"},
    {"kind": "protein-properties", "sequence": "ACD", "project_id": "ignored?"},
])
def test_http_rejects_invalid_or_ambiguous_calculations(api, body):
    response = api.post("/api/v2/wetlab/calculations", json=body)
    assert response.status_code == 422, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
