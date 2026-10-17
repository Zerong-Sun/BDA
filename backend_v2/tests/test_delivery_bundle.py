"""Exports carry actual data and verified bytes, scoped to the selected project."""
from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile
from contextlib import contextmanager

import pytest
from backend_v2.app.artifacts.models import Artifact, ArtifactLineageEdge
from backend_v2.app.candidates.models import Candidate, CandidateMetric
from backend_v2.app.core.problem import DomainError
from backend_v2.app.delivery import tasks
from backend_v2.app.delivery.bundle import assemble_bundle, snapshot_selection
from backend_v2.app.delivery.models import DeliveryPackage
from backend_v2.app.experiments.models import ExperimentResult
from backend_v2.tests.test_room_decision_hotspot_api import client as client
from sqlalchemy import select


class Storage:
    objects: dict[str, bytes] = {}

    def read_bytes(self, key, *, max_bytes):
        data = self.objects[key]
        if len(data) > max_bytes:
            raise ValueError("too_large")
        return data

    def put_bytes(self, key, data, content_type):
        self.objects[key] = data


def data_fixture(ids, *, foreign=False):
    data = b"verified source content"
    project = ids["other_project"] if foreign else ids["project"]
    with ids["factory"]() as session:
        creator = ids["user"]
        artifact = Artifact(project_id=project, created_by=creator, filename="../../structure.pdb", artifact_type="structure",
                            content_type="chemical/x-pdb", object_key=f"test/{uuid.uuid4()}", size_bytes=len(data),
                            checksum_sha256=hashlib.sha256(data).hexdigest())
        session.add(artifact)
        session.flush()
        candidate = Candidate(project_id=project, candidate_key=f"candidate-{uuid.uuid4()}", name="Frozen name", structure_artifact_id=artifact.id,
                              scores={"confidence": 0.9}, properties={"sequence": "ACD"})
        session.add(candidate)
        session.flush()
        result = ExperimentResult(project_id=project, created_by=creator, candidate_id=candidate.id,
                                  experiment_type="binding", value=12, unit="nM", pass_status="unknown", source_artifact_id=artifact.id)
        session.add_all([result, CandidateMetric(candidate_id=candidate.id, metric_key="plddt", value=90, method="fold", evidence_kind="predicted")])
        session.commit()
        Storage.objects[artifact.object_key] = data
        return candidate.id, artifact.id, artifact.object_key


def wire(monkeypatch, ids):
    @contextmanager
    def scope():
        with ids["factory"]() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
    monkeypatch.setattr(tasks, "session_scope", scope)
    monkeypatch.setattr(tasks, "ObjectStorage", Storage)


def test_delivery_contains_selected_frozen_records_actual_files_crate_and_lineage(client, monkeypatch):
    api, ids = client
    candidate, artifact, _ = data_fixture(ids)
    other_candidate, _, _ = data_fixture(ids)
    foreign, _, _ = data_fixture(ids, foreign=True)
    response = api.post(f"/api/v2/projects/{ids['project']}/delivery-packages", json={"name": "Review package", "candidate_ids": [str(candidate)]})
    assert response.status_code == 202, response.text
    record = response.json()["delivery_package"]
    assert "_snapshot" not in record["selection"]
    assert record["selection"]["record_counts"] == {"candidates": 1, "metrics": 1, "experiment_results": 1, "artifacts": 1}
    with ids["factory"]() as session:
        row = session.get(Candidate, candidate)
        row.name = "Edited after queueing"
        session.commit()
    wire(monkeypatch, ids)
    assert tasks.build_delivery_package.run(record["id"])["status"] == "available"
    assert tasks.build_delivery_package.run(record["id"])["status"] == "ignored"
    with ids["factory"]() as session:
        package = session.get(DeliveryPackage, uuid.UUID(record["id"]))
        exported = session.get(Artifact, package.artifact_id)
        archive = zipfile.ZipFile(io.BytesIO(Storage.objects[exported.object_key]))
        assert json.loads(archive.read("candidates.json"))[0]["name"] == "Frozen name"
        assert json.loads(archive.read("candidate-metrics.json"))[0]["evidence_kind"] == "predicted"
        assert json.loads(archive.read("experiment-results.json"))[0]["value"] == 12
        manifest = json.loads(archive.read("manifest.json"))
        assert str(foreign) not in archive.read("candidates.json").decode()
        assert str(other_candidate) not in archive.read("candidates.json").decode()
        for item in manifest["files"]:
            assert ".." not in item["path"].split("/")
            content = archive.read(item["path"])
            assert hashlib.sha256(content).hexdigest() == item["checksum_sha256"]
        crate = json.loads(archive.read("ro-crate-metadata.json"))
        graph = {entity["@id"]: entity for entity in crate["@graph"]}
        assert graph["ro-crate-metadata.json"]["about"] == {"@id": "./"}
        assert graph["./"]["datePublished"] == record["selection"]["frozen_at"]
        assert {part["@id"] for part in graph["./"]["hasPart"]} <= set(archive.namelist())
        assert "redistribution" in graph["./"]["license"]
        edges = list(session.scalars(select(ArtifactLineageEdge).where(ArtifactLineageEdge.child_artifact_id == exported.id)))
        assert len(edges) == 1 and edges[0].parent_artifact_id == artifact


