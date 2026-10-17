from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from backend_v2.app.core.database import get_session
from backend_v2.app.core.problem import DomainError, domain_error_handler
from backend_v2.app.identity.deps import current_user
from backend_v2.app.registry.api import router
from backend_v2.app.registry.extensions import ExtensionAssessmentCreate, assess, extension_catalog, manifests
from backend_v2.app.registry.models import ComputeNode, LLMProvider, ModelPlugin
from backend_v2.app.registry.qualification import model_qualification_issues, validate_qualification_resources
from backend_v2.app.registry.runtime_validation import plugin_declaration_fingerprint, runtime_validation_is_current
from backend_v2.app.registry.schemas import RegistryResourceUpdate
from backend_v2.app.registry.service import create_resource, update_resource
from backend_v2.tests.test_copilot_agent_loop import session as session_fixture
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError


@pytest.fixture(name="session")
def db_session():
    yield from session_fixture.__wrapped__()


def _review(**overrides):
    return {"schema_version": "1.0", "plugin_key": "boltz", "plugin_version": "2", "code_reference": "https://github.com/jwohlwend/boltz/tree/reviewed-version",
            "code_license": "MIT", "checkpoint_identifier": "exact-model-weights", "checkpoint_sha256": "a" * 64,
            "checkpoint_license": "MIT", "license_reference": "https://github.com/jwohlwend/boltz/blob/main/LICENSE",
            "license_mode": "open", "intended_use": "research", "allowed_uses": ["research"], "review_status": "approved",
            "reviewer": "Registry maintainer", "reviewed_at": "2020-01-01T00:00:00Z", "validation_scope": "One bounded folding benchmark", **overrides}


def _plugin(**overrides):
    plugin = SimpleNamespace(id=uuid.uuid4(), name="Boltz", plugin_key="boltz", plugin_version="2", enabled=True,
                             validation_status="valid", resources={"gpu": True, "gpu_count": 1, "scientific_qualification": _review()},
                             manifest_checksum="b" * 64, runtime_mode="container", container_image="model@sha256:" + "c" * 64,
                             command="predict", parameter_schema={}, output_schema={}, input_ports=[], output_ports=[],
                             runtime_setup=[], output_parser=None, input_adapter=None, site_overrides={}, runtime_validation_status="proven", **overrides)
    plugin.runtime_validation_evidence = {"declaration_fingerprint": plugin_declaration_fingerprint(plugin)}
    return plugin


def _node():
    return SimpleNamespace(id=uuid.uuid4(), backend="docker", queue=None, enabled=True, labels={"gpu_count": 2}, health_status="healthy")


def _proposal():
    return ExtensionAssessmentCreate(license_review_ref="review-1", data_review_ref="data-1", validation_plan_ref="benchmark-1", budget_review_ref="budget-1")


def _definition(identifier):
    return next(item for item in manifests()[0] if item.id == identifier)


def test_versioned_manifest_catalog_has_resource_license_data_and_triggers():
    definitions, checksum = manifests()
    assert len(definitions) == 13
    assert len(checksum) == 64
    for item in definitions:
        assert item.resources and item.license_boundary and item.data_boundary and item.rollout_trigger and item.effort
        assert item.function_ids and all(key.startswith("F") for key in item.function_ids)
        assert item.sources and len(item.requirements) == 5


def test_scientific_trial_readiness_requires_exact_current_records():
    plugin, node = _plugin(), _node()
    result = assess(_definition("scientific-models"), proposal=_proposal(), plugin=plugin, node=node)
    assert result.ready_for_trial
    assert result.scientific_validation == "not_assessed"
    assert result.state == "needs_configuration"  # No installation action or operational transition.
    plugin.command = "changed runtime"
    result = assess(_definition("scientific-models"), proposal=_proposal(), plugin=plugin, node=node)
    assert not result.ready_for_trial
    assert any(item.id == "runtime_proof" and item.status == "missing" for item in result.checks)
    plugin.enabled = False
    assert assess(_definition("scientific-models"), plugin=plugin).state == "disabled"


