import uuid

import pytest
from backend_v2.app.audit.models import AuditLog
from backend_v2.app.compute.models import JobSubmission
from backend_v2.app.core.problem import DomainError
from backend_v2.app.workflows.legacy import normalize_legacy_draft_nodes
from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun
from backend_v2.tests.test_copilot_agent_loop import _project
from backend_v2.tests.test_copilot_agent_loop import session as session_fixture
from sqlalchemy import select


@pytest.fixture(name="session")
def db_session():
    yield from session_fixture.__wrapped__()


def draft(session):
    project, user = _project(session)
    run = WorkflowRun(project_id=project.id, name="Legacy draft", status="draft", created_by=user.id)
    session.add(run)
    session.flush()
    node = WorkflowNode(workflow_run_id=run.id, node_key="fold", node_type="fold_prediction",
                        model_plugin="historical", status="not_started", parameters={"original": "keep"})
    session.add(node)
    session.flush()
    return project, user, run, node


def test_only_retired_spelling_is_normalized_and_audited_once(session):
    project, user, run, node = draft(session)
    original_ids = (run.id, node.id)
    changes = normalize_legacy_draft_nodes(session, project, run.id, user, 1)
    session.flush()
    session.expire_all()
    assert node.status == "draft" and node.version == 2 and run.version == 2
    assert original_ids == (run.id, node.id)
    assert node.parameters == {"original": "keep"}
    assert changes[0]["before"] == "not_started"
    assert normalize_legacy_draft_nodes(session, project, run.id, user, 2) == []
    logs = session.scalars(select(AuditLog).where(AuditLog.action == "workflow.legacy_status.normalize")).all()
    assert len(logs) == 1 and logs[0].payload["changes"] == changes


@pytest.mark.parametrize("case,code", [("foreign", 404), ("missing", 404), ("stale", 412), ("running", 409), ("submitted", 409)])
def test_refuses_foreign_stale_or_executed_history(session, case, code):
    project, user, run, node = draft(session)
    version = 1
    run_id = run.id
    if case == "foreign":
        project, _ = _project(session)
    elif case == "missing":
        run_id = uuid.uuid4()
    elif case == "stale":
        version = 8
    elif case == "running":
        run.status = "running"
    elif case == "submitted":
        session.add(JobSubmission(workflow_run_id=run.id, project_id=project.id, created_by=user.id, compute_backend="docker"))
    session.flush()
    with pytest.raises(DomainError) as exc:
        normalize_legacy_draft_nodes(session, project, run_id, user, version)
    assert exc.value.status_code == code
    assert node.status == "not_started" and node.version == 1
