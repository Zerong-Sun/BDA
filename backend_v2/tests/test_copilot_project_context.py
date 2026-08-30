from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, cast

from backend_v2.app.copilot.project_context import (
    MAX_CONTEXT_ITEMS,
    MAX_CONTEXT_TEXT,
    ProjectContextService,
    _sanitize,
)


class FakeSession:
    def __init__(self, outputs):
        self.outputs = iter(outputs)

    def scalars(self, statement):
        return iter(next(self.outputs))


def test_project_context_reads_each_operational_data_family() -> None:
    project_id = uuid.uuid4()
    workflow_id = uuid.uuid4()
    target = SimpleNamespace(
        id=uuid.uuid4(),
        name="Target A",
        uniprot_accession="P12345",
        organism="human",
        identity_status="confirmed",
        structure_status="available",
        structure_artifact_id=uuid.uuid4(),
    )
    candidate = SimpleNamespace(
        id=uuid.uuid4(),
        candidate_key="C1",
        name="Candidate A",
        status="ranked",
        rank=1,
        score=0.9,
        scores={"interface": 0.8},
        properties={"token": "secret", "safe": True},
        structure_artifact_id=uuid.uuid4(),
        complex_artifact_id=None,
    )
    result = SimpleNamespace(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        candidate_ref="C1",
        experiment_type="BLI",
        pass_status="pass",
        value=1.2,
        unit="nM",
        conclusion="Recorded binding.",
        failure_reason=None,
        result_metadata={"replicates": 3},
        source_artifact_id=uuid.uuid4(),
    )
    workflow = SimpleNamespace(
        id=workflow_id,
        name="Design route",
        status="draft",
        graph={"nodes": [{}], "edges": []},
    )
    node = SimpleNamespace(
        id=uuid.uuid4(),
        workflow_run_id=workflow_id,
        node_key="design",
        node_type="model",
        model_plugin="demo",
        status="draft",
        error_message=None,
    )
    draft = SimpleNamespace(
        id=uuid.uuid4(),
        name="Draft A",
        backend="lsf",
        status="draft",
        confirmed_job_id=None,
        specification={"queue": "normal"},
    )
    job = SimpleNamespace(
        id=uuid.uuid4(),
        workflow_run_id=workflow_id,
        workflow_node_id=node.id,
        status="running",
        compute_backend="lsf",
        model_plugin="demo",
        attempt_number=1,
        error_code=None,
        error_message=None,
    )
    knowledge = SimpleNamespace(
        id=uuid.uuid4(),
        title="Assay constraints",
        content="Use matched controls.",
        entry_type="curated",
        source={"type": "researcher"},
        tags=["assay"],
        version=2,
    )
    session = FakeSession(
        [
            [target],
            [candidate],
            [result],
            [workflow],
            [node],
            [draft],
            [job],
            [knowledge],
        ]
    )
    context = ProjectContextService(
        cast(Any, session),
        cast(Any, SimpleNamespace(id=project_id)),
    )

    targets = context.list_targets()
    candidates = context.list_candidates()
    results = context.list_experiment_results()
    workflows = context.workflow_status()
    compute = context.compute_status()
    notes = context.search_knowledge("controls")

    assert targets[0]["data"]["uniprot_accession"] == "P12345"
    assert candidates[0]["data"]["rank"] == 1
    assert "token" not in candidates[0]["data"]["properties"]
    assert results[0]["data"]["value"] == 1.2
    assert workflows[0]["data"]["nodes"][0]["node_key"] == "design"
    assert compute["drafts"][0]["data"]["status"] == "draft"
    assert compute["jobs"][0]["data"]["status"] == "running"
    assert notes[0]["data"]["version"] == 2

    citation = context.citation_for_item(results[0])
    assert citation["source_type"] == "project_database"
    assert citation["artifact_id"] == str(result.source_artifact_id)


def test_project_context_redacts_sensitive_key_variants_recursively() -> None:
    sanitized = _sanitize(
        {
            "safe": "visible",
            "access_token": "secret",
            "OPENAI_API_KEY": "secret",
            "credentialRef": "secret",
            "nested": {
                "password_hint": "secret",
                "authorization": "secret",
                "token_count": 42,
            },
        }
    )

    assert sanitized == {
        "safe": "visible",
        "nested": {"token_count": 42},
    }


def test_project_context_bounds_text_and_collection_size() -> None:
    sanitized = _sanitize(
        {
            "content": "x" * (MAX_CONTEXT_TEXT + 1),
            "items": list(range(MAX_CONTEXT_ITEMS + 10)),
        }
    )

    assert sanitized["content"].endswith("[truncated]")
    assert len(sanitized["items"]) == MAX_CONTEXT_ITEMS
