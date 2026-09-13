"""Regression checks for novice handoffs, without live models or compute."""

from __future__ import annotations

import base64
import json
import uuid
from types import SimpleNamespace

import pytest
from backend_v2.app.compute.schemas import SubmissionCreate
from backend_v2.app.compute.scripts import preview_context, render_script
from backend_v2.app.compute.service import create_submission
from backend_v2.app.copilot import provider_selection
from backend_v2.app.copilot.api import get_config
from backend_v2.app.copilot.models import CopilotConfig
from backend_v2.app.copilot.route_catalog import DesignRoute, RouteStep
from backend_v2.app.copilot.schemas import RoutePlanCreate
from backend_v2.app.copilot.service import _route_option, create_route_plan
from backend_v2.app.core.config import get_settings
from backend_v2.app.core.problem import DomainError
from backend_v2.app.registry.models import LLMProvider, ModelPlugin
from backend_v2.app.research import search_query
from backend_v2.app.wetlab.api import preview_analysis
from backend_v2.app.wetlab.schemas import AnalysisPreviewRequest
from backend_v2.app.workflows import preflight
from backend_v2.app.workflows.models import WorkflowNode
from backend_v2.tests.test_compute_service import compute_session as _compute_session
from backend_v2.tests.test_wetlab_analysis import _unicorn_bytes
from fastapi import Response
from sqlalchemy import func, select

compute_session = _compute_session


def provider(session, name="Shared model", **kwargs):
    row = LLMProvider(
        name=name,
        provider_type="openai",
        endpoint="https://model.test",
        model="test",
        credential_ref="env:GUIDED_TEST_MODEL_KEY",
        enabled=True,
        **kwargs,
    )
    session.add(row)
    session.flush()
    return row


def test_provider_default_ambiguity_and_project_isolation(compute_session, monkeypatch):
    session, _, project, _ = compute_session
    monkeypatch.setattr(provider_selection, "get_settings", lambda: SimpleNamespace(llm_default_provider_ref=""))
    shared = provider(session)
    foreign = provider(session, f"Project {uuid.uuid4()} BYOK")
    assert provider_selection.select_provider(session, project_id=project.id) is shared
    assert provider_selection.select_provider(session, foreign.id, project_id=project.id) is None
    second = provider(session, "Second shared model")
    assert provider_selection.select_provider(session, project_id=project.id) is None
    second.config = {"platform_default": True}
    assert provider_selection.select_provider(session, project_id=project.id) is second
    session.add(CopilotConfig(project_id=project.id, llm_provider_id=shared.id))
    session.flush()
    assert provider_selection.select_provider(session, project_id=project.id) is shared
    shared.enabled = False
    assert provider_selection.select_provider(session, project_id=project.id) is None


def test_get_config_inherits_without_creating_a_row(compute_session, monkeypatch):
    session, user, project, _ = compute_session
    monkeypatch.setattr(provider_selection, "get_settings", lambda: SimpleNamespace(llm_default_provider_ref=""))
    monkeypatch.setenv("GUIDED_TEST_MODEL_KEY", "fixture-placeholder")
    provider(session)
    response = Response()
    result = get_config(project.id, response, session, user)
    assert result.version == 0
    assert result.settings["inherited_provider"] is True
    assert result.settings["llm_model"] == "test"
    assert result.api_key_configured is True
    assert session.scalar(select(func.count()).select_from(CopilotConfig)) == 0


def test_chinese_search_is_translated_before_retrieval(compute_session, monkeypatch):
    session, _, project, _ = compute_session
    monkeypatch.setattr(search_query, "select_provider", lambda *args, **kwargs: object())
    monkeypatch.setattr(search_query, "complete", lambda *args: '{"query": "protein thermostability"}')
    assert search_query.search_topic(session, project.id, "蛋白质热稳定性") == "protein thermostability"
    assert search_query.search_topic(session, project.id, "PD-1 binding") == "PD-1 binding"
    monkeypatch.setattr(search_query, "complete", lambda *args: '{"query": "仍然是中文"}')
    with pytest.raises(DomainError, match="valid English"):
        search_query.search_topic(session, project.id, "蛋白质热稳定性")
    monkeypatch.setattr(search_query, "select_provider", lambda *args, **kwargs: None)
    with pytest.raises(DomainError, match="Configure a model"):
        search_query.search_topic(session, project.id, "蛋白质热稳定性")


