from __future__ import annotations

import hashlib
import json
import stat
import uuid
from collections.abc import Generator
from types import SimpleNamespace

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.database import get_session
from backend_v2.app.core.models import Base
from backend_v2.app.identity.deps import current_user
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.intelligence.models import (
    DesignRoute,
    IntelligenceEvidence,
    IntelligenceHotspot,
    IntelligenceReport,
    IntelligenceRun,
)
from backend_v2.app.literature.models import (
    LiteratureChunk,
    LiteratureClaim,
    LiteratureDocument,
    LiteratureEvidence,
    LiteratureRelation,
)
from backend_v2.app.main import app
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.app.targets.models import Target
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def domain_client() -> Generator[tuple[TestClient, dict]]:
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        user = User(username="domain-admin", display_name="Domain Admin", role="admin", enabled=True)
        organization = Organization(name="Domain Org")
        session.add_all([user, organization])
        session.flush()
        session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
        project = Project(
            organization_id=organization.id, owner_id=user.id, name="Domain project", project_type="protein_design"
        )
        session.add(project)
        session.flush()
        session.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
        session.commit()
        ids = {"user": user.id, "organization": organization.id, "project": project.id}
        # Handed out so a test can inspect rows the API does not expose - a Celery
        # task's effects, for instance. Same engine, so it sees what the client wrote.
        ids["session_factory"] = factory

    def session_override() -> Generator[Session]:
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def user_override() -> User:
        with factory() as session:
            return session.get(User, ids["user"])  # type: ignore[return-value]

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[current_user] = user_override
    try:
        yield TestClient(app, raise_server_exceptions=True), ids
    finally:
        app.dependency_overrides.clear()
        drop_all(engine, Base.metadata)
        engine.dispose()


def test_project_target_workflow_candidate_loop(domain_client) -> None:
    client, ids = domain_client
    project_id = str(ids["project"])
    assert client.get("/api/v2/projects").json()["items"][0]["id"] == project_id
    project = client.get(f"/api/v2/projects/{project_id}")
    assert project.headers["etag"] == 'W/"1"'
    assert (
        client.patch(
            f"/api/v2/projects/{project_id}", headers={"If-Match": 'W/"1"'}, json={"status": "active"}
        ).status_code
        == 200
    )

    first = client.post(f"/api/v2/projects/{project_id}/targets", json={"name": "Example protein", "sequence": "MKT"}).json()
    second = client.post(f"/api/v2/projects/{project_id}/targets", json={"name": "PD-L1", "sequence": "QDK"}).json()
    assert len(client.get(f"/api/v2/projects/{project_id}/targets").json()["items"]) == 2
    assert (
        client.put(f"/api/v2/projects/{project_id}/primary-target", json={"target_id": second["id"]}).status_code == 200
    )
    assert client.get(f"/api/v2/projects/{project_id}/primary-target").json()["id"] == second["id"]
    assert (
        client.patch(
            f"/api/v2/targets/{first['id']}", headers={"If-Match": 'W/"1"'}, json={"organism": "plant"}
        ).status_code
        == 200
    )

    workflow_payload = {
        "name": "design",
        "nodes": [{"key": "design", "node_type": "model", "model_plugin": "demo"}],
        "edges": [],
    }
    workflow = client.post(f"/api/v2/projects/{project_id}/workflow-runs", json=workflow_payload).json()
    assert client.get(f"/api/v2/workflow-runs/{workflow['id']}").status_code == 200
    assert client.post(f"/api/v2/workflow-runs/{workflow['id']}/validate").json()["valid"] is True
    workflow_payload["name"] = "design-v2"
    assert (
        client.put(
            f"/api/v2/workflow-runs/{workflow['id']}/graph", headers={"If-Match": 'W/"1"'}, json=workflow_payload
        ).status_code
        == 200
    )

    candidate = client.post(
        f"/api/v2/projects/{project_id}/candidates", json={"candidate_key": "c-1", "name": "candidate", "score": 0.9}
    ).json()
    assert client.get(f"/api/v2/candidates/{candidate['id']}").status_code == 200
    assert (
        client.patch(
            f"/api/v2/candidates/{candidate['id']}", headers={"If-Match": 'W/"1"'}, json={"status": "selected"}
        ).json()["status"]
        == "selected"
    )
    assert client.get(f"/api/v2/projects/{project_id}/result-summary").json()["candidate_count"] == 1
    created_results = client.post(
        f"/api/v2/projects/{project_id}/experiment-results",
        json={
            "results": [
                {
                    "candidate_ref": "c-1",
                    "experiment_type": "BLI_Kd",
                    "pass_status": "pass",
                    "value": 42,
                    "unit": "nM",
                },
                {
                    "candidate_ref": "c-1",
                    "experiment_type": "SEC_monomer",
                    "pass_status": "fail",
                    "value": 61,
                    "unit": "percent",
                },
                {
                    "candidate_ref": "c-1",
                    "experiment_type": "SPR_Kd",
                    "pass_status": "pass",
                    "value": 0.1,
                    "unit": "uM",
                },
            ]
        },
    )
    assert created_results.status_code == 201
    result_summary = client.get(f"/api/v2/projects/{project_id}/result-summary").json()
    assert result_summary["best_result_value"] == 42
    assert result_summary["best_result_unit"] == "nM"
    workspace = client.get(f"/api/v2/projects/{project_id}/research-workspace")
    assert workspace.status_code == 200
    assert workspace.json()["project"]["name"] == {"zh": None, "en": None, "default": "Domain project"}
    assert workspace.json()["review_document"] is None
    assert workspace.json()["review_sections"] == []


