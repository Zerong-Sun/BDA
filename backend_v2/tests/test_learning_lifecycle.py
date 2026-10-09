"""Synthetic software acceptance: learning updates, source integrity and two rounds."""

from __future__ import annotations

import csv
import hashlib
import io
import uuid

import pytest
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.campaigns.models import CampaignEvaluation, CampaignRound
from backend_v2.app.learning import engine, validation
from backend_v2.app.learning.models import LearningBatch
from backend_v2.tests.test_learning import _observation, _post, _proposal, _rows, _setup, _trained
from backend_v2.tests.test_learning import client as client  # noqa: F401
from sqlalchemy import select


def _promote(ctx, model, action="promote"):
    return _post(
        ctx,
        f"models/{model['id']}/review",
        {"action": action, "rationale": "Synthetic validation"},
        version=model["version"],
        status=200,
    )


def _approve(ctx, decision):
    return _post(
        ctx,
        f"decisions/{decision['id']}/review",
        {"approve": True, "rationale": "Synthetic round reviewed"},
        version=decision["version"],
        status=200,
    )


def _batch(ctx, decision, status=201):
    return _post(
        ctx,
        "batches",
        {"decision_id": decision["id"], "rationale": "Synthetic handoff"},
        version=decision["version"],
        status=status,
    )


def test_two_round_handoff_result_feedback_and_delivery(client):
    assay, study, initial, dataset, model = _trained(client)
    model = _promote(client, model)
    first = _batch(client, _approve(client, _proposal(client, study, model)))
    assert first["manifest"]["external_submission"] is False
    decision = (
        client[0].get(f"/api/v2/projects/{client[1]['project']}/learning/decisions/{first['decision_id']}").json()
    )
    assert _batch(client, decision)["id"] == first["id"]
    selected = first["manifest"]["candidates"]
    results = []
    for i, c in enumerate(selected):
        index = client[1]["candidates"].index(uuid.UUID(c["candidate_id"]))
        results.append(
            _post(
                client,
                "observations",
                _observation(client[1], assay, index, batch_key=first["manifest"]["batch_key"], value=35 + i * 30),
            )
        )
    receipt = {"result_ids": [r["id"] for r in results], "actual_cost_cents": 275, "note": "Includes repeat costs"}
    _post(
        client, f"batches/{first['id']}/receive", {**receipt, "result_ids": [results[0]["id"]]}, version=1, status=422
    )
    received = _post(client, f"batches/{first['id']}/receive", receipt, version=1, status=200)
    assert received["receipt"]["over_estimate"]
    _post(client, f"batches/{first['id']}/receive", receipt, version=1, status=412)
    _post(client, f"batches/{first['id']}/receive", receipt, version=2, status=409)
    updated = _post(
        client, "datasets", {"study_id": study["id"], "result_ids": [r["id"] for r in [*initial, *results]]}
    )
    assert updated["digest"] != dataset["digest"]
    newer = _promote(client, _post(client, "models", {"dataset_id": updated["id"], "algorithm": "ridge"}))
    second = _batch(client, _approve(client, _proposal(client, study, newer)))
    assert second["campaign_id"] == first["campaign_id"]
    assert second["manifest"]["round_number"] == 2
    failed = []
    for c in second["manifest"]["candidates"]:
        index = client[1]["candidates"].index(uuid.UUID(c["candidate_id"]))
        failed.append(
            _post(
                client,
                "observations",
                _observation(
                    client[1], assay, index, batch_key=second["manifest"]["batch_key"], status="failed", value=None
                ),
            )
        )
    _post(
        client,
        f"batches/{second['id']}/receive",
        {"result_ids": [r["id"] for r in failed], "actual_cost_cents": 100, "note": "All failures counted"},
        version=1,
        status=200,
    )
    response = client[0].get(f"/api/v2/projects/{client[1]['project']}/learning/studies/{study['id']}/delivery")
    assert response.status_code == 200, response.text
    package = response.json()
    assert engine.digest(package["content"]) == package["checksum"]
    assert package["content"]["cost_summary"]["reported_experiment_cents"] == 375
    assert package["content"]["release_evidence"]["completed_batches"] == 2
    assert not package["content"]["release_evidence"]["prospective_benefit_verified"]
    with client[2]() as session:
        assert len(list(session.scalars(select(CampaignEvaluation)))) == len(results) + len(failed)
        assert len(list(session.scalars(select(CampaignRound)))) == 2


