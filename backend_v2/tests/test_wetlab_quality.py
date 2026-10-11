"""Pathological synthetic traces and versioned instrument QC acceptance."""

from __future__ import annotations

import hashlib
import json
import uuid
from types import SimpleNamespace

import numpy as np
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.candidates.models import CandidateMetric
from backend_v2.app.experiments.models import ExperimentResult
from backend_v2.app.learning import service as learning
from backend_v2.app.projects.models import Project
from backend_v2.app.wetlab import analysis
from backend_v2.app.wetlab.diagnostics import optimizer_diagnostics
from backend_v2.app.wetlab.kernels import akta, bli, calculators
from backend_v2.tests.test_learning import _observation, _post, _setup
from backend_v2.tests.test_learning import client as client  # noqa: F401
from backend_v2.tests.test_wetlab_analysis import _fortebio_bytes
from sqlalchemy import select


def test_two_points_have_no_variance_estimate_and_repeated_times_are_unfittable():
    fit = calculators.fit_kinetics([0, 60], [0, 1])
    assert fit["slope"] == 1
    assert fit["diagnostics"]["residual_degrees_of_freedom"] == 0
    assert fit["diagnostics"]["slope_interval_95_dOD_min"] is None
    assert calculators.fit_kinetics([0, 0, 0], [1, 2, 3])["slope"] is None


def test_ols_interval_and_residual_statistics_are_conditional_and_finite():
    fit = calculators.fit_kinetics([0, 60, 120, 180, 240], [1, 2.1, 3, 3.9, 5])
    diagnostic = fit["diagnostics"]
    lo, hi = diagnostic["slope_interval_95_dOD_min"]
    assert lo < fit["slope"] < hi
    assert diagnostic["residual_rmse"] > 0
    assert diagnostic["initial_rate_window_verified"] is False
    json.dumps(fit, allow_nan=False)


def test_enzyme_missing_and_constant_signals_are_not_zero_failure_labels(monkeypatch):
    monkeypatch.setattr(
        calculators,
        "parse_tecan_xlsx",
        lambda _: {
            "wells": {
                "A1": {"times": [0, 60, 120], "od": [1, 1, 1]},
                "A2": {"times": [0, 60, 120], "od": [float("nan"), 1, float("inf")]},
            }
        },
    )
    measurement, summary = analysis.analyse_enzyme_bytes(b"synthetic")
    assert summary["fits"]["A2"]["slope"] is None
    codes = {c["code"] for c in summary["quality_control"]["checks"]}
    assert {"constant_response", "missing_points", "well_not_fitted", "background_unavailable"} <= codes
    assert summary["fits"]["A1"]["slope"] == 0
    assert measurement["results"]["quality_control"]["review_required"]
    json.dumps(summary, allow_nan=False)


def test_bli_insufficient_concentrations_and_phase_coverage_are_explicit():
    t = np.arange(100.0)
    curves = [bli.Curve(str(i), "sample", 10, t, np.ones(100)) for i in range(2)]
    fit = bli.fit_kd(curves, t_assoc=0, t_dissoc=20)
    assert "error" in fit and not fit.get("joint")
    assert fit["quality_control"]["checks"][0]["code"] == "insufficient_concentrations"
    curves[1].conc_nM = 20
    fit = bli.fit_kd(curves, t_assoc=0, t_dissoc=98)
    assert any(c["code"] == "insufficient_phase_points" for c in fit["quality_control"]["checks"])


def test_nonfinite_bli_trace_is_excluded_without_json_nan():
    curves = [bli.Curve("bad", "sample", 10, np.arange(10.0), np.full(10, np.nan))]
    fit = bli.fit_kd(curves)
    assert "error" in fit
    assert any(c["code"] == "missing_points" for c in fit["quality_control"]["checks"])
    json.dumps(fit, allow_nan=False)


def test_optimizer_boundary_and_rank_diagnostics_do_not_invent_confidence_intervals():
    fit = SimpleNamespace(
        fun=np.array([0.1, 0.2, -0.1]), jac=np.ones((3, 2)), active_mask=[-1, 0], success=True, status=1
    )
    diagnostic = optimizer_diagnostics(fit, ["kon", "koff"])
    assert diagnostic["active_bounds"] == ["kon"]
    assert diagnostic["identifiability"] == "numerically_rank_deficient"
    assert "No parameter confidence interval" in diagnostic["uncertainty"]


def test_akta_boundary_and_channel_identity_are_reviewable(monkeypatch):
    volumes = np.linspace(0, 5, 501)
    signal = 30 * np.exp(-(((volumes - 3) / 2) ** 2))
    channels = {
        "UV 1_280": akta.Channel("UV 1_280", "UV", "mAU", volumes, signal),
        "Conductivity": akta.Channel("Conductivity", "Other", "mS/cm", volumes, signal),
    }
    monkeypatch.setattr(akta, "parse_akta_zip", lambda _: {"channels": channels, "events": {}})
    measurement, summary = analysis.analyse_akta_bytes(b"synthetic")
    assert measurement["unit"] == "mAU*mL"
    assert any(c["code"] == "boundary_truncated_peak" for c in summary["quality_control"]["checks"])
    other, _ = analysis.analyse_akta_bytes(b"synthetic", channel="Conductivity")
    assert other["value"] is None and other["unit"] is None


