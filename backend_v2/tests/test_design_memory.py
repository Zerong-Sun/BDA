"""General design learning: enforce review, preserve history, feed outcomes forward."""

import uuid

import pytest
from backend_v2.app.compute.models import Job
from backend_v2.app.design_memory.models import DesignLesson
from backend_v2.app.design_memory.service import blockers
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun
from backend_v2.tests.test_learning import client as learning_client
from sqlalchemy import select


@pytest.fixture(name="client")
def design_client():
    yield from learning_client.__wrapped__()


def run(ctx, parent=None):
    api, ids, _ = ctx
    response = api.post(
        f"/api/v2/projects/{ids['project']}/workflow-runs",
        json={
            "name": "Synthetic design",
            "derived_from_id": parent,
            "nodes": [{"key": "design", "node_type": "design", "model_plugin": "synthetic"}],
            "edges": [],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def state(ctx, rid):
    response = ctx[0].get(f"/api/v2/workflow-runs/{rid}/design-learning")
    assert response.status_code == 200, response.text
    return response.json()


def review(ctx, rid, patch=None, expected=201):
    current = state(ctx, rid)
    keys = [i["key"] for i in current["checklist"]] + [f"lesson:{r['id']}" for r in current["lessons"]]
    payload = {
        "fingerprint": current["fingerprint"],
        "memory_digest": current["memory_digest"],
        "objective": "Increase synthetic response",
        "context": "Synthetic control system",
        "items": [
            {
                "key": k,
                "disposition": "test",
                "rationale": "Scope matched; uncertain evidence",
                "hypothesis": f"Hypothesis {k}",
                "action": "Change one factor",
                "comparison": "Matched unchanged control",
                "readout": "Synthetic units",
                "decision_rule": "Support only if difference exceeds calibrated error",
            }
            for k in keys
        ],
    }
    if patch:
        patch(payload)
    response = ctx[0].post(
        f"/api/v2/workflow-runs/{rid}/design-learning/reviews",
        json=payload,
        headers={"If-Match": f'W/"{current["workflow_version"]}"'},
    )
    assert response.status_code == expected, response.text
    return response.json()


def lesson_body(**patch):
    return {
        "title": "Synthetic lesson",
        "statement": "Effect requires matched conditions",
        "conditions": "Synthetic only",
        "limitations": "Not experimentally verified",
        "evidence": ["synthetic:observation-1"],
        "outcome": "hypothesis",
        "next_design_change": "Measure the matched control",
        **patch,
    }


def lesson(ctx, **patch):
    response = ctx[0].post(f"/api/v2/projects/{ctx[1]['project']}/design-lessons", json=lesson_body(**patch))
    assert response.status_code == 201, response.text
    return response.json()


def finish(ctx, rid, status="succeeded"):
    with ctx[2]() as session:
        session.get(WorkflowRun, uuid.UUID(rid)).status = status
        session.commit()


def test_new_design_and_api_submission_require_review(client):
    rid = run(client)
    assert state(client, rid)["required"]
    response = client[0].post(
        f"/api/v2/workflow-runs/{rid}/submissions",
        json={"compute_backend": "docker"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 409, response.text
    assert any(e["code"] == "design_learning_review_required" for e in response.json()["errors"])
    with client[2]() as session:
        assert not list(session.scalars(select(Job)))
    review(client, rid)
    assert state(client, rid)["state"] == "ready"


def test_prior_lessons_and_all_core_questions_must_be_checked(client):
    lesson(client)
    rid = run(client)
    review(client, rid, lambda p: p["items"].pop(), expected=422)
    review(client, rid, lambda p: p["items"][0].update({"action": " "}), expected=422)
    review(client, rid, lambda p: p["items"].append(p["items"][0]), expected=422)
    review(
        client,
        rid,
        lambda p: p["items"][0].update(
            {"disposition": "not_applicable", "rationale": "Outside the current system", "action": ""}
        ),
    )


def test_design_edits_and_new_evidence_invalidate_but_layout_does_not(client):
    rid = run(client)
    review(client, rid)
    with client[2]() as s:
        workflow = s.get(WorkflowRun, uuid.UUID(rid))
        workflow.graph = {**workflow.graph, "layout": {"x": 42}}
        s.commit()
    assert state(client, rid)["state"] == "ready"
    with client[2]() as s:
        node = s.scalar(select(WorkflowNode).where(WorkflowNode.workflow_run_id == uuid.UUID(rid)))
        node.parameters = {"direction": "reverse"}
        s.commit()
    assert state(client, rid)["state"] == "stale"
    review(client, rid)
    lesson(client)
    assert state(client, rid)["state"] == "stale"
    review(client, rid)
    assert len(state(client, rid)["history"]) == 3


def test_stale_snapshot_and_optimistic_version_are_rejected(client):
    rid = run(client)
    review(client, rid, lambda p: p.update({"memory_digest": "a" * 64}), expected=409)
    saved = review(client, rid)
    payload = {k: v for k, v in saved["payload"].items() if k != "lesson_snapshots"}
    response = client[0].post(
        f"/api/v2/workflow-runs/{rid}/design-learning/reviews", json=payload, headers={"If-Match": 'W/"1"'}
    )
    assert response.status_code == 412


@pytest.mark.parametrize("outcome", ["supported", "refuted", "inconclusive", "method_invalid", "execution_blocked"])
def test_feedback_keeps_original_hypothesis_and_feeds_next_design(client, outcome):
    rid = run(client)
    original = review(client, rid)
    finish(client, rid, "cancelled" if outcome == "execution_blocked" else "succeeded")
    response = client[0].post(
        f"/api/v2/workflow-runs/{rid}/design-learning/feedback",
        json={**lesson_body(outcome=outcome), "review_id": original["id"], "item_key": "identity"},
    )
    assert response.status_code == 201, response.text
    current = state(client, rid)
    assert current["state"] == "frozen"
    assert current["review"]["payload"] == original["payload"]
    assert "identity" not in current["pending_feedback"]
    assert len(current["pending_feedback"]) == 5
    next_id = run(client, rid)
    assert state(client, next_id)["lessons"][0]["payload"]["outcome"] == outcome
    review(client, next_id)
    with client[2]() as s:
        assert blockers(s, s.get(WorkflowRun, uuid.UUID(next_id)))[0]["code"] == "design_learning_feedback_required"
    for key in current["pending_feedback"]:
        response = client[0].post(
            f"/api/v2/workflow-runs/{rid}/design-learning/feedback",
            json={**lesson_body(outcome="inconclusive"), "review_id": original["id"], "item_key": key},
        )
        assert response.status_code == 201
    assert state(client, next_id)["state"] == "stale"
    review(client, next_id)
    with client[2]() as s:
        assert not blockers(s, s.get(WorkflowRun, uuid.UUID(next_id)))


def test_feedback_cannot_reference_another_design_or_unexecuted_hypothesis(client):
    rid = run(client)
    original = review(client, rid)
    url = f"/api/v2/workflow-runs/{rid}/design-learning/feedback"
    body = {**lesson_body(outcome="supported"), "review_id": original["id"], "item_key": "identity"}
    assert client[0].post(url, json=body).status_code == 409
    finish(client, rid)
    body["review_id"] = str(uuid.uuid4())
    assert client[0].post(url, json=body).status_code == 404
    body.update(review_id=original["id"], item_key="invented")
    assert client[0].post(url, json=body).status_code == 422


def test_feedback_must_use_final_review_not_abandoned_draft(client):
    rid = run(client)
    abandoned = review(client, rid)
    review(client, rid)
    finish(client, rid)
    response = client[0].post(
        f"/api/v2/workflow-runs/{rid}/design-learning/feedback",
        json={**lesson_body(outcome="inconclusive"), "review_id": abandoned["id"], "item_key": "identity"},
    )
    assert response.status_code == 409


def test_manual_execution_has_review_and_feedback_gates_without_creating_jobs(client):
    rid = run(client)
    endpoint = f"/api/v2/workflow-runs/{rid}/design-learning/manual-execution"

    def transition(phase):
        return client[0].post(
            endpoint, json={"phase": phase}, headers={"If-Match": f'W/"{state(client, rid)["workflow_version"]}"'}
        )

    # Executable routes cannot use the manual path to bypass compute submission.
    assert transition("start").status_code == 409
    with client[2]() as s:
        node = s.scalar(select(WorkflowNode).where(WorkflowNode.workflow_run_id == uuid.UUID(rid)))
        node.execution_mode = "manual"
        s.commit()
    assert transition("start").status_code == 409
    original = review(client, rid)
    response = transition("start")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "running"
    assert transition("complete").status_code == 409
    for item in original["payload"]["items"]:
        response = client[0].post(
            f"/api/v2/workflow-runs/{rid}/design-learning/feedback",
            json={**lesson_body(outcome="execution_blocked"), "review_id": original["id"], "item_key": item["key"]},
        )
        assert response.status_code == 201, response.text
    response = transition("complete")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert state(client, rid)["manual_execution_complete"]
    assert transition("complete").status_code == 409
    with client[2]() as s:
        assert not list(s.scalars(select(Job)))


def test_revision_preserves_history_and_import_requires_source_access(client):
    initial = lesson(client)
    newer = lesson(client, supersedes_id=initial["id"], outcome="refuted")
    rid = run(client)
    assert [r["id"] for r in state(client, rid)["lessons"]] == [newer["id"]]
    response = client[0].post(
        f"/api/v2/projects/{client[1]['other']}/design-lessons/import", json={"source_id": newer["id"]}
    )
    assert response.status_code == 201
    assert response.json()["payload"]["origin"]["snapshot"]["payload"]["outcome"] == "refuted"
    with client[2]() as s:
        foreign_org = Organization(name="Private")
        s.add(foreign_org)
        s.flush()
        foreign_project = Project(
            organization_id=foreign_org.id, owner_id=client[1]["user"], name="Private", project_type="test"
        )
        s.add(foreign_project)
        s.flush()
        foreign_lesson = DesignLesson(
            project_id=foreign_project.id, created_by=client[1]["user"], payload=lesson_body()
        )
        s.add(foreign_lesson)
        s.flush()
        foreign_id = foreign_lesson.id
        s.get(User, client[1]["user"]).role = "researcher"
        s.commit()
    assert (
        client[0]
        .post(f"/api/v2/projects/{client[1]['project']}/design-lessons/import", json={"source_id": str(foreign_id)})
        .status_code
        == 403
    )
    with client[2]() as s:
        s.get(User, client[1]["user"]).role = "viewer"
        s.commit()
    assert (
        client[0].post(f"/api/v2/projects/{client[1]['project']}/design-lessons", json=lesson_body()).status_code == 403
    )


def test_graph_replace_cannot_erase_gate_and_legacy_is_not_rewritten(client):
    rid = run(client)
    response = client[0].put(
        f"/api/v2/workflow-runs/{rid}/graph",
        json={"name": "Changed", "nodes": [], "edges": []},
        headers={"If-Match": 'W/"1"'},
    )
    assert response.status_code == 200, response.text
    assert response.json()["graph"]["design_learning_required"]
    with client[2]() as s:
        historical = WorkflowRun(
            project_id=client[1]["project"],
            name="Historical",
            created_by=client[1]["user"],
            graph={"nodes": [], "edges": []},
        )
        s.add(historical)
        s.flush()
        assert not blockers(s, historical)


def test_manual_completion_uses_corrected_feedback_without_erasing_history(client):
    rid = run(client)
    with client[2]() as s:
        s.scalar(select(WorkflowNode).where(WorkflowNode.workflow_run_id == uuid.UUID(rid))).execution_mode = "manual"
        s.commit()
    original = review(client, rid)
    endpoint = f"/api/v2/workflow-runs/{rid}/design-learning"

    def transition(phase):
        return client[0].post(
            endpoint + "/manual-execution",
            json={"phase": phase},
            headers={"If-Match": f'W/"{state(client, rid)["workflow_version"]}"'},
        )

    assert transition("start").status_code == 200
    old = None
    for item in original["payload"]["items"]:
        response = client[0].post(
            endpoint + "/feedback",
            json={
                **lesson_body(outcome="method_invalid" if item["key"] == "identity" else "supported"),
                "review_id": original["id"],
                "item_key": item["key"],
            },
        )
        assert response.status_code == 201
        if item["key"] == "identity":
            old = response.json()
    wrong_question = next(i["key"] for i in original["payload"]["items"] if i["key"] != "identity")
    rejected = client[0].post(
        endpoint + "/feedback",
        json={
            **lesson_body(outcome="supported", supersedes_id=old["id"]),
            "review_id": original["id"],
            "item_key": wrong_question,
        },
    )
    assert rejected.status_code == 422
    replacement = client[0].post(
        endpoint + "/feedback",
        json={
            **lesson_body(outcome="supported", supersedes_id=old["id"]),
            "review_id": original["id"],
            "item_key": "identity",
        },
    )
    assert replacement.status_code == 201
    assert transition("complete").json()["status"] == "succeeded"
    # Corrections affect completion but retain the original observation in the journal.
    assert any(row["id"] == old["id"] for row in state(client, rid)["feedback"])