def test_new_evidence_stales_approved_handoff_and_withdrawal_keeps_sources(client):
    assay, study, results, _, model = _trained(client)
    model = _promote(client, model)
    approved = _approve(client, _proposal(client, study, model))
    evidence = _post(
        client,
        "evidence",
        {
            "study_id": study["id"],
            "kind": "fact",
            "statement": "Synthetic fixture fact",
            "result_ids": [results[0]["id"]],
        },
    )
    _batch(client, approved, status=409)
    pending = _proposal(client, study, model)
    withdrawn = _post(
        client, f"evidence/{evidence['id']}/withdraw", {"rationale": "Conflicting new evidence"}, version=1, status=200
    )
    assert withdrawn["sources"] == evidence["sources"] and withdrawn["withdrawal"]["rationale"]
    _post(
        client, f"decisions/{pending['id']}/review", {"approve": True, "rationale": "Old state"}, version=1, status=409
    )
    pending = _proposal(client, study, model)
    _post(client, "observations", _observation(client[1], assay, 6))
    _post(
        client,
        f"decisions/{pending['id']}/review",
        {"approve": True, "rationale": "Old observations"},
        version=1,
        status=409,
    )
    _post(client, "evidence", {"study_id": study["id"], "kind": "fact", "statement": "Unsupported fact"}, status=422)


def test_rollback_retires_current_model_and_invalidates_old_proposal(client):
    _, study, _, dataset, old = _trained(client)
    old = _promote(client, old)
    stale = _proposal(client, study, old)
    new = _promote(client, _post(client, "models", {"dataset_id": dataset["id"], "algorithm": "ridge"}))
    old["version"] += 1  # superseded by the second promotion
    rolled_back = _promote(client, old, action="rollback")
    assert rolled_back["status"] == "promoted" and rolled_back["version"] == 4
    current = client[0].get(f"/api/v2/projects/{client[1]['project']}/learning/models/{new['id']}").json()
    assert current["status"] == "retired"
    _post(
        client, f"decisions/{stale['id']}/review", {"approve": True, "rationale": "Stale review"}, version=1, status=409
    )


def test_study_revision_blocks_old_handoff_and_preserves_contract(client):
    _, study, _, _, model = _trained(client)
    approved = _approve(client, _proposal(client, study, _promote(client, model)))
    revised = _post(
        client,
        "studies",
        {
            "assay_id": study["assay_id"],
            "research_goal_id": study["research_goal_id"],
            "name": "Revised budget",
            "direction": "maximize",
            "batch_budget_cents": 1000,
            "supersedes_id": study["id"],
        },
    )
    assert revised["supersedes_id"] == study["id"]
    _batch(client, approved, status=409)
    current = client[0].get(f"/api/v2/projects/{client[1]['project']}/learning/studies/{study['id']}").json()
    assert current["batch_budget_cents"] == 250


def _csv_artifact(ctx, monkeypatch, data):
    with ctx[2]() as session:
        row = session.get(Artifact, ctx[1]["artifact"])
        row.size_bytes = len(data)
        row.checksum_sha256 = hashlib.sha256(data).hexdigest()
        session.commit()
    monkeypatch.setattr("backend_v2.app.learning.imports.ObjectStorage.read_bytes", lambda *_args, **_kwargs: data)


