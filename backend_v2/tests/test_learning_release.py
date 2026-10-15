"""Release regression coverage for learning provenance and ingestion boundaries."""

from datetime import UTC, datetime

import pytest
from backend_v2.app.artifacts.models import Artifact
from backend_v2.tests.test_learning import _observation, _post, _setup, _trained
from backend_v2.tests.test_learning import client as client  # noqa: F401
from backend_v2.tests.test_learning_lifecycle import _promote


@pytest.mark.parametrize(
    "reserved",
    [
        {"result_metadata": {"learning": {"assay_id": "unvalidated"}}},
        {"result_metadata": {"learning_withdrawal": {"rationale": "Forged"}}},
        {"batch_key": "learning:closed-batch"},
        {"experiment_type": "learning_assay"},
    ],
)
def test_general_results_cannot_write_learning_owned_fields(client, reserved):
    response = client[0].post(
        f"/api/v2/projects/{client[1]['project']}/experiment-results",
        json={"results": [{"experiment_type": "binding", **reserved}]},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "learning_ingestion_required"


def test_deleted_artifact_cannot_support_learning(client):
    assay, study, results, _, model = _trained(client)
    with client[2].begin() as session:
        artifact = session.get(Artifact, client[1]["artifact"])
        artifact.deleted_at = datetime.now(UTC)
    _post(client, "observations", _observation(client[1], assay, 7), status=404)
    _post(
        client,
        "evidence",
        {
            "study_id": study["id"],
            "kind": "fact",
            "statement": "Deleted source",
            "artifact_ids": [str(client[1]["artifact"])],
        },
        status=404,
    )
    _post(
        client,
        "evidence",
        {
            "study_id": study["id"],
            "kind": "fact",
            "statement": "Result from deleted source",
            "result_ids": [results[0]["id"]],
        },
        status=404,
    )
    _post(
        client,
        f"models/{model['id']}/review",
        {
            "action": "promote",
            "rationale": "Deleted source must block promotion",
        },
        version=model["version"],
        status=409,
    )
    frozen = _post(client, "datasets", {"study_id": study["id"], "result_ids": [r["id"] for r in results]})
    assert frozen["manifest"]["included"] == []
    assert {r["reason"] for r in frozen["manifest"]["excluded"]} == {"source_artifact_unavailable"}


def test_new_dual_assay_decision_rejects_superseded_secondary_contract(client):
    _, study, _, _, primary = _trained(client)
    other_assay, other_study, _, _, secondary = _trained(client)
    primary, secondary = _promote(client, primary), _promote(client, secondary)
    _post(
        client,
        "studies",
        {
            "assay_id": other_assay["id"],
            "research_goal_id": str(client[1]["goal"]),
            "name": "Revised secondary objective",
            "direction": "minimize",
            "batch_budget_cents": 200,
            "supersedes_id": other_study["id"],
        },
    )
    _post(
        client,
        "decisions",
        {
            "study_id": study["id"],
            "model_id": primary["id"],
            "secondary_model_id": secondary["id"],
            "candidates": [{"candidate_id": str(client[1]["candidates"][6]), "cost_cents": 50}],
        },
        status=409,
    )


@pytest.mark.parametrize("algorithm", ["knn", "ridge"])
def test_unrepresentable_training_returns_validation_error(client, algorithm):
    assay, study = _setup(client)
    results = [
        _post(client, "observations", _observation(client[1], assay, i, value=1e308 * (-1 if i % 2 else 1)))
        for i in range(6)
    ]
    dataset = _post(client, "datasets", {"study_id": study["id"], "result_ids": [r["id"] for r in results]})
    _post(client, "models", {"dataset_id": dataset["id"], "algorithm": algorithm}, status=422)


def test_handoff_freezes_exact_sequences_and_assay_instructions(client):
    from backend_v2.app.learning import engine
    from backend_v2.tests.test_learning import _proposal
    from backend_v2.tests.test_learning_lifecycle import _approve, _batch

    assay, study, _, _, model = _trained(client)
    model = _promote(client, model)
    batch = _batch(client, _approve(client, _proposal(client, study, model)))
    manifest = batch["manifest"]
    assert manifest["schema_version"] == 2
    assert manifest["assay"]["method"] == assay["method"]
    assert manifest["assay"]["conditions"] == assay["conditions"]
    assert manifest["assay"]["unit"] == assay["unit"]
    assert manifest["goal"] == study["goal_snapshot"]
    for candidate in manifest["candidates"]:
        assert engine.features(candidate["sequence"])["sequence_sha256"] == candidate["sequence_sha256"]
    assert engine.digest(manifest) == batch["digest"]