def test_research_translation_failure_marks_failed_and_closes_client(compute_session, monkeypatch):
    from unittest.mock import Mock

    from backend_v2.app.research import generation
    from backend_v2.app.research.models import ResearchGeneration

    session, user, project, _ = compute_session
    evidence_tools = Mock()
    monkeypatch.setattr(generation, "EvidenceToolService", lambda **kwargs: evidence_tools)
    monkeypatch.setattr(
        generation, "build_research_workspace",
        lambda *args: SimpleNamespace(model_dump=lambda **kwargs: {"references": []}),
    )
    monkeypatch.setattr(
        search_query, "search_topic",
        Mock(side_effect=DomainError("search_translation_invalid", "Invalid query", status_code=422)),
    )
    row = ResearchGeneration(
        source_project_id=project.id, organization_id=project.organization_id,
        created_by=user.id, status="pending", version=1, request={"topic": "蛋白质热稳定性"},
    )
    result = generation.finalize_research_generation(session, row)
    assert result.status == "failed"
    assert result.error == "Invalid query"
    assert result.version == 2
    evidence_tools.close.assert_called_once_with()
    evidence_tools.search_europe_pmc.assert_not_called()


def test_incomplete_route_is_never_recommended(compute_session):
    session, _, project, _ = compute_session
    plan = create_route_plan(session, project, RoutePlanCreate(project_id=project.id, goal="Acquire a structure"))
    assert plan.recommended_route == ""
    assert not any(option.recommended for option in plan.route_options)
    assert all(option.constraints["missing_plugins"] for option in plan.route_options)


@pytest.mark.parametrize(
    "reply",
    [
        "not JSON",
        json.dumps({"route_id": "invented", "reason": "guessed"}),
        json.dumps({"route_id": "structure-acquisition", "reason": "guessed", "evidence_ids": ["invented"]}),
    ],
)
def test_invalid_model_route_cannot_become_a_workflow(compute_session, monkeypatch, reply):
    session, _, project, _ = compute_session
    session.add(
        ModelPlugin(
            plugin_key="AlphaFold2",
            plugin_version="test",
            name="AF2",
            container_image="af2:test",
            command="run",
            enabled=True,
        )
    )
    session.flush()
    monkeypatch.setattr(provider_selection, "select_provider", lambda *args, **kwargs: object())
    monkeypatch.setattr("backend_v2.app.copilot.provider.complete", lambda *args: reply)
    plan = create_route_plan(
        session, project, RoutePlanCreate(project_id=project.id, goal="Acquire structure", use_model=True)
    )
    assert plan.recommended_route == ""
    assert plan.workflow_spec == {}
    assert not any(option.recommended for option in plan.route_options)
    assert any("could not be validated" in item for item in plan.rationale)


