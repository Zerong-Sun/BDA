"""Best reviewed KD compares accepted evidence, not the lowest attempted fit."""

from __future__ import annotations

import pytest
from backend_v2.app.delivery.service import _kd_value_in_molar, result_summary
from backend_v2.app.experiments.models import ExperimentResult
from backend_v2.app.experiments.service import review_instrument_result
from backend_v2.app.identity.models import User
from backend_v2.app.projects.models import Project
from backend_v2.tests.test_wetlab_analysis import _artifact, _project
from backend_v2.tests.test_wetlab_analysis import session as session  # noqa: F401


def _result(session, project_id, user_id, value, *, unit="nM", kind="SPR_Kd", status="pass", metadata=None, artifact=None):
    row = ExperimentResult(
        project_id=project_id, created_by=user_id, experiment_type=kind, pass_status=status,
        value=value, unit=unit, result_metadata=metadata or {}, source_artifact_id=artifact.id if artifact else None,
    )
    session.add(row)
    session.flush()
    return row


def test_reviewed_bli_is_included_only_after_acceptance_and_without_claiming_assay_pass(session):
    project_id, user_id = _project(session)
    project, user = session.get(Project, project_id), session.get(User, user_id)
    source = _artifact(session, project_id, user_id, "synthetic.csv", b"synthetic")
    manual = _result(session, project_id, user_id, 0.1, unit="uM")
    bli = _result(session, project_id, user_id, 42, kind="bli_affinity", status="unknown", artifact=source,
                  metadata={"results": {"quality_control": {"version": "instrument-qc-v1"}},
                            "instrument_qc_review": {"status": "pending"},
                            "evidence_kind": "instrument_reported_kinetics",
                            "summary": {"selected_method": "instrument_kobs", "processing": {"reference_label": "reference"}}})
    assert result_summary(session, project).best_result_id == manual.id
    review_instrument_result(session, project, bli, user, expected=bli.version, accept=True,
                             rationale="Accept this instrument-derived sensitivity estimate with its limitations.")
    best = result_summary(session, project)
    assert (best.best_result_id, best.best_result_value, best.best_result_unit) == (bli.id, 42, "nM")
    assert bli.pass_status == "unknown"
    assert best.passed_result_count == 1  # QC acceptance does not change assay counts.
    review_instrument_result(session, project, bli, user, expected=bli.version, accept=False,
                             rationale="Withdraw fit acceptance after reviewing the reference.")
    assert result_summary(session, project).best_result_id == manual.id


@pytest.mark.parametrize(("kind", "status", "metadata"), [
    ("BLI_Kd", "unknown", {}),
    ("BLI_Kd", "fail", {}),
    ("bli_affinity", "pass", {}),
    ("bli_affinity", "pass", {"instrument_qc_review": {"status": "pending"}}),
    ("bli_affinity", "pass", {"instrument_qc_review": {"status": "rejected"}}),
    ("bli_affinity", "fail", {"instrument_qc_review": {"status": "accepted"}}),
    ("BLI_Kd", "pass", {"results": {"quality_control": {"version": "instrument-qc-v1"}}}),
    ("BLI_Kd", "pass", {"evidence_kind": "instrument_reported_kinetics"}),
    ("BLI_Kd", "pass", {"evidence_kind": "measured_trace_fit"}),
    ("SPR_Kd", "pass", {"instrument_qc_review": None}),
])
def test_lower_pending_failed_or_unreviewed_result_cannot_displace_reviewed_kd(session, kind, status, metadata):
    project_id, user_id = _project(session)
    project = session.get(Project, project_id)
    accepted = _result(session, project_id, user_id, 90)
    _result(session, project_id, user_id, 0.01, kind=kind, status=status, metadata=metadata)
    assert result_summary(session, project).best_result_id == accepted.id


def test_reviewed_kd_compares_molar_units_but_returns_original_value_and_scoped_identity(session):
    project_id, user_id = _project(session)
    project = session.get(Project, project_id)
    _result(session, project_id, user_id, 80, unit="nM")
    _result(session, project_id, user_id, 0.07, unit="uM")
    _result(session, project_id, user_id, 0.065, unit="µM")
    _result(session, project_id, user_id, 60000, unit="pM")
    expected = _result(session, project_id, user_id, 0.05, unit="μM")
    _result(session, project_id, user_id, 0.001, unit="s^-1")
    _result(session, project_id, user_id, 0.001, kind="EC50")
    foreign_id, foreign_user = _project(session)
    _result(session, foreign_id, foreign_user, 0.001)
    best = result_summary(session, project)
    assert (best.best_result_id, best.best_result_value, best.best_result_unit) == (expected.id, 0.05, "μM")


@pytest.mark.parametrize("value", [None, 0.0, -1.0, float("nan"), float("inf"), -float("inf")])
def test_invalid_kd_never_becomes_best_reviewed_result(session, value):
    project_id, user_id = _project(session)
    project = session.get(Project, project_id)
    _result(session, project_id, user_id, value)
    # Direct check covers NaN on backends where SQLite stores it as NULL.
    assert _kd_value_in_molar(value, "nM") is None
    best = result_summary(session, project)
    assert (best.best_result_id, best.best_result_value, best.best_result_unit) == (None, None, None)


def test_unreviewed_only_project_has_no_best_kd(session):
    project_id, user_id = _project(session)
    _result(session, project_id, user_id, 1, status="unknown")
    _result(session, project_id, user_id, 0.1, kind="bli_affinity", status="unknown",
            metadata={"instrument_qc_review": {"status": "pending"}})
    assert result_summary(session, session.get(Project, project_id)).best_result_id is None