def test_csv_dry_run_atomicity_retry_and_checksum(client, monkeypatch):
    assay, _ = _setup(client)
    values = _observation(client[1], assay)
    values.pop("assay_id")
    values.pop("source_artifact_id")
    values["qc_accepted"] = "true"
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(values))
    writer.writeheader()
    writer.writerow(values)
    data = stream.getvalue().encode()
    _csv_artifact(client, monkeypatch, data)
    payload = {"assay_id": assay["id"], "artifact_id": str(client[1]["artifact"])}
    preview = _post(client, "observations/import", payload, status=200)
    assert preview["row_count"] == 1 and preview["result_ids"] == []
    imported = _post(client, "observations/import", {**payload, "dry_run": False}, status=200)
    retry = _post(client, "observations/import", {**payload, "dry_run": False}, status=200)
    assert retry["result_ids"] == imported["result_ids"]
    monkeypatch.setattr(
        "backend_v2.app.learning.imports.ObjectStorage.read_bytes", lambda *_args, **_kwargs: data + b"\n"
    )
    _post(client, "observations/import", payload, status=409)


@pytest.mark.parametrize("strategy", ["family", "batch"])
def test_grouped_validation_purges_identical_sequences(strategy):
    rows = [{**r, "batch_key": f"b{i // 2}", "family_key": f"f{i // 2}"} for i, r in enumerate(_rows())]
    if strategy == "batch":
        rows.append({**rows[0], "batch_key": "b1"})
    _, result = validation.train(rows, "ridge", strategy)
    for fold in result["folds"]:
        assert set(fold["train_sequences"]).isdisjoint(r["sequence_sha256"] for r in fold["test_predictions"])
    assert result["eligible_for_promotion"]


def test_time_validation_never_trains_on_future_or_repeated_test_sequence():
    rows = [{**r, "observed_at": f"2026-01-{i + 1:02}T00:00:00+00:00"} for i, r in enumerate(_rows())]
    rows.append({**rows[0], "observed_at": "2026-01-07T00:00:00+00:00"})
    _, result = validation.train(rows, "knn", "time")
    fold = result["folds"][0]
    assert rows[0]["sequence_sha256"] not in fold["train_sequences"]
    assert len(fold["test_predictions"]) == 2
    with pytest.raises(ValueError):
        validation.train(_rows(), "knn", "time")


@pytest.mark.parametrize("strategy", ["sequence", "family"])
def test_calibration_is_disjoint_and_labels_never_fit_or_select_the_model(strategy):
    rows = [
        {
            **engine.features("A" * n + "C" * (100 - n)),
            "value": float(n),
            "family_key": f"f{n}",
            "batch_key": "b1",
            "replicate_key": "bio1",
        }
        for n in range(10, 90, 3)
    ]
    parameters, evaluation = validation.train(rows, "ridge", strategy, calibrate=True)
    calibration = evaluation["calibration"]
    held = set(calibration["calibration_sequences"])
    assert len(calibration["calibration_groups"]) == 9
    assert calibration["quantile_rank"] == 9
    assert calibration["half_width"] == max(calibration["group_absolute_errors"])
    assert held.isdisjoint(p["sequence_sha256"] for p in parameters["points"])
    for fold in evaluation["folds"]:
        assert held.isdisjoint(fold["train_sequences"])
        assert held.isdisjoint(p["sequence_sha256"] for p in fold["test_predictions"])
    changed, changed_eval = validation.train(
        [{**r, "value": r["value"] + 1000 if r["sequence_sha256"] in held else r["value"]} for r in rows],
        "ridge",
        strategy,
        calibrate=True,
    )
    assert changed["points"] == parameters["points"] and changed["weights"] == parameters["weights"]
    assert changed_eval["folds"] == evaluation["folds"]
    assert changed_eval["eligible_for_promotion"] == evaluation["eligible_for_promotion"]
    assert changed["interval_half_width"] > parameters["interval_half_width"]
    assert validation.train(list(reversed(rows)), "ridge", strategy, calibrate=True) == (parameters, evaluation)
    held_row = next(r for r in rows if r["sequence_sha256"] in held)
    proposal = engine.propose(
        parameters,
        [{**held_row, "candidate_id": "calibration", "cost_cents": 1}],
        direction="maximize",
        budget=100,
        batch_size=1,
        exploration_fraction=0,
    )
    assert proposal["selected"] == [] and proposal["excluded"][0]["reason"] == "measured_or_duplicate_sequence"
    proposal = engine.propose(
        parameters,
        [
            {**held_row, "candidate_id": "retest", "cost_cents": 1},
            {**engine.features("W" * 100), "candidate_id": "ood", "cost_cents": 1},
        ],
        retest_candidates=["retest"],
        direction="maximize",
        budget=100,
        batch_size=2,
        exploration_fraction=0,
    )
    within = next(r for r in proposal["considered"] if r["candidate_id"] == "retest")
    assert within["nominal_interval"] is not None
    assert within["nominal_interval"][1] - within["nominal_interval"][0] == pytest.approx(
        2 * parameters["interval_half_width"]
    )
    assert next(r for r in proposal["considered"] if r["candidate_id"] == "ood")["nominal_interval"] is None


