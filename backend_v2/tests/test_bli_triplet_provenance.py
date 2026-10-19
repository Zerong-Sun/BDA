"""Synthetic kinetic exports exercise provenance; no research fixtures are required."""
# ruff: noqa: F811

from __future__ import annotations

import csv
import hashlib
import io
import uuid

import numpy as np
import pytest
from backend_v2.app.copilot.instrument_tools import register
from backend_v2.app.copilot.registry import ToolContext, ToolRegistry
from backend_v2.app.core.problem import DomainError
from backend_v2.app.experiments.models import ExperimentResult
from backend_v2.app.identity.models import OrganizationMember
from backend_v2.app.projects.models import Project
from backend_v2.app.wetlab import analysis
from backend_v2.app.wetlab.kernels import bli
from backend_v2.tests.test_wetlab_analysis import _artifact, _project, session, stored  # noqa: F401
from sqlalchemy import select


def triplets() -> bytes:
    concentrations = [100.0, 30.0, 10.0, 0.0]
    labels = ["sensor1", "sensor2", "sensor3", "reference"]
    rows = []
    metadata = {"Conc1": [c*1e-9 for c in concentrations], "Start1": [0.0]*4, "Stop1": [300.0]*4,
                "KObs": [2e-5*c+0.001 if c else float("nan") for c in concentrations],
                "Error KObs": [0.0001]*4, "KOff": [0.001]*4, "Error KOff": [0.00001]*4}
    for key, values in metadata.items():
        rows.append([item for value in values for item in (key, str(value), "")])
    rows.append([label for label in labels for _ in range(3)])
    rows.append([name for i in range(1, 5) for name in (f"Time{i}", f"Data{i}", f"Fit{i}")])
    for t in np.arange(0.0, 301.0, 2.0):
        row = []
        for i, concentration in enumerate(concentrations):
            measured = bli._simulate_1to1(np.asarray([t]), 8e-5, 0.002, 0.7+0.1*i, concentration, 0.0, 100.0)[0]
            measured += 0.003*np.sin(t/13)+0.01
            # Intentionally inconsistent instrument fit: must never become observed data.
            row += [str(t), str(measured), str(42.0 if t < 300 else -99999)]
        rows.append(row)
    output = io.StringIO()
    csv.writer(output).writerows(rows)
    return output.getvalue().encode()


MAPPING = {"sensor1": "sample", "sensor2": "sample", "sensor3": "sample", "reference": "sample"}


def test_parser_distinguishes_data_fit_units_and_acquisition_bounds():
    curves = bli.parse_bli_csv(triplets())
    assert curves[0].conc_nM == pytest.approx(100)
    assert curves[0].response[0] == pytest.approx(0.01)
    assert curves[0].instrument_fit[0] == 42
    assert np.isnan(curves[0].instrument_fit[-1])
    assert curves[0].metadata["Stop1"] == 300
    assert curves[0].sample_id == "sensor1"  # identity needs an explicit mapping
    assert curves[0].source_format == "kinetic_triplets"


def test_malformed_triplet_and_unknown_mapping_fail_closed():
    bad = triplets().replace(b"Data2", b"Fit2", 1)
    with pytest.raises(DomainError, match="triplets"):
        analysis.analyse_bli_bytes(bad)
    with pytest.raises(DomainError):
        analysis.analyse_bli_bytes(triplets(), sample_mapping={"missing_sensor": "sample"})
    with pytest.raises(DomainError):
        analysis.analyse_bli_bytes(triplets(), reference_label="sensor1")


def test_discovery_and_missing_phase_never_guess_sample_or_phase():
    measurement, summary = analysis.analyse_bli_bytes(triplets())
    assert measurement["value"] is None
    assert len(summary["curves"]) == 4
    measurement, summary = analysis.analyse_bli_bytes(triplets(), sample_mapping=MAPPING)
    assert measurement["value"] is None
    assert "phase_boundaries_required" in {check["code"] for check in summary["quality_control"]["checks"]}


