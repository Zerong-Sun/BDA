"""Scientific evidence must be scoped, reviewed and rechecked at real execution."""

import copy
import uuid

import pytest
from backend_v2.app.audit.models import AuditLog
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import OrganizationMember, User
from backend_v2.app.literature.models import LiteratureChunk
from backend_v2.app.projects.models import ProjectMember
from backend_v2.app.workflows.gate_runtime import gate_inputs, run_gate
from backend_v2.app.workflows.models import WorkflowRun
from backend_v2.app.workflows.scientific_gates import (
    CANDIDATE,
    REVIEW,
    ScientificEvidenceCreate,
    ScientificEvidenceReview,
    approval_status,
    review_evidence,
    save_evidence,
    search_sources,
)
from backend_v2.tests.scientific_gate_helpers import approve_test_gate, candidate_payload
from backend_v2.tests.test_compute_binding import _node
from backend_v2.tests.test_compute_binding import env as env
from backend_v2.tests.test_workflow_gates import runtime_fixture
from pydantic import ValidationError
from sqlalchemy import select


def draft(env):
    s = env["session"]
    edge = {
        "id": "ab",
        "source": "a",
        "target": "b",
        "source_port": "sequences",
        "target_port": "sequences",
        "gate": {
            "mode": "automatic",
            "configured": True,
            "rules": {"conditions": [{"metric": "score", "op": "gte", "value": 80}]},
        },
    }
    w = WorkflowRun(
        project_id=env["project"].id, name="science", created_by=env["user"].id, graph={"nodes": [], "edges": [edge]}
    )
    s.add(w)
    s.flush()
    s.add_all([_node(w, "a", env["producer"], []), _node(w, "b", env["consumer"], [])])
    s.flush()
    return w, edge


def test_missing_and_forged_graph_approval_fail_closed(env):
    w, edge = draft(env)
    edge["scientific_approval"] = {"accepted": True, "reviewer": "admin"}
    assert not approval_status(env["session"], w, edge)["allowed"]
    payload = candidate_payload(env, w, edge).model_dump(mode="json")
    with pytest.raises(ValidationError):
        ScientificEvidenceCreate.model_validate({**payload, "accepted": True})


def test_candidate_is_not_approval_and_admin_approval_is_bound(env):
    w, edge = draft(env)
    s = env["session"]
    result = save_evidence(w.id, edge["id"], candidate_payload(env, w, edge), s, env["user"])
    assert not approval_status(s, w, edge)["allowed"]
    status = review_evidence(
        w.id,
        edge["id"],
        uuid.UUID(result["id"]),
        ScientificEvidenceReview(
            workflow_version=w.version,
            decision="approve",
            rationale="Checked scientific methods and calibration control outcomes",
        ),
        s,
        env["user"],
    )
    assert status["allowed"] and status["approved_evidence_id"] == result["id"]
    changed = copy.deepcopy(edge)
    changed["gate"]["rules"]["conditions"][0]["value"] = 95
    assert not approval_status(s, w, changed)["allowed"]
    w.version += 1
    assert not approval_status(s, w, edge)["allowed"]


def test_wrong_project_source_and_unanchored_quote_rejected(env):
    w, edge = draft(env)
    payload = candidate_payload(env, w, edge)
    payload.sources[0].quote = "This sentence is absent from the stored source."
    with pytest.raises(DomainError, match="Quote must occur"):
        save_evidence(w.id, edge["id"], payload, env["session"], env["user"])
    payload.sources[0].document_id = uuid.uuid4()
    with pytest.raises(DomainError, match="Evidence must reference"):
        save_evidence(w.id, edge["id"], payload, env["session"], env["user"])


def test_no_calibration_or_cross_method_contract_cannot_be_approved(env):
    w, edge = draft(env)
    payload = candidate_payload(env, w, edge)
    payload.calibration = None
    payload.parameters[0].method_key = "AlphaFold3"
    result = save_evidence(w.id, edge["id"], payload, env["session"], env["user"])
    assert {
        "scientific_calibration_required",
        "scientific_method_scope_mismatch",
        "scientific_source_method_mismatch",
    } <= set(result["issues"])
    with pytest.raises(DomainError) as error:
        review_evidence(
            w.id,
            edge["id"],
            uuid.UUID(result["id"]),
            ScientificEvidenceReview(
                workflow_version=w.version,
                decision="approve",
                rationale="Not acceptable because the scientific contract is incomplete",
            ),
            env["session"],
            env["user"],
        )
    assert error.value.error_code == "scientific_evidence_not_ready"


def test_researcher_can_save_but_cannot_approve(env):
    w, edge = draft(env)
    s = env["session"]
    scientist = User(username="science-writer", display_name="Scientist", role="researcher", enabled=True)
    s.add(scientist)
    s.flush()
    s.add(ProjectMember(project_id=w.project_id, user_id=scientist.id, role="researcher"))
    s.add(OrganizationMember(organization_id=env["project"].organization_id, user_id=scientist.id, role="researcher"))
    s.flush()
    candidate = save_evidence(w.id, edge["id"], candidate_payload(env, w, edge), s, scientist)
    with pytest.raises(DomainError) as error:
        review_evidence(
            w.id,
            edge["id"],
            uuid.UUID(candidate["id"]),
            ScientificEvidenceReview(
                workflow_version=w.version,
                decision="approve",
                rationale="A researcher cannot grant a scientific gate approval",
            ),
            s,
            scientist,
        )
    assert error.value.status_code == 403


