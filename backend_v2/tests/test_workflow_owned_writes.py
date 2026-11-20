"""Writes other domains make to workflow and candidate rows, through the owning service."""

from __future__ import annotations

import uuid

from backend_v2.app.candidates.models import Candidate
from backend_v2.app.candidates.service import link_structure
from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun
from backend_v2.app.workflows.service import mirror_node_status, record_run_transition, set_workflow_status


def _run() -> WorkflowRun:
    return WorkflowRun(id=uuid.uuid4(), status="draft", graph={"nodes": []}, version=1)


def test_status_change_bumps_the_version_once_and_a_repeat_is_free() -> None:
    run = _run()
    set_workflow_status(run, "running")
    set_workflow_status(run, "running")
    assert (run.status, run.version) == ("running", 2)


def test_design_transition_always_moves_the_version_to_serialize_writers() -> None:
    run = _run()
    record_run_transition(run, graph_flags={"design_learning_required": True})
    record_run_transition(run, graph_flags={"design_learning_required": True})
    assert run.graph == {"nodes": [], "design_learning_required": True}
    assert run.version == 3

    record_run_transition(run, status="succeeded")
    assert (run.status, run.version) == ("succeeded", 4)


def test_node_mirror_writes_only_on_change() -> None:
    node = WorkflowNode(id=uuid.uuid4(), status="draft", error_message=None, version=1)
    mirror_node_status(node, "failed", "exit 1")
    mirror_node_status(node, "failed", "exit 1")
    assert (node.status, node.error_message, node.version) == ("failed", "exit 1", 2)


def test_structure_link_is_versioned() -> None:
    candidate = Candidate(id=uuid.uuid4(), version=1)
    artifact_id = uuid.uuid4()
    link_structure(candidate, artifact_id)
    link_structure(candidate, artifact_id)
    assert (candidate.structure_artifact_id, candidate.version) == (artifact_id, 2)