def test_foreign_or_missing_candidates_are_rejected_before_enqueuing(client):
    api, ids = client
    foreign, _, _ = data_fixture(ids, foreign=True)
    for candidate in [foreign, uuid.uuid4()]:
        response = api.post(f"/api/v2/projects/{ids['project']}/delivery-packages", json={"name": "Invalid", "candidate_ids": [str(candidate)]})
        assert response.status_code == 422, response.text
    with ids["factory"]() as session:
        assert not list(session.scalars(select(DeliveryPackage)))


@pytest.mark.parametrize("change", ["corrupt", "deleted", "foreign"])
def test_corrupt_removed_or_foreign_source_cannot_be_exported(client, monkeypatch, change):
    api, ids = client
    candidate, artifact, key = data_fixture(ids)
    response = api.post(f"/api/v2/projects/{ids['project']}/delivery-packages", json={"name": "Invalid source", "candidate_ids": [str(candidate)]})
    package_id = response.json()["delivery_package"]["id"]
    if change == "corrupt":
        Storage.objects[key] = b"x" * len(Storage.objects[key])
    else:
        with ids["factory"]() as session:
            row = session.get(Artifact, artifact)
            if change == "deleted":
                row.status = "deleted"
            else:
                row.project_id = ids["other_project"]
            session.commit()
    wire(monkeypatch, ids)
    with pytest.raises(DomainError):
        tasks.build_delivery_package.run(package_id)
    with ids["factory"]() as session:
        package = session.get(DeliveryPackage, uuid.UUID(package_id))
        assert package.status == "failed" and package.artifact_id is None
        assert not list(session.scalars(select(Artifact).where(Artifact.artifact_type == "delivery_package")))


def test_excluding_measurements_and_size_bounds(client, monkeypatch):
    _, ids = client
    candidate, _, _ = data_fixture(ids)
    with ids["factory"]() as session:
        selection = {"candidate_ids": [str(candidate)], "include_experiment_results": False}
        snapshot = snapshot_selection(session, ids["project"], selection)
        assert snapshot["experiment_results"] == []
        first, _ = assemble_bundle(session, Storage(), uuid.UUID(int=1), "Package", snapshot, selection)
        second, _ = assemble_bundle(session, Storage(), uuid.UUID(int=1), "Package", snapshot, selection)
        assert first == second
        monkeypatch.setattr("backend_v2.app.delivery.bundle.MAX_BYTES", 10)
        with pytest.raises(DomainError, match="smaller|limited"):
            snapshot_selection(session, ids["project"], selection)


def test_newest_listing_paginates_by_time_and_preserves_legacy_id_order(client):
    from datetime import UTC, datetime, timedelta
    api, ids = client
    now = datetime.now(UTC)
    with ids['factory']() as session:
        for identifier, days in [(uuid.UUID(int=1), 0), (uuid.UUID(int=2), -1), (uuid.UUID(int=3), -2)]:
            session.add(DeliveryPackage(id=identifier, project_id=ids['project'], created_by=ids['user'], name=str(days),
                                        created_at=now + timedelta(days=days), selection={}))
        session.commit()
    path = f"/api/v2/projects/{ids['project']}/delivery-packages"
    first = api.get(path, params={'order': 'newest', 'limit': 1}).json()
    assert first['items'][0]['name'] == '0'
    second = api.get(path, params={'order': 'newest', 'limit': 1, 'cursor': first['next_cursor']}).json()
    assert second['items'][0]['name'] == '-1'
    assert api.get(path, params={'order': 'newest', 'cursor': 'invalid'}).status_code == 422
    assert len(api.get(path).json()['items']) == 3