def test_research_target_gap_resolution_is_enqueued(domain_client) -> None:
    client, ids = domain_client
    project_id = str(ids["project"])
    candidate = client.post(
        f"/api/v2/projects/{project_id}/candidates",
        json={
            "candidate_key": "C10",
            "name": "GPR65/TDAG8",
            "candidate_kind": "research_target",
            "properties": {"gene": "GPR65", "reference_ids": ["R014"]},
        },
    ).json()
    accepted = client.post(
        f"/api/v2/projects/{project_id}/research-targets/{candidate['id']}/gap-resolutions",
        json={"resolve_references": True, "resolve_structure": True},
    )
    assert accepted.status_code == 202
    assert accepted.json()["research_target_id"] == candidate["id"]
    saved = client.get(f"/api/v2/candidates/{candidate['id']}").json()
    assert saved["properties"]["gap_resolution"]["status"] == "pending"
    rejected = client.post(
        f"/api/v2/projects/{project_id}/research-targets/{candidate['id']}/gap-resolutions",
        json={"resolve_references": False, "resolve_structure": False},
    )
    assert rejected.status_code == 422


def _copilot_research_result() -> dict:
    return {
        "schema_version": "1.0",
        "project": {
            "key": "pain-ion-channel-map",
            "name": "Pain ion-channel evidence map",
            "project_type": "target_research",
            "summary": "A reviewable map of an ion-channel mechanism in chronic pain.",
            "research_question": "Which ion-channel mechanisms have direct evidence in chronic pain?",
            "project_review": "# Project Review\n\nAll generated claims require human review.",
            "methods": "Search PubMed and follow identifier-level citation checks.",
        },
        "primary_target": {
            "name": "Transient receptor potential cation channel V1",
            "gene": "TRPV1",
            "uniprot": "Q8NER1",
            "organism": "Homo sapiens",
        },
        "references": [
            {
                "id": "REF-1",
                "title": "TRPV1 and chronic pain",
                "authors": "Example et al.",
                "journal": "Pain Research",
                "year": 2024,
                "pmid": "12345678",
                "doi": "10.1000/example.1",
                "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
            }
        ],
        "nodes": [
            {
                "id": "TRPV1",
                "kind": "target",
                "label": "TRPV1",
                "description": "Candidate nociceptive ion channel.",
                "reference_ids": ["REF-1"],
            },
            {
                "id": "PAIN",
                "kind": "outcome",
                "label": "Chronic pain",
                "description": "Persistent pain outcome.",
                "reference_ids": ["REF-1"],
            },
        ],
        "edges": [
            {
                "id": "EDGE-1",
                "source": "TRPV1",
                "target": "PAIN",
                "predicate": "modulates",
                "summary": "The cited study links TRPV1 activity with persistent pain phenotypes.",
                "assertion": "evidence_based_inference",
                "evidence_grade": "B",
                "reference_ids": ["REF-1"],
            }
        ],
        "candidates": [
            {
                "id": "C01",
                "name": "TRPV1",
                "summary": "Prioritize for orthogonal validation.",
                "score": 81.5,
                "reference_ids": ["REF-1"],
            }
        ],
    }


def test_copilot_research_json_validates_and_imports_atomically(domain_client) -> None:
    client, ids = domain_client
    result = _copilot_research_result()
    payload = {
        "organization_id": str(ids["organization"]),
        "result": f"```json\n{json.dumps(result)}\n```",
    }

    validation = client.post("/api/v2/copilot-research-imports/validate", json=payload)
    assert validation.status_code == 200
    assert validation.json()["valid"] is True
    assert validation.json()["counts"] == {
        "projects": 1,
        "references": 1,
        "nodes": 2,
        "edges": 1,
        "candidates": 1,
    }

    imported = client.post("/api/v2/copilot-research-imports", json=payload)
    assert imported.status_code == 201
    assert imported.json()["status"] == "created"
    project_id = imported.json()["project_id"]

    project = client.get(f"/api/v2/projects/{project_id}").json()
    assert project["name"] == result["project"]["name"]
    assert project["source_package_id"].startswith("copilot-research:")
    assert project["localized_content"]["copilot_research"]["review_status"] == "pending_review"
    assert client.get(f"/api/v2/projects/{project_id}/primary-target").json()["identity_status"] == "unconfirmed"

    research = client.get(f"/api/v2/projects/{project_id}/research").json()
    assert research["briefs"][0]["status"] == "draft"
    assert research["briefs"][0]["scope"]["evidence_relations"]["edges"][0]["id"] == "EDGE-1"
    assert {finding["finding_type"] for finding in research["findings"]} == {
        "evidence_entity",
        "evidence_statement",
    }
    assert all(finding["evidence"]["review_status"] == "pending_review" for finding in research["findings"])
    documents = client.get(f"/api/v2/projects/{project_id}/literature/documents").json()["items"]
    assert documents[0]["external_id"] == "12345678"
    assert documents[0]["status"] == "pending_review"
    candidates = client.get(
        f"/api/v2/projects/{project_id}/candidates",
        params={"candidate_kind": "research_target"},
    ).json()["items"]
    assert candidates[0]["candidate_key"] == "C01"

    workspace = client.get(f"/api/v2/projects/{project_id}/research-workspace")
    assert workspace.status_code == 200
    assert workspace.json()["project"]["source_package_id"].startswith("copilot-research:")
    assert workspace.json()["review_document"]["content"]["default"].startswith("# Project Review")
    assert len(workspace.json()["graph_edges"]) == 1
    assert workspace.json()["references"][0]["metadata"]["pmid"] == "12345678"

    repeated = client.post("/api/v2/copilot-research-imports", json=payload)
    assert repeated.status_code == 201
    assert repeated.json()["status"] == "unchanged"
    assert repeated.json()["project_id"] == project_id


