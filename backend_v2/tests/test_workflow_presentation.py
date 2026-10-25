from copy import deepcopy

import pytest
from backend_v2.app.core.problem import DomainError
from backend_v2.app.workflows.models import WorkflowRun
from backend_v2.app.workflows.schemas import RoutePresentation, WorkflowCreate
from backend_v2.app.workflows.service import replace_workflow_graph, update_presentation
from backend_v2.tests.test_copilot_chain import _project
from backend_v2.tests.test_copilot_chain import session as _session
from pydantic import ValidationError

session = _session


def test_rename_retains_aliases_even_when_a_caller_omits_them(session):
    project, user = _project(session)
    run = WorkflowRun(project_id=project.id, created_by=user.id, name="Legacy A", graph={})
    session.add(run)
    session.flush()
    update_presentation(session, run, _presentation().model_copy(update={"aliases": []}), user, project, run.version)
    update_presentation(session, run, _presentation().model_copy(update={"name": "新名", "aliases": []}), user, project, run.version)
    assert run.graph["route_presentation"]["aliases"] == ["Legacy A", "支架改造"]


@pytest.mark.parametrize("stored", [[], {"aliases": "legacy"}, {"aliases": [None, {}, "Legacy A"]}])
def test_malformed_legacy_display_metadata_can_be_repaired(session, stored):
    project, user = _project(session)
    run = WorkflowRun(project_id=project.id, created_by=user.id, name="Legacy A",
        graph={"route_presentation": stored, "localized_content": []})
    session.add(run)
    session.flush()
    update_presentation(session, run, _presentation(), user, project, run.version)
    assert "Legacy A" in run.graph["route_presentation"]["aliases"]
    assert run.graph["localized_content"]["name"]["zh"] == "支架改造"


def test_presentation_http_enforces_versions_scope_and_read_only_roles(session):
    from backend_v2.app.core.database import get_session
    from backend_v2.app.core.problem import domain_error_handler
    from backend_v2.app.identity.deps import current_user
    from backend_v2.app.workflows.api import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    project, user = _project(session)
    _, outsider = _project(session)
    run = WorkflowRun(project_id=project.id, created_by=user.id, name="Route 1", graph={})
    session.add(run)
    session.flush()
    app = FastAPI()
    app.add_exception_handler(DomainError, domain_error_handler)
    app.include_router(router)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[current_user] = lambda: user
    url = f"/workflow-runs/{run.id}/presentation"
    with TestClient(app) as client:
        payload = _presentation().model_dump()
        assert client.patch(url, json=payload).status_code == 428
        assert client.patch(url, json=payload, headers={"If-Match": 'W/"0"'}).status_code == 412
        response = client.patch(url, json=payload, headers={"If-Match": f'W/"{run.version}"'})
        assert response.status_code == 200
        assert response.headers["etag"] == f'W/"{run.version}"'
        headers = {"If-Match": response.headers["etag"]}
        app.dependency_overrides[current_user] = lambda: outsider
        assert client.patch(url, json=payload, headers=headers).status_code == 403
        app.dependency_overrides[current_user] = lambda: user
        user.role = "viewer"
        assert client.patch(url, json=payload, headers=headers).status_code == 403


def _presentation():
    return RoutePresentation(name="支架改造", name_en="Scaffold engineering", category="design",
        method="Scaffold engineering", summary="Preserve the scaffold and compare changes.",
        objective="Test the hypothesis", evidence="Not experimentally validated", next_step="Review evidence",
        record_role="current_plan", aliases=["Route 1"])


def test_presentation_keeps_execution_and_history_intact(session):
    project, user = _project(session)
    graph = {"nodes": [{"key": "existing", "parameters": {"seed": 7}}], "edges": [], "layout": {"zoom": 1}}
    run = WorkflowRun(project_id=project.id, created_by=user.id, name="Route 1", status="running", graph=deepcopy(graph))
    session.add(run)
    session.flush()
    version = run.version
    update_presentation(session, run, _presentation(), user, project, version)
    assert run.status == "running"
    assert {key: run.graph[key] for key in graph} == graph
    assert run.graph["route_presentation"]["aliases"] == ["Route 1"]
    version = run.version
    update_presentation(session, run, _presentation(), user, project, version)
    assert run.version == version
    with pytest.raises(DomainError, match="modified"):
        update_presentation(session, run, _presentation(), user, project, version - 1)
    other, _ = _project(session)
    with pytest.raises(DomainError, match="not found"):
        update_presentation(session, run, _presentation(), user, other, version)


def test_graph_edit_preserves_classification_and_cannot_desynchronize_names(session):
    project, user = _project(session)
    run = WorkflowRun(project_id=project.id, created_by=user.id, name="Route 1", status="draft", graph={"nodes": [], "edges": []})
    session.add(run)
    session.flush()
    update_presentation(session, run, _presentation(), user, project, run.version)
    replace_workflow_graph(session, run, WorkflowCreate(name=run.name), user, project, run.version)
    assert run.graph["route_presentation"] == _presentation().model_dump()
    with pytest.raises(DomainError, match="presentation"):
        replace_workflow_graph(session, run, WorkflowCreate(name="A different name"), user, project, run.version)


@pytest.mark.parametrize("changes", [{"category": "anything"}, {"name": " "}, {"status": "succeeded"}, {"name": "x" * 61}])
def test_display_contract_rejects_bad_categories_and_execution_fields(changes):
    with pytest.raises(ValidationError):
        RoutePresentation.model_validate({**_presentation().model_dump(), **changes})
