from __future__ import annotations

import copy
import json
import uuid
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
    descriptors = client.get("/api/v2/research-packages")
    assert descriptors.status_code == 200
    assert len(descriptors.json()) == 1
    descriptor = descriptors.json()[0]
    assert descriptor == {
        "package_id": "pd1-demo-v1",
        "version": "1.0.0",
        "display_name": {**_package()["title"], "default": ""},
        "license": "CC-BY-4.0",
        "checksum": "34b9618a8c5d44148267ae907a91a6eb5c16a2062e2c91e64616ddb64d6a0fdd",
        "size": PACKAGE_PATH.stat().st_size,
        "installed": False,
    }
    payload = {
        "organization_id": str(ids["organization"]),
        "package_id": descriptor["package_id"],
        "version": descriptor["version"],
        "checksum": descriptor["checksum"],
    }

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
    assert client.get("/api/v2/research-packages").json()[0]["installed"] is True

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
    room = client.get(f"/api/v2/copilot/projects/{project['id']}/room").json()
    examples = [item['message'] for item in room['items'] if item.get('message') and item['message']['context'].get('editorial_demo')]
    assert len(examples) == 8
    assert all(m['context']['editorial_demo']['static'] and not m['tool_calls'] and m['bot'] is None for m in examples)


def test_catalog_reimport_preserves_edits_to_installed_editorial_examples(domain_client) -> None:
    from backend_v2.app.copilot.models import CopilotConversation, CopilotMessage
    from sqlalchemy import select

    client, ids = domain_client
    descriptor = client.get('/api/v2/research-packages').json()[0]
    payload = {'organization_id': str(ids['organization']), 'package_id': descriptor['package_id'],
               'version': descriptor['version'], 'checksum': descriptor['checksum']}
    first = client.post('/api/v2/research-package-imports', json=payload)
    assert first.status_code == 201
    project_id = uuid.UUID(first.json()['projects'][0]['project_id'])
    with ids['session_factory']() as session:
        conversation_id = session.scalar(select(CopilotConversation.id).where(CopilotConversation.project_id == project_id))
        message = session.scalar(select(CopilotMessage).where(CopilotMessage.conversation_id == conversation_id).order_by(CopilotMessage.created_at))
        assert message
        message_id = message.id
        message.content = 'An explicitly edited demonstration question.'
        session.commit()
    assert client.post('/api/v2/research-package-imports', json=payload).status_code == 201
    with ids['session_factory']() as session:
        assert session.get(CopilotMessage, message_id).content == 'An explicitly edited demonstration question.'


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
        "/api/v2/research-package-imports/legacy-payload",
        json={"organization_id": str(ids["organization"]), "package": package},
    )

    assert response.status_code == 422
    assert message in response.json()["detail"]