def test_route_autobinds_only_unambiguous_declared_ports():
    upstream = ModelPlugin(
        id=uuid.uuid4(),
        plugin_key="first",
        name="first",
        enabled=True,
        input_ports=[],
        output_ports=[{"name": "pdb", "kind": "protein_structure", "artifact_type": "backbone_set"}],
    )
    downstream = ModelPlugin(
        id=uuid.uuid4(),
        plugin_key="second",
        name="second",
        enabled=True,
        input_ports=[{"name": "backbone", "kind": "protein_structure", "required": True, "accepts": ["backbone_set"]}],
        output_ports=[],
    )
    route = DesignRoute("test", "Test", "Test route", False, (RouteStep("first", ""), RouteStep("second", "")))
    option, _ = _route_option(route, 1, {"first": upstream, "second": downstream}, "test")
    assert option.workflow_spec["nodes"][1]["input_bindings"] == [
        {"port": "backbone", "source": "upstream", "from_node": "first-1", "from_port": "pdb"}
    ]
    upstream.output_ports = [
        *upstream.output_ports,
        {"name": "other", "kind": "protein_structure", "artifact_type": "backbone_set"},
    ]
    option, _ = _route_option(route, 1, {"first": upstream, "second": downstream}, "test")
    assert option.workflow_spec["nodes"][1]["input_bindings"] == []
    downstream.input_ports = [{"not_a_port": True}]
    option, _ = _route_option(route, 1, {"first": upstream, "second": downstream}, "test")
    assert option.constraints["missing_plugins"] == ["second"]


def test_strict_preflight_requires_current_runtime_proof(compute_session, monkeypatch):
    session, _, _, workflow = compute_session
    monkeypatch.setattr(
        preflight, "get_settings", lambda: get_settings().model_copy(update={"compute_require_runtime_proof": True})
    )
    blockers, warnings, checks = preflight.evaluate_preflight(session, workflow, compute_backend="demo")
    assert {"plugin_unvalidated", "plugin_runtime_unproven"} <= {item["code"] for item in blockers}
    assert not warnings
    assert checks["connectivity_checked"] is False
    node = session.scalar(select(WorkflowNode).where(WorkflowNode.workflow_run_id == workflow.id))
    node.container_image = "unvalidated:image"
    blockers, _, _ = preflight.evaluate_preflight(session, workflow, compute_backend="demo")
    assert any(item["code"] == "plugin_runtime_override" for item in blockers)


def test_preview_preserves_ssh_staging(monkeypatch):
    monkeypatch.setattr(
        "backend_v2.app.core.config.get_settings",
        lambda: SimpleNamespace(
            lsf_remote_root="/cluster/bda", lsf_queue="normal", lsf_staging_mode="ssh", lsf_upload_wrapper=""
        ),
    )
    ctx = preview_context(SimpleNamespace(queue=None, parameters={}, container_image=None), None, "lsf", "run-model")
    assert ctx.staging_mode == "ssh"
    script = render_script(ctx)
    assert "output-manifest.json" in script
    assert "curl" not in script


def test_stale_preview_and_second_submit_are_rejected(compute_session):
    session, user, project, workflow = compute_session
    with pytest.raises(DomainError) as stale:
        create_submission(
            session,
            workflow=workflow,
            project=project,
            user=user,
            idempotency_key="stale",
            payload=SubmissionCreate(compute_backend="demo", workflow_version=workflow.version + 1),
        )
    assert stale.value.status_code == 412
    create_submission(
        session,
        workflow=workflow,
        project=project,
        user=user,
        idempotency_key="first",
        payload=SubmissionCreate(compute_backend="demo", workflow_version=workflow.version),
    )
    with pytest.raises(DomainError) as duplicate:
        create_submission(
            session,
            workflow=workflow,
            project=project,
            user=user,
            idempotency_key="second",
            payload=SubmissionCreate(compute_backend="demo"),
        )
    assert duplicate.value.error_code == "workflow_locked"
    assert session.scalar(select(func.count()).select_from(WorkflowNode)) == 2


def test_standalone_analysis_needs_no_project_or_artifact():
    result = preview_analysis(
        AnalysisPreviewRequest(instrument="akta", content_base64=base64.b64encode(_unicorn_bytes()).decode()), user=None
    )
    assert result.experiment_type == "akta_purification"
    assert result.summary


@pytest.mark.parametrize("data", [b"not an instrument file", b"PKbroken zip"])
def test_malformed_instrument_preview_is_actionable(data):
    with pytest.raises(DomainError) as invalid:
        preview_analysis(
            AnalysisPreviewRequest(instrument="akta", content_base64=base64.b64encode(data).decode()), user=None
        )
    assert invalid.value.status_code == 422