def test_measured_fit_ignores_instrument_fit_columns_and_preserves_processing():
    measurement, summary = analysis.analyse_bli_bytes(triplets(), sample_mapping=MAPPING, t_assoc=0, t_dissoc=100,
                                                     reference_label="reference", correction_note="Subtract paired reference")
    assert measurement["value"] == pytest.approx(25.0, rel=0.01)
    assert measurement["results"]["joint"]["kon_M_inv_s"] == pytest.approx(80000, rel=0.01)
    assert summary["evidence_kind"] == "measured_trace_fit"
    assert summary["curves"][0]["points"][0][1] == pytest.approx(0.01)
    assert summary["curves"][0]["processed_points"][0][1] == pytest.approx(0.0)
    assert summary["curves"][0]["instrument_fit_points"][0][1] == 42
    assert summary["curves"][0]["analysis_fit_points"][0][1] != 42
    assert summary["source_checksum_sha256"] == hashlib.sha256(triplets()).hexdigest()
    assert summary["uncertainty"]["confidence_interval_nM"] is None


def test_exact_instrument_regression_does_not_claim_zero_uncertainty():
    measurement, summary = analysis.analyse_bli_bytes(triplets(), sample_mapping=MAPPING, analysis_method="instrument_kobs")
    assert measurement["value"] == pytest.approx(50)
    assert summary["evidence_kind"] == "instrument_reported_kinetics"
    assert summary["instrument_kinetics"]["r2"] == 1.0
    assert summary["instrument_kinetics"]["deterministic_relationship"]
    assert summary["uncertainty"]["kd_standard_error_nM"] is None
    assert "deterministic_kobs_relationship" in {c["code"] for c in summary["quality_control"]["checks"]}


def test_corrected_results_append_snapshots_and_retain_source(session, stored):
    project_id, user_id = _project(session)
    body = triplets()
    artifact = _artifact(session, project_id, user_id, "synthetic.csv", body)
    stored[artifact.object_key] = body
    original, _ = analysis.analyse_bli(session, project_id, user_id, artifact.id,
                                     sample_mapping=MAPPING, analysis_method="instrument_kobs")
    original_metadata = dict(original.result_metadata)
    corrected, summary = analysis.analyse_bli(session, project_id, user_id, artifact.id, sample_mapping=MAPPING,
                                            analysis_method="instrument_kobs", correction_note="Exclude lowest concentration for sensitivity analysis",
                                            excluded_labels=["sensor3"], supersedes_result_id=original.id)
    assert corrected.id != original.id
    assert original.result_metadata == original_metadata
    assert corrected.result_metadata["supersedes_result_id"] == str(original.id)
    assert corrected.result_metadata["summary"] == summary
    assert artifact.checksum_sha256 == hashlib.sha256(body).hexdigest()
    assert stored[artifact.object_key] == body
    with pytest.raises(DomainError):
        analysis.analyse_bli(session, project_id, user_id, artifact.id, supersedes_result_id=uuid.uuid4(), correction_note="Invalid")
    with pytest.raises(DomainError):
        analysis.analyse_bli(session, project_id, user_id, artifact.id, supersedes_result_id=original.id)


def test_bot_preview_is_project_scoped_hash_verified_and_read_only(session, stored):
    project_id, user_id = _project(session)
    session.add(OrganizationMember(organization_id=session.get(Project, project_id).organization_id, user_id=user_id, role="researcher"))
    session.flush()
    body = triplets()
    artifact = _artifact(session, project_id, user_id, "synthetic.csv", body)
    stored[artifact.object_key] = body
    registry = ToolRegistry()
    register(registry)
    context = ToolContext(project_id=project_id, user_id=user_id, session=session)
    arguments = {"artifact_id": str(artifact.id), "sample_mapping": MAPPING, "analysis_method": "instrument_kobs"}
    result = registry.execute("preview_bli_artifact", context, arguments, granted={"wetlab-authoring"})
    assert result["persisted"] is False
    assert result["value"] == pytest.approx(50)
    assert list(session.scalars(select(ExperimentResult))) == []
    with pytest.raises(DomainError):
        registry.execute("preview_bli_artifact", context, arguments, granted={"project-read"})
    stored[artifact.object_key] = b"altered"
    with pytest.raises(DomainError) as error:
        registry.execute("preview_bli_artifact", context, arguments, granted={"wetlab-authoring"})
    assert error.value.error_code == "instrument_source_integrity"