def test_changed_source_revokes_approval_and_search_returns_anchor(env):
    w, edge = draft(env)
    approve_test_gate(env, w, edge)
    s = env["session"]
    assert approval_status(s, w, edge)["allowed"]
    sources = search_sources(w.id, edge["id"], "Synthetic", s, env["user"])
    assert len(sources["items"]) == 1 and sources["items"][0]["chunk_sha256"]
    chunk = s.get(LiteratureChunk, uuid.UUID(sources["items"][0]["chunk_id"]))
    chunk.content += " Changed version."
    assert not approval_status(s, w, edge)["allowed"]


def test_real_execution_and_post_release_dispatch_recheck_approval(env):
    s, w, _, source, target, gate, storage = runtime_fixture(env)
    run_gate(s, gate, storage)
    assert gate.status == "released" and gate.snapshot["scientific_approval"]["evidence_id"]
    review = s.scalar(select(AuditLog).where(AuditLog.action == REVIEW, AuditLog.entity_id == w.id))
    review.payload = {**review.payload, "decision": "reject"}
    assert gate_inputs(s, target, {"a"}, {"a": source}) == "waiting"
    assert gate.status == "error" and gate.error_message == "scientific_evidence_approval_required"
    gate.status = "waiting"
    with pytest.raises(ValueError, match="scientific_evidence_approval_required"):
        run_gate(s, gate, storage)


def test_manual_gate_does_not_require_scientific_approval(env):
    s, _, _, _, _, gate, storage = runtime_fixture(env, "review")
    run_gate(s, gate, storage)
    assert gate.status == "awaiting_review"
    assert not list(s.scalars(select(AuditLog).where(AuditLog.action == CANDIDATE)))


def test_submission_preflight_reports_scientific_blocker(env):
    from backend_v2.app.compute.models import Job
    from backend_v2.app.compute.schemas import SubmissionCreate
    from backend_v2.app.compute.service import create_submission
    from backend_v2.app.workflows.preflight import evaluate_preflight

    w, edge = draft(env)
    blockers, _, _ = evaluate_preflight(env["session"], w)
    assert any(b["code"] == "scientific_evidence_approval_required" for b in blockers)
    with pytest.raises(DomainError) as error:
        create_submission(
            env["session"],
            workflow=w,
            project=env["project"],
            payload=SubmissionCreate(compute_backend="demo"),
            idempotency_key="missing-science",
            user=env["user"],
        )
    assert error.value.status_code == 409
    assert not list(env["session"].scalars(select(Job).where(Job.workflow_run_id == w.id)))


def test_calibration_report_cannot_be_its_own_raw_data(env):
    w, edge = draft(env)
    payload = candidate_payload(env, w, edge)
    payload.calibration.raw_data_artifact_ids = [payload.calibration.artifact_id]
    with pytest.raises(DomainError) as error:
        save_evidence(w.id, edge["id"], payload, env["session"], env["user"])
    assert error.value.error_code == "scientific_calibration_raw_required"


def test_cross_project_search_and_replay_are_isolated(env):
    from backend_v2.app.literature.models import LiteratureDocument
    from backend_v2.app.projects.models import Project

    s = env["session"]
    w, edge = draft(env)
    candidate = approve_test_gate(env, w)
    second = Project(
        organization_id=env["project"].organization_id, owner_id=env["user"].id, name="other", project_type="design"
    )
    s.add(second)
    s.flush()
    secret = LiteratureDocument(
        project_id=second.id, title="Other project's private source", source="pubmed", external_id="1234567"
    )
    s.add(secret)
    s.flush()
    s.add(LiteratureChunk(document_id=secret.id, position=0, content="Do not return this cross project source"))
    s.flush()
    assert not search_sources(w.id, edge["id"], "cross project", s, env["user"])["items"]
    foreign = WorkflowRun(project_id=second.id, name="foreign", created_by=env["user"].id, graph=w.graph)
    s.add(foreign)
    s.flush()
    assert not approval_status(s, foreign, edge)["allowed"]
    with pytest.raises(DomainError) as error:
        review_evidence(
            foreign.id,
            edge["id"],
            uuid.UUID(candidate["id"]),
            ScientificEvidenceReview(
                workflow_version=foreign.version,
                decision="approve",
                rationale="An approval cannot cross project or workflow boundaries",
            ),
            s,
            env["user"],
        )
    assert error.value.status_code == 404