def _reviews(session, user, workflow):
    from backend_v2.app.workflows.api import preview_node_script
    from backend_v2.app.workflows.schemas import ScriptPreviewCreate
    return {node.id: preview_node_script(node.id, ScriptPreviewCreate(compute_backend='docker'), session, user).review_fingerprint
            for node in session.scalars(select(WorkflowNode).where(WorkflowNode.workflow_run_id == workflow.id))}


def test_reviewed_submission_persists_once_and_replays_identically(compute_session):
    session, user, project, workflow = compute_session
    reviews = _reviews(session, user, workflow)
    payload = SubmissionCreate(compute_backend='docker', workflow_version=workflow.version, review_fingerprints=reviews)
    submission, jobs = create_submission(session, workflow=workflow, project=project, user=user,
                                         payload=payload, idempotency_key='reviewed')
    same, repeated = create_submission(session, workflow=workflow, project=project, user=user,
                                       payload=payload, idempotency_key='reviewed')
    assert submission.id == same.id
    assert len(jobs) == len(repeated) == 2


@pytest.mark.parametrize('change', ['plugin', 'parameters', 'site', 'missing_review'])
def test_submission_rejects_changes_since_review(compute_session, monkeypatch, change):
    from backend_v2.app.compute.models import Job
    session, user, project, workflow = compute_session
    reviews = _reviews(session, user, workflow)
    if change == 'plugin':
        session.scalar(select(ModelPlugin)).command = 'different-command'
    elif change == 'parameters':
        session.scalar(select(WorkflowNode)).parameters = {'count': 2}
    elif change == 'site':
        settings = get_settings().model_copy(update={'docker_host': 'tcp://different.example:2376'})
        monkeypatch.setattr('backend_v2.app.compute.review.get_settings', lambda: settings)
    else:
        reviews.pop(next(iter(reviews)))
    with pytest.raises(DomainError) as error, session.begin_nested():
        create_submission(session, workflow=workflow, project=project, user=user, idempotency_key='stale-review',
            payload=SubmissionCreate(compute_backend='docker', workflow_version=workflow.version, review_fingerprints=reviews))
    assert error.value.error_code in {'preview_changed', 'preview_incomplete'}
    assert session.scalar(select(func.count()).select_from(Job)) == 0


def test_foreign_byok_cannot_be_bound_by_configuration(compute_session):
    from backend_v2.app.copilot.schemas import CopilotConfigUpdate
    from backend_v2.app.copilot.service import put_config
    session, _, project, _ = compute_session
    foreign = provider(session, f'Project {uuid.uuid4()} BYOK')
    with pytest.raises(DomainError) as error:
        put_config(session, None, project.id, CopilotConfigUpdate(llm_provider_id=foreign.id), 0)
    assert error.value.status_code == 403


@pytest.mark.parametrize('pairs', ['ab', [['only-one']], [[{}, 'max']], [['min', 'max', 'extra']]])
def test_malformed_plugin_ordering_rules_block_instead_of_crashing(pairs):
    node = SimpleNamespace(node_key='node', parameters={})
    plugin = SimpleNamespace(parameter_schema={'x-bda-order-pairs': pairs})
    assert preflight.order_pair_blockers(node, plugin)[0]['code'] == 'plugin_order_pairs_invalid'


def test_enzyme_project_does_not_receive_binder_template(compute_session, monkeypatch):
    from backend_v2.app.copilot import service
    from backend_v2.app.copilot.route_catalog import routes_for
    session, _, project, _ = compute_session
    project.project_type = 'enzyme_design'
    monkeypatch.setattr(service, 'routes_for', lambda **kwargs: routes_for(has_structure=True))
    plan = create_route_plan(session, project, RoutePlanCreate(project_id=project.id, goal='Improve enzyme stability'))
    assert plan.route_options == []
    assert plan.recommended_route == ''
    assert any('project type' in item for item in plan.rationale)
