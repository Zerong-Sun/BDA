"""Instrument tool transport must retain provenance and current write authority."""

from __future__ import annotations

import copy
import uuid
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot import tools  # noqa: F401
from backend_v2.app.copilot.registry import REGISTRY, ToolContext
from backend_v2.app.core.problem import DomainError
from backend_v2.app.experiments.models import ExperimentResult
from backend_v2.app.identity.models import OrganizationMember, User
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.app.wetlab import analysis
from backend_v2.app.wetlab.kernels import bli_kinetic
from backend_v2.app.wetlab.schemas import BliAnalysisRequest
from backend_v2.tests.test_bli_triplet_provenance import MAPPING, triplets
from backend_v2.tests.test_wetlab_analysis import _artifact, _candidate, _project
from backend_v2.tests.test_wetlab_analysis import session as session  # noqa: F401
from backend_v2.tests.test_wetlab_analysis import stored as stored  # noqa: F401
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from sqlalchemy import select


def _context(session):
    project_id, user_id = _project(session)
    user = session.get(User, user_id)
    user.role = "researcher"
    project = session.get(Project, project_id)
    session.add(OrganizationMember(organization_id=project.organization_id, user_id=user_id, role="researcher"))
    session.flush()
    return ToolContext(session=session, project_id=project_id, user_id=user_id,
                       actions=SimpleNamespace(request_allows=lambda _: True)), user


@pytest.mark.parametrize("tool_name", ["analyse_bli_run", "analyse_akta_run", "analyse_enzyme_plate"])
@pytest.mark.parametrize("revocation", ["global_viewer", "project_viewer", "disabled"])
def test_previously_authorized_tool_rechecks_actor_before_any_instrument_write(session, monkeypatch, tool_name, revocation):
    context, user = _context(session)
    if revocation == "global_viewer":
        user.role = "viewer"
    elif revocation == "project_viewer":
        session.add(ProjectMember(project_id=context.project_id, user_id=user.id, role="viewer"))
    else:
        user.enabled = False
    session.flush()
    called = []
    for name in ("analyse_bli", "analyse_akta", "analyse_enzyme"):
        monkeypatch.setattr(analysis, name, lambda *args, **kwargs: called.append(True))
    with pytest.raises(DomainError):
        REGISTRY.execute(tool_name, context, {"artifact_id": str(uuid.uuid4())}, granted={"wetlab-authoring"})
    assert called == []
    assert list(session.scalars(select(ExperimentResult))) == []


def test_bli_tool_forwards_every_declared_processing_option(session, monkeypatch):
    context, _ = _context(session)
    artifact, candidate, prior = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    captured = {}
    def run(session_arg, project_id, user_id, artifact_id, **kwargs):
        captured.update(kwargs)
        assert (session_arg, project_id, user_id, artifact_id) == (session, context.project_id, context.user_id, artifact)
        return SimpleNamespace(id=uuid.uuid4(), version=1, experiment_type="bli_affinity", value=None, unit=None), {"evidence_kind": "measured_trace_fit"}
    monkeypatch.setattr(analysis, "analyse_bli", run)
    REGISTRY.execute("analyse_bli_run", context, {
        "artifact_id": str(artifact), "candidate_id": str(candidate), "sample_id": "sample",
        "t_assoc": 0, "t_dissoc": 100, "sample_mapping": MAPPING,
        "excluded_labels": ["sensor3"], "reference_label": "reference",
        "analysis_method": "measured_global", "baseline_mode": "fitted_offset",
        "correction_note": "Explicit sensitivity check", "supersedes_result_id": str(prior),
    }, granted={"wetlab-authoring"})
    assert captured == {
        "candidate_id": candidate, "sample_id": "sample", "t_assoc": 0, "t_dissoc": 100,
        "sample_mapping": MAPPING, "excluded_labels": ["sensor3"], "reference_label": "reference",
        "analysis_method": "measured_global", "baseline_mode": "fitted_offset",
        "correction_note": "Explicit sensitivity check", "supersedes_result_id": prior,
    }


def test_bli_save_and_preview_declare_the_rest_processing_contract():
    rest_schema = BliAnalysisRequest.model_json_schema()
    saved = REGISTRY.get("analyse_bli_run")
    preview = REGISTRY.get("preview_bli_artifact")
    assert saved is not None and preview is not None
    assert saved.parameters == {**rest_schema, "additionalProperties": False}
    assert preview.parameters["properties"] == {
        key: value for key, value in rest_schema["properties"].items()
        if key not in {"candidate_id", "supersedes_result_id"}
    }
    assert preview.parameters["additionalProperties"] is False


@pytest.mark.parametrize("tool_name", ["analyse_bli_run", "preview_bli_artifact"])
@pytest.mark.parametrize(("field", "maximum", "make_value"), [
    ("correction_note", 2000, lambda length: "x" * length),
    ("reference_label", 200, lambda length: "x" * length),
    ("sample_mapping", 384, lambda length: {f"sensor{i}": "sample" for i in range(length)}),
    ("excluded_labels", 384, lambda length: [f"sensor{i}" for i in range(length)]),
])
def test_bli_tool_enforces_rest_option_limits_before_analysis(session, monkeypatch, tool_name, field, maximum, make_value):
    context, _ = _context(session)
    spec = REGISTRY.get(tool_name)
    assert spec is not None
    args = {"artifact_id": str(uuid.uuid4()), field: make_value(maximum)}
    BliAnalysisRequest.model_validate(args)
    Draft202012Validator(spec.parameters).validate(args)

    def must_not_analyse(*args, **kwargs):
        raise AssertionError("Out-of-contract arguments must be rejected before analysis")
    monkeypatch.setattr(analysis, "analyse_bli", must_not_analyse)
    monkeypatch.setattr(analysis, "analyse_bli_bytes", must_not_analyse)
    args[field] = make_value(maximum + 1)
    with pytest.raises(ValidationError):
        BliAnalysisRequest.model_validate(args)
    with pytest.raises(DomainError) as error:
        REGISTRY.execute(tool_name, context, args, granted={"wetlab-authoring"})
    assert error.value.error_code == "copilot_tool_arguments_invalid"
    assert list(session.scalars(select(ExperimentResult))) == []