@pytest.mark.parametrize("count", [0, "2", True, None])
def test_gpu_declarations_cannot_be_inferred_from_truthy_values(count):
    node = _node()
    node.labels["gpu_count"] = count
    result = assess(_definition("scientific-models"), proposal=_proposal(), plugin=_plugin(), node=node)
    assert not result.ready_for_trial
    assert any(item.id == "gpu_resources" and item.status == "missing" for item in result.checks)


def test_malformed_legacy_resource_records_report_gaps_instead_of_crashing():
    plugin, node = _plugin(), _node()
    plugin.resources = ["legacy-invalid"]
    result = assess(_definition("scientific-models"), proposal=_proposal(), plugin=plugin, node=node)
    assert not result.ready_for_trial
    assert any("malformed" in item for item in result.blockers)
    node.labels = ["legacy-invalid"]
    result = assess(_definition("scientific-models"), proposal=_proposal(), plugin=_plugin(), node=node)
    assert not result.ready_for_trial
    provider = SimpleNamespace(enabled=True, model="model", credential_ref="env:PRIVATE", config=["legacy-invalid"])
    result = assess(_definition("local-inference"), proposal=_proposal(), provider=provider)
    assert any(item.id == "local_deployment" and item.status == "missing" for item in result.checks)


def test_no_ready_state_for_demo_backend_unresolved_site_or_missing_reviews():
    node, plugin = _node(), _plugin()
    node.backend = "demo"
    assert not assess(_definition("scientific-models"), proposal=_proposal(), plugin=plugin, node=node).ready_for_trial
    node.backend = "lsf"
    plugin.runtime_mode, plugin.container_image = "conda", "site://unresolved"
    result = assess(_definition("scientific-models"), proposal=_proposal(), plugin=plugin, node=node)
    assert any(item.id == "site_runtime" and item.status == "blocked" for item in result.checks)
    assert len(assess(_definition("scientific-models"), plugin=_plugin(), node=_node()).blockers) >= 4


def test_future_plans_never_become_available_from_filled_forms():
    for definition in manifests()[0]:
        if definition.adapter == "planned":
            result = assess(definition, proposal=_proposal(), plugin=_plugin(), node=_node())
            assert result.state == "planned"
            assert not result.ready_for_trial
            assert any(item.id == "adapter" and item.status == "blocked" for item in result.checks)


def test_local_provider_is_only_declared_local_not_inferred_from_url():
    provider = SimpleNamespace(enabled=True, model="model", credential_ref="env:PRIVATE", config={}, endpoint="http://localhost:1234")
    result = assess(_definition("local-inference"), proposal=_proposal(), provider=provider)
    assert any(item.id == "local_deployment" and item.status == "missing" for item in result.checks)
    provider.config["deployment_kind"] = "local"
    result = assess(_definition("local-inference"), proposal=_proposal(), provider=provider)
    assert not result.blockers
    assert not result.ready_for_trial  # Declaration does not prove a working provider.