def test_copilot_research_import_reports_field_and_reference_paths_without_writes(domain_client) -> None:
    client, ids = domain_client
    initial_projects = client.get("/api/v2/projects", params={"limit": 200}).json()["items"]
    initial_research = client.get(f"/api/v2/projects/{ids['project']}/research").json()

    invalid = _copilot_research_result()
    invalid["project"]["unsupported_field"] = "unsupported"
    unsupported = client.post(
        "/api/v2/copilot-research-imports",
        json={"organization_id": str(ids["organization"]), "result": invalid},
    )
    assert unsupported.status_code == 422
    assert client.get("/api/v2/projects", params={"limit": 200}).json()["items"] == initial_projects

    invalid = _copilot_research_result()
    invalid["edges"][0]["reference_ids"] = ["REF-MISSING"]
    invalid["nodes"][0]["kind"] = "unsupported-kind"
    response = client.post(
        "/api/v2/copilot-research-imports",
        json={"organization_id": str(ids["organization"]), "result": invalid},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_copilot_research_result"
    assert response.json()["errors"] == [
        {
            "kind": "schema",
            "path": "$.nodes[0].kind",
            "message": "Input should be 'topic', 'target', 'disease', 'pathway', 'mechanism', 'compound', 'outcome' or 'evidence'",
        }
    ]

    invalid["nodes"][0]["kind"] = "target"
    response = client.post(
        "/api/v2/copilot-research-imports",
        json={"organization_id": str(ids["organization"]), "result": invalid},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_copilot_research_references"
    assert response.json()["errors"] == [
        {
            "kind": "unknown_reference",
            "path": "$.edges[0].reference_ids[0]",
            "message": "Referenced citation is not declared in $.references",
            "reference": "REF-MISSING",
        }
    ]
    assert client.get("/api/v2/projects", params={"limit": 200}).json()["items"] == initial_projects
    assert client.get(f"/api/v2/projects/{ids['project']}/research").json() == initial_research


def test_campaign_research_literature_intelligence(domain_client) -> None:
    client, ids = domain_client
    project_id = str(ids["project"])
    target = client.post(f"/api/v2/projects/{project_id}/targets", json={"name": "Target"}).json()
    campaign = client.post(f"/api/v2/projects/{project_id}/campaigns", json={"name": "Campaign"}).json()
    assert client.get(f"/api/v2/campaigns/{campaign['id']}").status_code == 200
    assert (
        client.patch(
            f"/api/v2/campaigns/{campaign['id']}", headers={"If-Match": 'W/"1"'}, json={"status": "active"}
        ).status_code
        == 200
    )
    round_ = client.post(f"/api/v2/campaigns/{campaign['id']}/rounds", json={"hypothesis": "improve affinity"}).json()
    assert (
        client.post(
            f"/api/v2/campaign-rounds/{round_['id']}/evaluations", json={"metrics": {"score": 1}, "outcome": "pass"}
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/v2/campaign-rounds/{round_['id']}/decisions", json={"decision": "continue", "rationale": "promising"}
        ).status_code
        == 201
    )
    assert client.get(f"/api/v2/campaign-rounds/{round_['id']}/evaluations").status_code == 200

    assert (
        client.post(
            f"/api/v2/projects/{project_id}/knowledge", json={"title": "Fact", "content": "Evidence"}
        ).status_code
        == 201
    )
    assert client.get(f"/api/v2/projects/{project_id}/knowledge").json()["items"]
    brief = client.post(f"/api/v2/projects/{project_id}/research-briefs", json={"title": "Review"})
    assert brief.status_code == 201
    assert (
        client.post(
            f"/api/v2/projects/{project_id}/research-findings", json={"title": "Finding", "content": "Observed"}
        ).status_code
        == 201
    )
    assert len(client.get(f"/api/v2/projects/{project_id}/research").json()["findings"]) == 1
    assert (
        client.post(
            f"/api/v2/projects/{project_id}/literature/ingestions", json={"title": "Paper", "source": "doi"}
        ).status_code
        == 202
    )
    assert (
        client.post(
            f"/api/v2/projects/{project_id}/literature/subscriptions", json={"query": "PD-1 proteins"}
        ).status_code
        == 202
    )
    run = client.post(
        f"/api/v2/projects/{project_id}/intelligence-runs",
        json={"target_id": target["id"], "query": {"topic": "binding"}},
    )
    assert run.status_code == 202
    assert client.get(f"/api/v2/projects/{project_id}/intelligence-runs").json()["items"]


def test_registry_copilot_delivery_compute_draft_and_ligand(domain_client, monkeypatch, tmp_path) -> None:
    client, ids = domain_client
    project_id = str(ids["project"])
    plugin = client.post(
        "/api/v2/registry/model-plugins",
        json={
            "plugin_key": "rf",
            "plugin_version": "1",
            "name": "RF",
            "container_image": "rf:1",
            "command": "run",
        },
    )
    assert plugin.status_code == 201
    plugin_id = plugin.json()["id"]
    assert client.get(f"/api/v2/registry/model-plugins/{plugin_id}/snapshot").status_code == 200
    assert client.get("/api/v2/registry/model-plugins").json()["items"]
    skills = client.get("/api/v2/copilot/skills")
    assert skills.status_code == 200
    assert {item["id"] for item in skills.json()} == {
        "project-read",
        "research-read",
        "result-interpretation",
        "knowledge-authoring",
        "literature-search",
        "target-intelligence",
        "research-gap-repair",
        "wetlab-read",
        "wetlab-authoring",
        "research-trace-authoring",
        "workflow-planning",
        "compute-drafting",
        "agent-orchestration",
    }
    assert {
        item["execution_mode"]
        for item in skills.json()
    } == {"read", "draft", "queue"}
    shared_provider = client.post(
        "/api/v2/registry/llm-providers",
        json={
            "name": "Shared demo provider",
            "provider_type": "openai_compatible",
            "endpoint": "https://demo.invalid/v1",
            "model": "demo-model",
            "credential_ref": "unconfigured/demo",
        },
    )
    assert shared_provider.status_code == 201
    initial_config = client.put(
        f"/api/v2/copilot/projects/{project_id}/config",
        json={
            "llm_provider_id": shared_provider.json()["id"],
            "settings": {},
            "enabled_skills": ["knowledge"],
        },
    )
    assert initial_config.status_code == 200
    assert initial_config.json()["api_key_configured"] is False
    monkeypatch.setattr(
        "backend_v2.app.copilot.service.get_settings",
        lambda: SimpleNamespace(is_production=False, llm_local_secret_dir=str(tmp_path)),
    )
    configured = client.put(
        f"/api/v2/copilot/projects/{project_id}/config",
        headers={"If-Match": 'W/"1"'},
        json={
            "llm_provider_id": shared_provider.json()["id"],
            "settings": {
                "llm_api_base": "https://example.invalid/v1",
                "llm_model": "test-model",
                "llm_api_key": "secret-test-key",
            },
            "enabled_skills": ["knowledge", "literature", "intelligence"],
        },
    )
    assert configured.status_code == 200
    assert configured.json()["llm_provider_id"] != shared_provider.json()["id"]
    assert configured.json()["api_key_configured"] is True
    assert "llm_api_key" not in configured.json()["settings"]
    assert configured.json()["settings"]["api_key_preview"] == "••••-key"
    assert client.put(
        f"/api/v2/copilot/projects/{project_id}/config",
        headers={"If-Match": 'W/"2"'},
        json={
            "llm_provider_id": configured.json()["llm_provider_id"],
            "settings": {},
            "enabled_skills": ["not-a-capability"],
        },
    ).status_code == 422
    secret_path = tmp_path / f"project-{project_id}.key"
    assert secret_path.read_text() == "secret-test-key"
    assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600
    shared_provider_after = client.get(f"/api/v2/registry/llm-providers/{shared_provider.json()['id']}")
    assert shared_provider_after.json()["model"] == "demo-model"
    assert client.post(
        "/api/v2/copilot/chat",
        json={
            "project_id": project_id,
            "message": "Invalid capability",
            "skill": "not-a-capability",
        },
    ).status_code == 422
    assert client.post(
        "/api/v2/copilot/chat",
        json={
            "project_id": project_id,
            "message": "Create a compute draft",
            "skill": "compute-drafting",
        },
    ).status_code == 422
    assert client.post(
        "/api/v2/copilot/chat",
        json={
            "project_id": project_id,
            "message": "Oversized entity context",
            "context": {"selected_entity_ids": ["x" * 101]},
        },
    ).status_code == 422
    chat = client.post(
        "/api/v2/copilot/chat",
        json={
            "project_id": project_id,
            "message": "Summarize evidence",
            "skill": "research-read",
        },
    ).json()
    assert chat["message"]["context"]["_requested_by"] == client.get(
        "/api/v2/auth/me"
    ).json()["id"]
    assert chat["message"]["context"]["skill_hint"] == "research-read"
    assert client.get(f"/api/v2/copilot/conversations/{chat['conversation_id']}/messages").status_code == 200
    follow_up = client.post(
        "/api/v2/copilot/chat",
        json={
            "project_id": project_id,
            "conversation_id": chat["conversation_id"],
            "message": "Now focus on the selected reference",
            "intent": "review_section",
            "context": {
                "route": "/research",
                "research_tab": "references",
                "selected_entity_ids": ["PMID:123"],
                "language": "en",
            },
        },
    )
    assert follow_up.status_code == 202
    assert follow_up.json()["conversation_id"] == chat["conversation_id"]
    messages = client.get(f"/api/v2/copilot/conversations/{chat['conversation_id']}/messages").json()["items"]
    by_content = {item["content"]: item for item in messages}
    assert {"Summarize evidence", "Now focus on the selected reference"} <= set(by_content)
    assert by_content["Now focus on the selected reference"]["context"]["research_tab"] == "references"
    draft = client.post(
        "/api/v2/compute-drafts",
        json={"project_id": project_id, "name": "LSF draft", "backend": "lsf", "specification": {}},
    ).json()
    assert client.post(f"/api/v2/compute-drafts/{draft['id']}/confirm").status_code == 202
    assert client.post(f"/api/v2/projects/{project_id}/delivery-packages", json={"name": "Package"}).status_code == 202
    assert client.get(f"/api/v2/projects/{project_id}/delivery-packages").json()["items"]
    assert any(item["id"] == "thc" for item in client.get("/api/v2/ligands").json())
    assert (
        client.post(
            f"/api/v2/projects/{project_id}/ligand-imports",
            json={"ligand_id": "thc", "source": "pubchem"},
        ).status_code
        == 202
    )


def test_workflow_editor_and_project_aggregates(domain_client) -> None:
    client, ids = domain_client
    project_id = str(ids["project"])
    for suffix in ("overview", "candidate-funnel", "target-readiness", "research-summary"):
        assert client.get(f"/api/v2/projects/{project_id}/{suffix}").status_code == 200

    workflow = client.post(
        f"/api/v2/projects/{project_id}/workflow-runs",
        json={"name": "editable", "nodes": [], "edges": []},
    ).json()
    workflow_id = workflow["id"]
    graph = client.get(f"/api/v2/workflow-runs/{workflow_id}/graph")
    assert graph.headers["etag"] == 'W/"1"' and graph.json()["nodes"] == []
    assert client.get(f"/api/v2/workflow-runs/{workflow_id}/preflight").json()["allowed"] is False

    added = client.post(
        f"/api/v2/workflow-runs/{workflow_id}/nodes",
        headers={"If-Match": 'W/"1"'},
        json={"key": "design", "node_type": "model", "model_plugin": "custom", "command": "run-model"},
    )
    assert added.status_code == 201 and added.headers["etag"] == 'W/"2"'
    node_id = added.json()["id"]
    patched = client.patch(
        f"/api/v2/workflow-runs/{workflow_id}/nodes/{node_id}",
        headers={"If-Match": 'W/"2"'},
        json={"parameters": {"samples": 8}, "position": {"x": 10, "y": 20}},
    )
    assert patched.status_code == 200 and patched.headers["etag"] == 'W/"3"'
    layout = client.patch(
        f"/api/v2/workflow-runs/{workflow_id}/layout",
        headers={"If-Match": 'W/"3"'},
        json={"viewport": {"x": 0, "y": 0, "zoom": 1}, "positions": {"design": {"x": 10, "y": 20}}},
    )
    assert layout.status_code == 200 and layout.headers["etag"] == 'W/"4"'
    preview = client.post(f"/api/v2/workflow-nodes/{node_id}/script-previews", json={"overrides": {"samples": 16}})
    assert preview.status_code == 200 and "run-model" in preview.json()["script"]
    assert len(client.get(f"/api/v2/workflow-runs/{workflow_id}/nodes").json()["items"]) == 1
    deleted = client.delete(f"/api/v2/workflow-runs/{workflow_id}/nodes/{node_id}", headers={"If-Match": 'W/"4"'})
    assert deleted.status_code == 200


def test_advanced_domain_resource_contracts(domain_client) -> None:
    client, ids = domain_client
    project_id = str(ids["project"])
    target = client.post(f"/api/v2/projects/{project_id}/targets", json={"name": "Target"}).json()

    knowledge = client.post(
        f"/api/v2/projects/{project_id}/knowledge", json={"title": "Evidence", "content": "Initial"}
    ).json()
    changed = client.patch(
        f"/api/v2/knowledge/{knowledge['id']}",
        headers={"If-Match": 'W/"1"'},
        json={"content": "Reviewed", "tags": ["validated"]},
    )
    assert changed.status_code == 200 and changed.headers["etag"] == 'W/"2"'

    ingestion = client.post(
        f"/api/v2/projects/{project_id}/literature/ingestions",
        json={"title": "Paper", "source": "manual", "abstract": "Evidence paragraph."},
    )
    assert ingestion.status_code == 202
    document_id = ingestion.json()["id"]
    assert client.get(f"/api/v2/literature/documents/{document_id}").status_code == 200
    assert client.get(f"/api/v2/projects/{project_id}/literature/claims").status_code == 200
    assert client.get(f"/api/v2/projects/{project_id}/literature/relations").status_code == 200
    assert client.post(f"/api/v2/projects/{project_id}/literature/relation-detections").status_code == 202
    search_response = client.post(
        f"/api/v2/projects/{project_id}/literature/searches",
        json={
            "query": "odorant binding protein flavor",
            "sources": ["europe_pmc"],
            "limit": 5,
            "fetch_full_text": True,
            "extract_claims": True,
        },
    )
    assert search_response.status_code == 202
    search_run = search_response.json()
    assert search_run["status"] == "pending"
    assert search_run["sources"] == ["europe_pmc"]
    assert client.get(f"/api/v2/projects/{project_id}/literature/searches").json()["items"]
    search_detail = client.get(f"/api/v2/literature/searches/{search_run['id']}")
    assert search_detail.status_code == 200
    assert search_detail.json()["traces"] == []
    subscription = client.post(
        f"/api/v2/projects/{project_id}/literature/subscriptions",
        json={"query": "protein design", "cadence": "weekly"},
    ).json()
    assert client.get(f"/api/v2/projects/{project_id}/literature/subscriptions").json()["items"]
    subscription_id = subscription["id"]
    assert (
        client.patch(
            f"/api/v2/literature/subscriptions/{subscription_id}",
            headers={"If-Match": 'W/"1"'},
            json={"cadence": "daily", "enabled": False},
        ).status_code
        == 200
    )
    assert client.post(f"/api/v2/literature/subscriptions/{subscription_id}/runs").status_code == 202

    campaign = client.post(f"/api/v2/projects/{project_id}/campaigns", json={"name": "Campaign"}).json()
    round_ = client.post(f"/api/v2/campaigns/{campaign['id']}/rounds", json={"hypothesis": "test"}).json()
    decision = client.post(
        f"/api/v2/campaign-rounds/{round_['id']}/decisions",
        json={"decision": "continue", "rationale": "promising"},
    ).json()
    assert client.get(f"/api/v2/campaign-rounds/{round_['id']}/decisions").json()
    patched = client.patch(
        f"/api/v2/campaign-decisions/{decision['id']}",
        headers={"If-Match": 'W/"1"'},
        json={"rationale": "strong evidence"},
    )
    assert patched.status_code == 200 and patched.headers["etag"] == 'W/"2"'
    reviewed = client.post(
        f"/api/v2/campaign-decisions/{decision['id']}/review",
        headers={"If-Match": 'W/"2"'},
        json={"approve": True},
    )
    assert reviewed.json()["review_status"] == "approved"
    assert client.post(f"/api/v2/campaign-rounds/{round_['id']}/evaluation-runs").status_code == 202

    run = client.post(
        f"/api/v2/projects/{project_id}/intelligence-runs",
        json={"target_id": target["id"], "query": {"topic": "binding"}},
    ).json()
    assert client.get(f"/api/v2/intelligence-runs/{run['id']}").status_code == 200
    assert client.post(f"/api/v2/intelligence-runs/{run['id']}/exports").status_code == 202

    plugin = client.post(
        "/api/v2/registry/model-plugins",
        json={
            "plugin_key": "AlphaFold2",
            "plugin_version": "test",
            "name": "AlphaFold2",
            "container_image": "alphafold2:test",
            "command": "python run.py",
        },
    )
    assert plugin.status_code == 201
    route = client.post(
        "/api/v2/copilot/route-plans", json={"project_id": project_id, "goal": "design a stable binder"}
    )
    assert route.status_code == 200 and route.json()["recommended_route"] == "structure-acquisition"
    assert route.json()["workflow_spec"]["nodes"][0]["model_plugin_id"] == plugin.json()["id"]
    interpretation = client.post(
        "/api/v2/copilot/interpretations", json={"project_id": project_id, "subject": "results"}
    )
    assert interpretation.status_code == 200

    assert client.delete(f"/api/v2/knowledge/{knowledge['id']}", headers={"If-Match": 'W/"2"'}).status_code == 200


def test_registry_validation_and_compute_draft_reads(domain_client) -> None:
    client, ids = domain_client
    project_id = str(ids["project"])
    resources = {}
    for kind, path, data in (
        (
            "model_plugin",
            "model-plugins",
            {
                "plugin_key": "validator",
                "plugin_version": "1",
                "name": "Validator",
                "container_image": "registry/validator:1",
                "command": "validate",
            },
        ),
        ("server", "servers", {"name": "OCI", "server_type": "oci", "endpoint": "https://registry.example"}),
        ("compute_node", "compute-nodes", {"name": "LSF", "backend": "lsf", "queue": "test"}),
    ):
        response = client.post(f"/api/v2/registry/{path}", json=data)
        assert response.status_code == 201
        resources[kind] = response.json()["id"]
    assert client.post(f"/api/v2/registry/model-plugins/{resources['model_plugin']}/validations").status_code == 202
    assert client.post(f"/api/v2/registry/servers/{resources['server']}/connection-tests").status_code == 202
    assert client.post(f"/api/v2/registry/compute-nodes/{resources['compute_node']}/health-checks").status_code == 202
    assert client.get("/api/v2/registry/parameter-catalog").status_code == 200
    assert client.get("/api/v2/registry/script-assets").status_code == 200

    draft = client.post(
        "/api/v2/compute-drafts",
        json={"project_id": project_id, "name": "Remote draft", "backend": "lsf", "specification": {}},
    ).json()
    assert any(
        item["id"] == draft["id"]
        for item in client.get("/api/v2/compute-drafts", params={"project_id": project_id}).json()["items"]
    )
    assert client.get(f"/api/v2/compute-drafts/{draft['id']}").json()["id"] == draft["id"]


def test_typed_registry_resources_etags_and_deactivation(domain_client) -> None:
    client, _ = domain_client
    cases = (
        (
            "servers",
            {"name": "Registry", "server_type": "oci", "endpoint": "https://registry.test"},
            {"data": {"endpoint": "https://registry-v2.test"}},
        ),
        (
            "compute-nodes",
            {"name": "GPU node", "backend": "docker", "labels": {"accelerator": "gpu"}},
            {"data": {"queue": "gpu"}},
        ),
        (
            "model-plugins",
            {
                "plugin_key": "af3",
                "plugin_version": "3",
                "name": "AlphaFold 3",
                "container_image": "models/af3:3",
                "command": "predict",
            },
            {"data": {"command": "predict --json"}},
        ),
        (
            "method-plugins",
            {"plugin_key": "rank", "name": "Rank", "specification": {"method_type": "scoring"}},
            {"data": {"specification": {"method_type": "ranking"}}},
        ),
        (
            "llm-providers",
            {
                "name": "Research LLM",
                "provider_type": "openai-compatible",
                "model": "research-model",
                "credential_ref": "secret://research-llm",
            },
            {"data": {"model": "research-model-v2"}},
        ),
    )
    for path, create_payload, patch_payload in cases:
        created = client.post(f"/api/v2/registry/{path}", json=create_payload)
        assert created.status_code == 201
        assert "credential_ref" not in created.json()
        resource_id = created.json()["id"]
        detail = client.get(f"/api/v2/registry/{path}/{resource_id}")
        assert detail.status_code == 200 and detail.headers["etag"] == 'W/"1"'
        assert client.patch(f"/api/v2/registry/{path}/{resource_id}", json=patch_payload).status_code == 428
        updated = client.patch(
            f"/api/v2/registry/{path}/{resource_id}", headers={"If-Match": 'W/"1"'}, json=patch_payload
        )
        assert updated.status_code == 200 and updated.headers["etag"] == 'W/"2"'
        assert (
            client.patch(
                f"/api/v2/registry/{path}/{resource_id}", headers={"If-Match": 'W/"1"'}, json=patch_payload
            ).status_code
            == 412
        )
        disabled = client.delete(f"/api/v2/registry/{path}/{resource_id}", headers={"If-Match": 'W/"2"'})
        assert disabled.status_code == 200 and disabled.json()["enabled"] is False
        assert client.get(f"/api/v2/registry/{path}", params={"limit": 1}).json()["items"]


def test_literature_and_intelligence_resource_flows(domain_client) -> None:
    client, ids = domain_client
    project_id = ids["project"]
    user_id = ids["user"]
    session_generator = app.dependency_overrides[get_session]()
    session = next(session_generator)
    target = Target(project_id=project_id, name="Evidence target")
    document = LiteratureDocument(
        project_id=project_id, title="Design study", source="pubmed", external_id="PMID:1", status="available"
    )
    session.add_all([target, document])
    session.flush()
    chunk = LiteratureChunk(document_id=document.id, position=0, content="The target is designable.")
    session.add(chunk)
    session.flush()
    first_claim = LiteratureClaim(
        document_id=document.id, chunk_id=chunk.id, claim="The target is designable", confidence="high"
    )
    second_claim = LiteratureClaim(document_id=document.id, chunk_id=chunk.id, claim="Validation is required")
    session.add_all([first_claim, second_claim])
    session.flush()
    literature_evidence = LiteratureEvidence(
        claim_id=first_claim.id, evidence_type="text", content="Reported experimentally", source_ref={"page": 2}
    )
    relation = LiteratureRelation(
        project_id=project_id,
        source_claim_id=first_claim.id,
        target_claim_id=second_claim.id,
        relation_type="supports",
    )
    run = IntelligenceRun(project_id=project_id, target_id=target.id, status="completed", query={}, created_by=user_id)
    session.add_all([literature_evidence, relation, run])
    session.flush()
    report = IntelligenceReport(run_id=run.id, title="Report", summary="Summary", content={})
    intelligence_evidence = IntelligenceEvidence(
        run_id=run.id, evidence_type="literature", citation={}, content="Evidence", confidence=0.7
    )
    hotspot = IntelligenceHotspot(run_id=run.id, label="A:10", residues=["A:10"])
    route = DesignRoute(
        run_id=run.id,
        name="Backbone design",
        workflow_spec={"name": "Intelligence route", "nodes": [], "edges": []},
    )
    session.add_all([report, intelligence_evidence, hotspot, route])
    session.commit()
    seeded = {
        "document": document.id,
        "chunk": chunk.id,
        "claim": first_claim.id,
        "literature_evidence": literature_evidence.id,
        "relation": relation.id,
        "run": run.id,
        "report": report.id,
        "intelligence_evidence": intelligence_evidence.id,
        "hotspot": hotspot.id,
        "route": route.id,
    }
    session_generator.close()

    assert client.get(f"/api/v2/projects/{project_id}/literature/documents").json()["items"]
    assert client.get(f"/api/v2/literature/documents/{seeded['document']}").json()["chunks"]
    assert client.get(f"/api/v2/literature/documents/{seeded['document']}/chunks").json()["items"]
    assert client.get(f"/api/v2/literature/chunks/{seeded['chunk']}").headers["etag"] == 'W/"1"'
    assert client.get(f"/api/v2/projects/{project_id}/literature/claims").json()["items"]
    assert client.get(f"/api/v2/literature/claims/{seeded['claim']}").headers["etag"] == 'W/"1"'
    assert client.get(f"/api/v2/literature/claims/{seeded['claim']}/evidence").json()["items"]
    assert client.get(f"/api/v2/literature/evidence/{seeded['literature_evidence']}").status_code == 200
    assert (
        client.patch(
            f"/api/v2/literature/claims/{seeded['claim']}",
            headers={"If-Match": 'W/"1"'},
            json={"review_status": "accepted"},
        ).status_code
        == 200
    )
    assert client.get(f"/api/v2/projects/{project_id}/literature/relations").json()["items"]
    assert client.get(f"/api/v2/literature/relations/{seeded['relation']}").status_code == 200
    assert (
        client.patch(
            f"/api/v2/literature/relations/{seeded['relation']}",
            headers={"If-Match": 'W/"1"'},
            json={"review_status": "accepted"},
        ).status_code
        == 200
    )
    assert client.post(f"/api/v2/projects/{project_id}/literature/relation-detections").status_code == 202
    subscription = client.post(
        f"/api/v2/projects/{project_id}/literature/subscriptions",
        json={"query": "protein design", "cadence": "weekly"},
    ).json()
    assert client.get(f"/api/v2/projects/{project_id}/literature/subscriptions").json()["items"]
    assert client.get(f"/api/v2/literature/subscriptions/{subscription['id']}").status_code == 200
    assert (
        client.patch(
            f"/api/v2/literature/subscriptions/{subscription['id']}",
            headers={"If-Match": 'W/"1"'},
            json={"cadence": "daily"},
        ).status_code
        == 200
    )
    assert client.post(f"/api/v2/literature/subscriptions/{subscription['id']}/runs").status_code == 202

    assert client.get(f"/api/v2/projects/{project_id}/intelligence-runs").json()["items"]
    detail = client.get(f"/api/v2/intelligence-runs/{seeded['run']}")
    assert detail.status_code == 200 and detail.json()["report"]["id"] == str(seeded["report"])
    for resource, resource_id in (
        ("intelligence-reports", seeded["report"]),
        ("intelligence-evidence", seeded["intelligence_evidence"]),
        ("intelligence-hotspots", seeded["hotspot"]),
        ("design-routes", seeded["route"]),
    ):
        assert client.get(f"/api/v2/{resource}/{resource_id}").headers["etag"] == 'W/"1"'
    assert (
        client.patch(
            f"/api/v2/intelligence-reports/{seeded['report']}",
            headers={"If-Match": 'W/"1"'},
            json={"review_status": "approved", "summary": "Reviewed"},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v2/intelligence-evidence/{seeded['intelligence_evidence']}",
            headers={"If-Match": 'W/"1"'},
            json={"review_status": "accepted", "confidence": 0.9},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v2/intelligence-hotspots/{seeded['hotspot']}",
            headers={"If-Match": 'W/"1"'},
            json={"review_status": "accepted", "rationale": "Validated"},
        ).status_code
        == 200
    )
    assert client.post(f"/api/v2/design-routes/{seeded['route']}/apply").status_code == 201
    assert client.post(f"/api/v2/intelligence-runs/{seeded['run']}/exports").status_code == 202


def test_research_resources_are_cursor_etag_and_audit_safe(domain_client) -> None:
    client, ids = domain_client
    project_id = str(ids["project"])
    brief = client.post(
        f"/api/v2/projects/{project_id}/research-briefs",
        json={"title": "Binding review", "content": "Initial scope", "scope": {"target": "PD1"}},
    ).json()
    finding = client.post(
        f"/api/v2/projects/{project_id}/research-findings",
        json={
            "brief_id": brief["id"],
            "finding_type": "evidence",
            "title": "Interface evidence",
            "content": "Residues support binding",
            "evidence": {"source": "PMID:1"},
        },
    ).json()
    assert client.get(f"/api/v2/projects/{project_id}/research-briefs", params={"limit": 1}).json()["items"]
    assert client.get(f"/api/v2/projects/{project_id}/research-findings", params={"limit": 1}).json()["items"]
    assert client.get(f"/api/v2/research-briefs/{brief['id']}").headers["etag"] == 'W/"1"'
    assert client.get(f"/api/v2/research-findings/{finding['id']}").headers["etag"] == 'W/"1"'
    assert (
        client.patch(
            f"/api/v2/research-briefs/{brief['id']}",
            headers={"If-Match": 'W/"1"'},
            json={"status": "reviewed", "content": "Reviewed scope"},
        ).headers["etag"]
        == 'W/"2"'
    )
    assert (
        client.patch(
            f"/api/v2/research-findings/{finding['id']}",
            headers={"If-Match": 'W/"1"'},
            json={"content": "Reviewed binding evidence"},
        ).headers["etag"]
        == 'W/"2"'
    )
    assert (
        client.patch(
            f"/api/v2/research-findings/{finding['id']}",
            headers={"If-Match": 'W/"1"'},
            json={"content": "stale"},
        ).status_code
        == 412
    )
    assert client.delete(f"/api/v2/research-findings/{finding['id']}", headers={"If-Match": 'W/"2"'}).status_code == 200
    assert client.delete(f"/api/v2/research-briefs/{brief['id']}", headers={"If-Match": 'W/"2"'}).status_code == 200
    assert client.get(f"/api/v2/research-findings/{finding['id']}").status_code == 404
    assert client.get(f"/api/v2/research-briefs/{brief['id']}").status_code == 404


def test_artifact_upload_and_target_structure_contract(domain_client, monkeypatch) -> None:
    client, ids = domain_client
    project_id = str(ids["project"])

    class Storage:
        data = b"ATOM      1  CA  GLY A   1      0.000   0.000   0.000\nEND\n"

        def upload_url(self, key: str) -> str:
            return f"https://minio.test/put/{key}"

        def inspect_and_hash(self, key: str) -> tuple[int, str]:
            return len(self.data), hashlib.sha256(self.data).hexdigest()

        def read_bytes(self, key: str, *, max_bytes: int) -> bytes:
            return self.data

        def promote(self, source: str, target: str) -> None:
            return None

        def remove(self, key: str) -> None:
            return None

        def download_url(self, key: str) -> str:
            return f"https://minio.test/get/{key}"

    monkeypatch.setattr("backend_v2.app.artifacts.service.ObjectStorage", Storage)
    monkeypatch.setattr("backend_v2.app.artifacts.api.ObjectStorage", Storage)
    upload = client.post(
        "/api/v2/artifact-uploads",
        json={
            "project_id": project_id,
            "filename": "target.pdb",
            "artifact_type": "target_structure",
            "content_type": "chemical/x-pdb",
        },
    )
    assert upload.status_code == 201 and upload.json()["upload_url"].startswith("https://minio.test/put/")
    checksum = hashlib.sha256(Storage.data).hexdigest()
    completed = client.post(
        f"/api/v2/artifact-uploads/{upload.json()['id']}/complete",
        json={"checksum_sha256": checksum, "lineage": {"source": "test"}},
    )
    assert completed.status_code == 200
    artifact_id = completed.json()["id"]
    assert completed.json()["download_url"].startswith("https://minio.test/get/")
    assert client.get("/api/v2/artifacts", params={"project_id": project_id}).json()["items"]
    assert client.get(f"/api/v2/artifacts/{artifact_id}").status_code == 200
    assert client.get(f"/api/v2/artifacts/{uuid.uuid4()}").status_code == 404

    target = client.post(f"/api/v2/projects/{project_id}/targets", json={"name": "Structured target"}).json()
    attached = client.put(
        f"/api/v2/targets/{target['id']}/structure-artifact",
        headers={"If-Match": 'W/"1"'},
        json={"artifact_id": artifact_id},
    )
    assert attached.status_code == 200 and attached.json()["structure_status"] == "available"
    imported = client.post(
        f"/api/v2/targets/{target['id']}/structure-imports",
        json={"source": "artifact", "artifact_id": artifact_id},
    )
    assert imported.status_code == 202
    revision = client.post(
        f"/api/v2/targets/{target['id']}/structure-revisions",
        json={"source_artifact_id": artifact_id, "remove_waters": True, "remove_heteroatoms": True},
    )
    assert revision.status_code == 202
    assert client.get(f"/api/v2/targets/{target['id']}/structure-revisions").json()
    not_ready = client.post(
        f"/api/v2/target-structure-revisions/{revision.json()['id']}/review",
        headers={"If-Match": 'W/"1"'},
        json={"approve": True},
    )
    assert not_ready.status_code == 409


def test_project_create_requires_prompt(domain_client) -> None:
    client, ids = domain_client
    missing_prompt = client.post(
        "/api/v2/projects",
        json={
            "organization_id": str(ids["organization"]),
            "name": "No prompt project",
            "project_type": "protein_design",
        },
    )
    assert missing_prompt.status_code == 422

    created = client.post(
        "/api/v2/projects",
        json={
            "organization_id": str(ids["organization"]),
            "name": "Prompted project",
            "project_type": "protein_design",
            "prompt": "Design a high-affinity binder against the stated target.",
        },
    )
    assert created.status_code == 201
    assert created.json()["prompt"] == "Design a high-affinity binder against the stated target."


def test_project_prompt_draft_create_and_get(domain_client) -> None:
    client, ids = domain_client
    accepted = client.post(
        "/api/v2/projects/prompt-drafts",
        json={
            "organization_id": str(ids["organization"]),
            "name": "Draft project",
            "project_type": "protein_design",
            "summary": "Bind the target with high specificity.",
        },
    )
    assert accepted.status_code == 202
    draft_id = accepted.json()["draft_id"]

    fetched = client.get(f"/api/v2/projects/prompt-drafts/{draft_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "pending"
    assert fetched.json()["prompt"] is None

    assert client.get(f"/api/v2/projects/prompt-drafts/{uuid.uuid4()}").status_code == 404