def _analyse(client, monkeypatch):
    api, ids, factory = client
    body = _fortebio_bytes()
    with factory() as session:
        artifact = session.get(Artifact, ids["artifact"])
        artifact.size_bytes = len(body)
        artifact.checksum_sha256 = hashlib.sha256(body).hexdigest()
        session.commit()
    monkeypatch.setattr(analysis, "ObjectStorage", lambda: SimpleNamespace(read_bytes=lambda *args, **kwargs: body))
    response = api.post(
        f"/api/v2/projects/{ids['project']}/wetlab/bli-analyses",
        json={
            "artifact_id": str(ids["artifact"]),
            "candidate_id": str(ids["candidates"][0]),
            "t_assoc": 0,
            "t_dissoc": 120,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _review(client, result, accept=True, version=None):
    api, ids, _ = client
    return api.post(
        f"/api/v2/projects/{ids['project']}/wetlab/results/{result['experiment_result_id']}/review",
        json={"accept": accept, "rationale": "Synthetic source and model assumptions reviewed"},
        headers={"If-Match": f'W/"{version or result["version"]}"'},
    )


def test_http_pending_accepted_rejected_projection_and_stale_review(client, monkeypatch):
    result = _analyse(client, monkeypatch)
    assert result["qc_review"]["status"] == "pending"
    with client[2]() as session:
        assert session.scalar(select(CandidateMetric)) is None
    accepted = _review(client, result)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["candidate_metric_recorded"]
    assert _review(client, result, False).status_code == 412
    rejected = _review(client, result, False, version=accepted.json()["version"])
    assert rejected.status_code == 200 and not rejected.json()["candidate_metric_recorded"]
    with client[2]() as session:
        assert session.scalar(select(CandidateMetric)) is None
        row = session.get(ExperimentResult, uuid.UUID(result["experiment_result_id"]))
        assert row.value == result["value"] and row.pass_status == "unknown"
        assert len(row.result_metadata["instrument_qc_history"]) == 2


def test_http_review_requires_version_project_source_and_finite_value(client, monkeypatch):
    result = _analyse(client, monkeypatch)
    api, ids, factory = client
    path = f"/api/v2/projects/{ids['project']}/wetlab/results/{result['experiment_result_id']}/review"
    assert api.post(path, json={"accept": True, "rationale": "Reviewed"}).status_code == 428
    other_path = path.replace(str(ids["project"]), str(ids["other"]))
    assert (
        api.post(other_path, json={"accept": True, "rationale": "Reviewed"}, headers={"If-Match": 'W/"1"'}).status_code
        == 404
    )
    with factory() as session:
        row = session.get(ExperimentResult, uuid.UUID(result["experiment_result_id"]))
        row.value = None
        session.commit()
    assert _review(client, result).status_code == 422


def test_learning_cannot_relabel_pending_fit_and_retains_review_provenance(client, monkeypatch):
    result = _analyse(client, monkeypatch)
    assay, study = _setup(client)
    _post(client, "observations", _observation(client[1], assay), status=422)
    failed = _post(
        client, "observations", _observation(client[1], assay, qc_accepted=False, status="failed", value=None)
    )
    accepted = _review(client, result).json()
    observation = _post(client, "observations", _observation(client[1], assay))
    assert observation["result_metadata"]["instrument_source"]["version"] == accepted["version"]
    other_rows = [_post(client, "observations", _observation(client[1], assay, i)) for i in range(1, 4)]
    train_snapshot = _post(client, "datasets", {"study_id": study["id"], "result_ids": [observation["id"], *[r["id"] for r in other_rows]]})
    model = _post(client, "models", {"dataset_id": train_snapshot["id"]})
    _review(client, result, False, version=accepted["version"])
    _post(client, "decisions", {"study_id": study["id"], "model_id": model["id"],
        "candidates": [{"candidate_id": str(client[1]["candidates"][6]), "cost_cents": 50}]}, status=409)
    frozen = _post(client, "datasets", {"study_id": study["id"], "result_ids": [observation["id"], failed["id"]]})
    assert not frozen["manifest"]["included"]
    assert {r["reason"] for r in frozen["manifest"]["excluded"]} == {
        "instrument_source_review_changed",
        "qc_not_accepted",
    }
    with client[2]() as session:
        row = session.get(ExperimentResult, uuid.UUID(observation["id"]))
        assert not learning._instrument_source_current(session, session.get(Project, client[1]["project"]), row)