def test_calibration_requires_independent_groups_and_supported_split():
    with pytest.raises(ValueError, match="20 independent"):
        validation.train(_rows(), "knn", "sequence", calibrate=True)
    with pytest.raises(ValueError, match="exchangeable"):
        validation.train(_rows(), "knn", "batch", calibrate=True)


def test_secondary_assay_evidence_is_portable_and_stale_sources_block_review(client):
    _, study, _, _, primary = _trained(client)
    _, _, second_results, second_dataset, secondary = _trained(client)
    primary, secondary = _promote(client, primary), _promote(client, secondary)
    decision = _post(
        client,
        "decisions",
        {
            "study_id": study["id"],
            "model_id": primary["id"],
            "secondary_model_id": secondary["id"],
            "candidates": [{"candidate_id": str(client[1]["candidates"][6]), "cost_cents": 50}],
        },
    )
    response = client[0].get(f"/api/v2/projects/{client[1]['project']}/learning/decisions/{decision['id']}/export")
    assert response.status_code == 200, response.text
    assert response.json()["content"]["secondary_evidence"]["dataset"]["digest"] == second_dataset["digest"]
    response = client[0].get(f"/api/v2/projects/{client[1]['project']}/learning/studies/{study['id']}/delivery")
    assert response.json()["content"]["secondary_evidence"][0]["model"]["id"] == secondary["id"]
    _post(
        client,
        f"observations/{second_results[0]['id']}/withdraw",
        {"rationale": "Instrument error"},
        version=1,
        status=200,
    )
    _post(
        client,
        f"decisions/{decision['id']}/review",
        {"approve": True, "rationale": "Review stale secondary assay"},
        version=1,
        status=409,
    )


def test_pareto_retests_and_stop_preserve_budget():
    rows = _rows()
    primary, _ = validation.train(rows, "ridge", "sequence")
    secondary, _ = validation.train([{**r, "value": -r["value"]} for r in rows], "ridge", "sequence")
    pool = [
        {**rows[0], "candidate_id": "retest", "cost_cents": 80},
        {**engine.features("A" * 45 + "C" * 55), "candidate_id": "new", "cost_cents": 80},
    ]
    result = engine.propose(
        primary,
        pool,
        direction="maximize",
        budget=100,
        batch_size=2,
        exploration_fraction=0.5,
        retest_candidates=["retest"],
        secondary_parameters=secondary,
    )
    assert result["selected"][0]["selection_reason"] == "retest" and result["estimated_cost_cents"] == 80
    assert all(r["pareto_front"] for r in result["considered"])
    stopped = engine.propose(
        primary,
        pool,
        direction="maximize",
        budget=100,
        batch_size=2,
        exploration_fraction=0.5,
        stop_reason="stop_target_reached",
    )
    assert stopped["action"] == "stop_target_reached" and not stopped["selected"]