def test_api_candidate_review_search_and_forged_payload(env, tmp_path):
    """Use the actual FastAPI routes against a separate file-backed test database."""
    from backend_v2.app.core.database import get_session
    from backend_v2.app.core.models import Base
    from backend_v2.app.core.problem import domain_error_handler
    from backend_v2.app.identity.deps import current_user
    from backend_v2.app.workflows.api import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    w, edge = draft(env)
    payload = candidate_payload(env, w, edge).model_dump(mode="json")
    env["session"].commit()
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'api.sqlite'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            rows = env["session"].connection().execute(table.select()).mappings().all()
            if rows:
                connection.execute(table.insert(), [dict(row) for row in rows])
    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(DomainError, domain_error_handler)

    def session_dependency():
        with Session(engine, expire_on_commit=False) as session:
            yield session
            session.commit()

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[current_user] = lambda: env["user"]
    prefix = f"/workflow-runs/{w.id}"
    with TestClient(app) as client:
        listing = client.get(f"{prefix}/scientific-gates")
        assert listing.status_code == 200 and not listing.json()["items"][0]["allowed"]
        sources = client.get(f"{prefix}/connections/ab/scientific-evidence/sources", params={"q": "Synthetic"})
        assert sources.status_code == 200 and sources.json()["items"][0]["chunk_id"]
        path = f"{prefix}/connections/ab/scientific-evidence"
        assert client.post(path, json={**payload, "accepted": True}).status_code == 422
        saved = client.post(path, json=payload)
        assert saved.status_code == 201, saved.text
        reviewed = client.post(
            f"{path}/{saved.json()['id']}/review",
            json={
                "workflow_version": w.version,
                "decision": "approve",
                "rationale": "Reviewed scope, methods, parameter semantics and independent calibration controls",
            },
        )
        assert reviewed.status_code == 200 and reviewed.json()["allowed"], reviewed.text
        stale = client.post(
            f"{path}/{saved.json()['id']}/review",
            json={
                "workflow_version": w.version + 1,
                "decision": "approve",
                "rationale": "This stale version must not authorize a different workflow",
            },
        )
        assert stale.status_code == 412
    engine.dispose()


def test_selected_count_resolution_preserves_reviewed_expression(env):
    from backend_v2.app.workflows.assistance import resolve_parameter_links
    from backend_v2.app.workflows.scientific_gates import assert_runtime_approval

    s, _, _, source, target, gate, storage = runtime_fixture(
        env,
        target_configuration={"parameter_links": {"count": {"source": "selected_count", "from_node": "a"}}},
        target_schema={"type": "object", "properties": {"count": {"type": "integer", "minimum": 1}}},
    )
    run_gate(s, gate, storage)
    assert gate.status == "released"
    assert gate_inputs(s, target, {"a"}, {"a": source}) == "ready"
    resolve_parameter_links(target, {"a": source})
    assert target.runtime_spec["parameters"]["count"] == 1
    assert "count" not in target.runtime_spec["input_manifest_template"]["parameters"]
    # Re-entry after legitimate resolution still authorizes the frozen expression.
    assert_runtime_approval(s, gate)
    assert gate_inputs(s, target, {"a"}, {"a": source}) == "ready"
    candidate = s.scalar(select(AuditLog).where(AuditLog.action == CANDIDATE))
    assert "target.parameter_links.count" in candidate.payload["binding"]["required_parameters"]
    target.runtime_spec = {
        **target.runtime_spec,
        "configuration": {
            "parameter_links": {"count": {"source": "upstream_parameter", "from_node": "a", "parameter": "other"}}
        },
    }
    with pytest.raises(ValueError, match="scientific_evidence_approval_required"):
        assert_runtime_approval(s, gate)


def test_nonlinked_runtime_parameter_change_still_fails(env):
    from backend_v2.app.workflows.scientific_gates import assert_runtime_approval

    s, _, _, source, _, gate, _ = runtime_fixture(env)
    source.runtime_spec = {**source.runtime_spec, "parameters": {"unreviewed_temperature": 100}}
    with pytest.raises(ValueError, match="scientific_static_parameters_changed"):
        assert_runtime_approval(s, gate)


@pytest.mark.parametrize(
    "field,value",
    [("command", "different-algorithm"), ("container_image", "other:1"), ("output_parser", "different-parser")],
)
def test_same_version_plugin_declaration_change_invalidates_draft(env, field, value):
    w, edge = draft(env)
    approve_test_gate(env, w)
    s = env["session"]
    assert approval_status(s, w, edge)["allowed"]
    plugin = env["producer"]
    nominal_version = plugin.plugin_version
    setattr(plugin, field, value)
    assert plugin.plugin_version == nominal_version
    assert not approval_status(s, w, edge)["allowed"]


def test_execution_uses_frozen_declaration_and_detects_snapshot_mutation(env):
    from backend_v2.app.workflows.scientific_gates import assert_runtime_approval

    s, _, _, source, _, gate, _ = runtime_fixture(env)
    # A later registry edit cannot rewrite the submitted job's model identity.
    env["producer"].command = "changed-after-submit"
    assert_runtime_approval(s, gate)
    source.runtime_spec = {
        **source.runtime_spec,
        "plugin_snapshot": {**source.runtime_spec["plugin_snapshot"], "command": "changed-after-submit"},
    }
    with pytest.raises(ValueError, match="scientific_evidence_approval_required"):
        assert_runtime_approval(s, gate)