def test_tool_saves_new_version_without_rewriting_prior_result_or_source(session, stored):
    context, _ = _context(session)
    body = triplets()
    artifact = _artifact(session, context.project_id, context.user_id, "synthetic.csv", body)
    stored[artifact.object_key] = body
    args = {"artifact_id": str(artifact.id), "sample_mapping": MAPPING, "analysis_method": "instrument_kobs"}
    first = REGISTRY.execute("analyse_bli_run", context, args, granted={"wetlab-authoring"})
    old = session.get(ExperimentResult, uuid.UUID(first["experiment_result_id"]))
    metadata = copy.deepcopy(old.result_metadata)
    second = REGISTRY.execute("analyse_bli_run", context, {
        **args, "excluded_labels": ["sensor3"], "supersedes_result_id": first["experiment_result_id"],
        "correction_note": "Sensitivity check only",
    }, granted={"wetlab-authoring"})
    assert second["experiment_result_id"] != first["experiment_result_id"]
    assert old.result_metadata == metadata
    assert stored[artifact.object_key] == body
    assert second["summary"]["source_checksum_sha256"] == artifact.checksum_sha256
    assert second["summary"]["evidence_kind"] == "instrument_reported_kinetics"
    assert second["summary"]["uncertainty"]["confidence_interval_nM"] is None
    assert all(row.pass_status == "unknown" for row in session.scalars(select(ExperimentResult)))


def test_tool_without_authorized_write_cannot_save_an_analysis(session, stored):
    context, _ = _context(session)
    denied = ToolContext(session=session, project_id=context.project_id, user_id=context.user_id,
                         actions=SimpleNamespace(request_allows=lambda _: False))
    with pytest.raises(DomainError) as error:
        REGISTRY.execute("analyse_bli_run", denied, {"artifact_id": str(uuid.uuid4())}, granted={"wetlab-authoring"})
    assert error.value.error_code == "copilot_action_requires_explicit_user_request"
    assert list(session.scalars(select(ExperimentResult))) == []


def test_instrument_only_kinetics_does_not_run_or_depend_on_a_measured_fit(monkeypatch):
    body = triplets().replace(b",0.01,42.0", b",30.0,42.0")
    def must_not_fit(*args, **kwargs):
        raise AssertionError("The requested instrument-parameter method must not run a measured fit")
    monkeypatch.setattr(bli_kinetic, "fit_measured", must_not_fit)
    measurement, summary = analysis.analyse_bli_bytes(
        body, sample_mapping=MAPPING, analysis_method="instrument_kobs",
        baseline_mode="fitted_offset", t_assoc=0, t_dissoc=100, reference_label="reference",
    )
    assert measurement["value"] == pytest.approx(50)
    assert summary["evidence_kind"] == "instrument_reported_kinetics"
    assert not any(curve["analysis_fit_points"] for curve in summary["curves"])
    assert not any(curve["processed_points"] for curve in summary["curves"])
    assert summary["processing"]["reference_applied"] is False
    assert summary["processing"]["baseline"] == "instrument_parameters_no_trace_preprocessing"


def test_accepted_candidate_projection_preserves_instrument_method_provenance(session, stored):
    from backend_v2.app.experiments.service import review_instrument_result

    context, user = _context(session)
    body = triplets()
    artifact = _artifact(session, context.project_id, user.id, "synthetic.csv", body)
    stored[artifact.object_key] = body
    candidate = _candidate(session, context.project_id)
    row, _ = analysis.analyse_bli(session, context.project_id, user.id, artifact.id,
                                 candidate_id=candidate.id, sample_mapping=MAPPING, analysis_method="instrument_kobs")
    project = session.get(Project, context.project_id)
    review_instrument_result(session, project, row, user, expected=row.version, accept=True,
                             rationale="Accept instrument-derived estimate with its stated limitations.")
    metric = analysis.record_measured_metric(session, row)
    assert metric is not None
    assert metric.source_experiment_result_id == row.id
    assert metric.context["source_evidence_kind"] == "instrument_reported_kinetics"
    assert metric.context["selected_method"] == "instrument_kobs"
    assert metric.context["source_checksum_sha256"] == artifact.checksum_sha256
    assert metric.context["processing"]["sample_mapping"] == MAPPING


@pytest.mark.parametrize("field", ["t_assoc", "t_dissoc"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_phase_is_rejected_before_any_result_is_recorded(session, stored, field, value):
    context, _ = _context(session)
    artifact = _artifact(session, context.project_id, context.user_id, "synthetic.csv", triplets())
    stored[artifact.object_key] = triplets()
    args = {"artifact_id": str(artifact.id), "sample_mapping": MAPPING, field: value}
    with pytest.raises(ValidationError):
        BliAnalysisRequest.model_validate(args)
    with pytest.raises(ValidationError):
        REGISTRY.execute("analyse_bli_run", context, args, granted={"wetlab-authoring"})
    with pytest.raises(DomainError) as error:
        analysis.analyse_bli_bytes(triplets(), sample_mapping=MAPPING, **{field: value})
    assert error.value.error_code == "bli_phase_invalid"
    assert list(session.scalars(select(ExperimentResult))) == []