def test_receipt_tampering_and_cross_project_records_are_rejected(client):
    _, study, _, _, model = _trained(client)
    batch = _batch(client, _approve(client, _proposal(client, study, _promote(client, model))))
    response = client[0].get(f"/api/v2/projects/{client[1]['other']}/learning/batches/{batch['id']}")
    assert response.status_code == 404
    with client[2]() as session:
        row = session.get(LearningBatch, uuid.UUID(batch["id"]))
        row.manifest = {**row.manifest, "tampered": True}
        session.commit()
    response = client[0].get(f"/api/v2/projects/{client[1]['project']}/learning/studies/{study['id']}/delivery")
    assert response.status_code == 409


def test_withdrawn_measurement_excludes_future_training_and_blocks_old_model(client):
    _, study, results, _, model = _trained(client)
    model = _promote(client, model)
    result = results[0]
    withdrawn = _post(
        client, f"observations/{result['id']}/withdraw", {"rationale": "Instrument fault"}, version=1, status=200
    )
    assert (
        withdrawn["value"] == result["value"]
        and withdrawn["result_metadata"]["learning"] == result["result_metadata"]["learning"]
    )
    frozen = _post(client, "datasets", {"study_id": study["id"], "result_ids": [result["id"]]})
    assert frozen["manifest"]["excluded"][0]["reason"] == "measurement_withdrawn"
    _post(
        client,
        "evidence",
        {"study_id": study["id"], "kind": "fact", "statement": "Invalid source", "result_ids": [results[0]["id"]]},
        status=409,
    )
    _post(
        client,
        "decisions",
        {
            "study_id": study["id"],
            "model_id": model["id"],
            "candidates": [{"candidate_id": str(client[1]["candidates"][-1]), "cost_cents": 1}],
        },
        status=409,
    )
    _post(
        client,
        f"models/{model['id']}/review",
        {"action": "retire", "rationale": "Withdrawn training source"},
        version=model["version"],
        status=200,
    )


def test_measurement_identity_retries_and_conflicting_values(client):
    assay, _ = _setup(client)
    body = _observation(client[1], assay, measurement_key="A01")
    original = _post(client, "observations", body)
    assert _post(client, "observations", body)["id"] == original["id"]
    _post(client, "observations", {**body, "value": 99}, status=409)
    technical = _post(client, "observations", {**body, "measurement_key": "A02"})
    assert technical["id"] != original["id"]


def test_original_preview_measurement_fingerprints_remain_idempotent(client):
    from backend_v2.app.experiments.models import ExperimentResult

    assay, _ = _setup(client)
    body = _observation(client[1], assay)
    body["value"] = float(body["value"])
    original = _post(client, "observations", body)
    with client[2]() as session:
        row = session.get(ExperimentResult, uuid.UUID(original["id"]))
        row.legacy_id = f"learning-observation:{client[1]['project']}:{engine.digest(body)}"
        row.result_metadata = {"learning": body, "assay_version": 1}
        session.commit()
    assert _post(client, "observations", body)["id"] == original["id"]


def test_csv_error_rolls_back_the_entire_file(client, monkeypatch):
    from backend_v2.app.experiments.models import ExperimentResult

    assay, _ = _setup(client)
    body = _observation(client[1], assay)
    body.pop("assay_id")
    body.pop("source_artifact_id")
    body["qc_accepted"] = "true"
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(body))
    writer.writeheader()
    writer.writerow(body)
    writer.writerow({**body, "candidate_id": str(client[1]["foreign"])})
    _csv_artifact(client, monkeypatch, stream.getvalue().encode())
    _post(
        client,
        "observations/import",
        {"assay_id": assay["id"], "artifact_id": str(client[1]["artifact"]), "dry_run": False},
        status=404,
    )
    with client[2]() as session:
        assert not list(session.scalars(select(ExperimentResult)))