def test_legacy_qualification_warns_but_explicit_restriction_blocks():
    plugin = _plugin()
    plugin.resources = {}
    blockers, warnings = model_qualification_issues(plugin)
    assert not blockers and warnings[0]["code"] == "model_qualification_missing"
    for changes, code in [
        ({"review_status": "pending"}, "model_qualification_not_approved"),
        ({"plugin_version": "old"}, "model_qualification_identity_mismatch"),
        ({"license_mode": "research_only", "intended_use": "commercial", "allowed_uses": ["commercial"]}, "model_qualification_research_only"),
        ({"allowed_uses": []}, "model_qualification_use_restricted"),
        ({"expires_at": "2020-01-02T00:00:00Z"}, "model_qualification_expired"),
        ({"reviewed_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()}, "model_qualification_future_review"),
    ]:
        plugin.resources = {"scientific_qualification": _review(**changes)}
        assert code in {item["code"] for item in model_qualification_issues(plugin)[0]}


def test_qualification_contract_rejects_bad_digests_unknown_fields_and_unreviewed_approval():
    for changes in ({"checkpoint_sha256": "unverified"}, {"reviewer": ""}, {"reviewed_at": None}, {"install_command": "curl remote | sh"}):
        with pytest.raises(DomainError) as exc:
            validate_qualification_resources({"scientific_qualification": _review(**changes)})
        assert exc.value.status_code == 422
    with pytest.raises(ValidationError):
        ExtensionAssessmentCreate(license_review_ref="x" * 501)
    with pytest.raises(ValidationError):
        ExtensionAssessmentCreate(endpoint="http://localhost", api_key="secret")


def test_qualification_changes_invalidate_runtime_proof_and_registry_rejects_invalid_review(session):
    plugin = _plugin()
    assert runtime_validation_is_current(plugin)
    plugin.resources = copy.deepcopy(plugin.resources)
    plugin.resources["scientific_qualification"]["checkpoint_sha256"] = "d" * 64
    assert not runtime_validation_is_current(plugin)
    data = {"plugin_key": "bad", "plugin_version": "1", "name": "Bad", "container_image": "image", "command": "run", "resources": {"scientific_qualification": {}}}
    with pytest.raises(DomainError):
        create_resource(session, "model_plugin", data)
    row = ModelPlugin(plugin_key="legacy", plugin_version="1", name="Legacy", container_image="image", command="run", resources={})
    session.add(row)
    session.flush()
    with pytest.raises(DomainError):
        update_resource(row, RegistryResourceUpdate(data={"resources": {"scientific_qualification": _review(checkpoint_sha256="bad")}}), row.version)


def test_live_catalog_reflects_registry_changes_without_revealing_connection_details(session):
    row = ModelPlugin(plugin_key="boltz", plugin_version="2", name="Boltz", container_image="private-runtime-path", command="private-command", resources={}, enabled=True)
    node = ComputeNode(name="Reviewed node", backend="lsf", labels={}, enabled=True)
    provider = LLMProvider(name="Local service", provider_type="openai", endpoint="https://private-host", model="model", credential_ref="env:DO_NOT_REVEAL", config={"deployment_kind": "local"}, enabled=True)
    session.add_all([row, node, provider])
    session.flush()
    result = extension_catalog(session)
    assert next(item for item in result.extensions if item.manifest.id == "scientific-models").assessment.state == "needs_configuration"
    serialized = result.model_dump_json()
    assert "private-runtime-path" not in serialized and "DO_NOT_REVEAL" not in serialized and "private-host" not in serialized
    row.enabled = False
    session.flush()
    assert next(item for item in extension_catalog(session).extensions if item.manifest.id == "scientific-models").assessment.state == "disabled"


def test_api_read_auth_admin_assessment_and_missing_ids(session):
    app = FastAPI()
    app.add_exception_handler(DomainError, domain_error_handler)
    app.include_router(router)
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        assert client.get("/registry/extensions").status_code == 401
        app.dependency_overrides[current_user] = lambda: SimpleNamespace(role="researcher")
        assert client.get("/registry/extensions").status_code == 200
        assert client.post("/registry/extensions/robotic-assay/assessments", json={}).status_code == 403
        app.dependency_overrides[current_user] = lambda: SimpleNamespace(role="admin")
        response = client.post("/registry/extensions/robotic-assay/assessments", json={})
        assert response.status_code == 200 and response.json()["state"] == "planned"
        assert client.post("/registry/extensions/unknown/assessments", json={}).status_code == 404
        assert client.post("/registry/extensions/scientific-models/assessments", json={"model_plugin_id": str(uuid.uuid4())}).status_code == 404
        assert client.post("/registry/extensions/local-inference/assessments", json={"endpoint": "http://localhost"}).status_code == 422
