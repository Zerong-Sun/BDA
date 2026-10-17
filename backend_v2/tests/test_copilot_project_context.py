from __future__ import annotations

import copy
import json
import uuid
from types import SimpleNamespace
from typing import Any, cast

from backend_v2.app.copilot.project_context import (
    MAX_CONTEXT_ITEMS,
    MAX_CONTEXT_TEXT,
    ProjectContextService,
    _experiment_metadata,
    _sanitize,
)
from backend_v2.app.experiments.api import get_result
from backend_v2.app.identity.models import OrganizationMember, User
from backend_v2.app.projects.models import Project
from backend_v2.app.wetlab import analysis
from backend_v2.tests.test_bli_triplet_provenance import MAPPING, triplets
from backend_v2.tests.test_wetlab_analysis import _artifact, _project
from backend_v2.tests.test_wetlab_analysis import session as session  # noqa: F401
from backend_v2.tests.test_wetlab_analysis import stored as stored  # noqa: F401
from fastapi import Response


class FakeSession:
    def __init__(self, outputs):
        self.outputs = iter(outputs)

    def scalars(self, statement):
        return iter(next(self.outputs))

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))


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
        # The name is a display string; the id is what reaches the registry, and
        # `review_compute_declaration` needs it. A stand-in missing the column
        # would let this read as covered while the real node carried nothing.
        model_plugin_id=uuid.uuid4(),
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


def test_plot_counts_are_exact_before_sanitization_and_only_plot_arrays_are_compacted() -> None:
    counts = {"points": 601, "instrument_fit_points": 511, "analysis_fit_points": 403, "processed_points": 0}
    curve = {
        "label": "sensor1", "conc_nM": 100, "excluded": False, "instrument_fit_r2": 0.98,
        **{key: [[float(i), 0.123] for i in range(count)] for key, count in counts.items()},
    }
    metadata = {
        "params": {"t_assoc": 0, "t_dissoc": 100},
        "summary": {"curves": [curve], "processing": {"excluded_labels": ["sensor2"]},
                    "methods": {"standard": {"kd_nM": 12.3, "interval": [10, 14]}},
                    "quality_control": {"checks": [{"code": "review_required"}]},
                    "source_checksum_sha256": "f" * 64},
        # Neither an unrelated 'points' field nor other numeric lists are plots.
        "results": {"points": [1, 2, 3], "covariance": [[1, 0], [0, 2]]},
    }
    before = copy.deepcopy(metadata)
    row = SimpleNamespace(id=uuid.uuid4(), source_artifact_id=uuid.uuid4(), result_metadata=metadata)
    compact = _experiment_metadata(cast(Any, row))
    compact_curve = compact["summary"]["curves"][0]
    assert compact_curve == {
        "label": "sensor1", "conc_nM": 100, "excluded": False, "instrument_fit_r2": 0.98,
        "plot_point_counts": counts,
    }
    assert _sanitize(compact)["summary"]["curves"][0]["plot_point_counts"] == counts
    for key in ("processing", "methods", "quality_control", "source_checksum_sha256"):
        assert compact["summary"][key] == before["summary"][key]
    assert compact["params"] == before["params"]
    assert compact["results"] == before["results"]
    assert compact["context_plot_data"]["experiment_result_id"] == str(row.id)
    assert compact["context_plot_data"]["source_artifact_id"] == str(row.source_artifact_id)
    assert len(json.dumps(_sanitize(compact))) < len(json.dumps(_sanitize(metadata))) / 2
    assert metadata == before


def test_model_context_keeps_saved_bli_plots_and_raw_source_intact_in_storage_and_api(session, stored):
    project_id, user_id = _project(session)
    project, user = session.get(Project, project_id), session.get(User, user_id)
    user.role = "researcher"
    session.add(OrganizationMember(organization_id=project.organization_id, user_id=user_id, role="researcher"))
    session.flush()
    body = triplets()
    artifact = _artifact(session, project_id, user_id, "synthetic.csv", body)
    stored[artifact.object_key] = body
    row, _ = analysis.analyse_bli(session, project_id, user_id, artifact.id,
                                 sample_mapping=MAPPING, analysis_method="instrument_kobs")
    before = copy.deepcopy(row.result_metadata)
    assert len(before["summary"]["curves"][0]["points"]) > MAX_CONTEXT_ITEMS

    item = ProjectContextService(session, project).list_experiment_results()[0]
    context = item["data"]["metadata"]
    for compact, full in zip(context["summary"]["curves"], before["summary"]["curves"], strict=True):
        assert compact["plot_point_counts"] == {
            key: len(full[key]) for key in ("points", "instrument_fit_points", "analysis_fit_points", "processed_points")
        }
        assert "points" not in compact
    assert context["summary"]["source_checksum_sha256"] == artifact.checksum_sha256
    assert item["data"]["source_artifact_id"] == str(artifact.id)
    assert context["context_plot_data"]["omitted_from_model_context"] is True
    assert "saved plot" in context["context_plot_data"]["note"]
    assert row.result_metadata == before
    session.flush()
    session.expire(row, ["result_metadata"])
    response = get_result(project_id, row.id, Response(), session, user)
    assert response.result_metadata == before
    assert stored[artifact.object_key] == body
