from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

pytest_plugins = ["backend_v2.tests.test_v2_domains"]

PACKAGE_PATH = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "public"
    / "research-packages"
    / "pd1-demo-v1.json"
)


def _package() -> dict:
    return json.loads(PACKAGE_PATH.read_text())


def test_pd1_demo_import_is_idempotent_and_evidence_closed(domain_client) -> None:
    client, ids = domain_client
    package = _package()
    payload = {"organization_id": str(ids["organization"]), "package": package}

    first = client.post("/api/v2/research-package-imports", json=payload)
    assert first.status_code == 201
    assert first.json()["counts"] == {
        "projects": 1,
        "candidates": 0,
        "findings": 4,
        "references": 12,
        "reference_links": 12,
        "knowledge": 8,
        "structures": 4,
    }
    assert len(first.json()["pdb_operation_ids"]) == 4
    assert first.json()["projects"][0]["source_project_key"] == "PD1"
    assert first.json()["projects"][0]["status"] == "created"

    second = client.post("/api/v2/research-package-imports", json=payload)
    assert second.status_code == 201
    assert second.json()["counts"] == first.json()["counts"]
    assert second.json()["pdb_operation_ids"] == []
    assert second.json()["projects"][0]["status"] == "unchanged"

    projects = [
        item
        for item in client.get("/api/v2/projects", params={"limit": 200}).json()["items"]
        if item["source_package_id"] == "pd1-demo-v1"
    ]
    assert len(projects) == 1
    project = projects[0]
    assert project["source_project_key"] == "PD1"
    assert project["localized_content"]["package"]["schema_version"] == "1.1"

    workspace = client.get(f"/api/v2/projects/{project['id']}/research-workspace").json()
    assert workspace["counts"] == {
        **workspace["counts"],
        "research_targets": 0,
        "references": 12,
        "graph_edges": 4,
    }
    reference_ids = {item["ref_id"] for item in workspace["references"]}
    assert all(set(edge["reference_ids"]) <= reference_ids for edge in workspace["graph_edges"])
    assert all(item["reference_id"] in reference_ids for item in workspace["structures"])
    assert "## 参考文献" in workspace["review_document"]["content"]["zh"]
    assert "## References" in workspace["review_document"]["content"]["en"]

    operations = [
        client.get(f"/api/v2/operations/{operation_id}").json()
        for operation_id in first.json()["pdb_operation_ids"]
    ]
    assert sum(bool(operation["progress"]["attach_to_target"]) for operation in operations) == 1


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda package: package["references"][0].update(project_ids=[]), "project_ids"),
        (
            lambda package: package["projects"][0]["structures"][0].update(reference_id="R999"),
            "references R999",
        ),
        (
            lambda package: package["projects"][0]["project_review"].update(
                zh=package["projects"][0]["project_review"]["zh"].replace("R036.", "R036:", 1)
            ),
            "bibliography must list each visible reference exactly once",
        ),
        (lambda package: package["projects"][0].update(primary_target=None), "primary_target"),
        (lambda package: package.update(schema_version=""), "Unsupported"),
    ],
)
def test_pd1_demo_import_rejects_open_or_invalid_evidence_sets(domain_client, mutate, message) -> None:
    client, ids = domain_client
    package = copy.deepcopy(_package())
    mutate(package)

    response = client.post(
        "/api/v2/research-package-imports",
        json={"organization_id": str(ids["organization"]), "package": package},
    )

    assert response.status_code == 422
    assert message in response.json()["detail"]
