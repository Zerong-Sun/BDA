"""Reimporting a bibliography must not erase or manufacture retrieved evidence."""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from pathlib import Path

import pytest
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.copilot.research_context import ResearchContextService
from backend_v2.app.literature.indexing import extract_europe_pmc_full_text, index_document_content
from backend_v2.app.literature.models import LiteratureDocument, LiteratureRetrievalTrace, LiteratureSearchRun
from backend_v2.app.projects.models import Project
from sqlalchemy import select

pytest_plugins = ["backend_v2.tests.test_v2_domains"]
PACKAGE = Path(__file__).resolve().parents[2] / "frontend/public/research-packages/pd1-demo-v1.json"


def _import(client, ids, package: dict | None = None) -> tuple[uuid.UUID, dict]:
    source = json.loads(PACKAGE.read_text()) if package is None else package
    if package is None:
        descriptor = next(item for item in client.get("/api/v2/research-packages").json()
                          if item["package_id"] == source["package_id"])
        response = client.post("/api/v2/research-package-imports", json={
            "organization_id": str(ids["organization"]), "package_id": descriptor["package_id"],
            "version": descriptor["version"], "checksum": descriptor["checksum"],
        })
    else:
        response = client.post("/api/v2/research-package-imports/legacy-payload", json={
            "organization_id": str(ids["organization"]), "package": source,
        })
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["projects"][0]["project_id"]), source


def _save_retrieved_content(ids, project_id: uuid.UUID, ref_id: str) -> dict:
    """Real persisted trace, artifact and indexed chunks; no external retrieval."""
    with ids["session_factory"]() as session:
        document = session.scalar(select(LiteratureDocument).where(
            LiteratureDocument.project_id == project_id, LiteratureDocument.external_id == ref_id,
        ))
        assert document is not None
        raw = b"<article><body><p>Synthetic test evidence for citation persistence.</p></body></article>"
        checksum = hashlib.sha256(raw).hexdigest()
        artifact = Artifact(
            project_id=project_id, created_by=ids["user"], artifact_type="literature_full_text",
            filename="synthetic-source.xml", content_type="application/xml", object_key=f"test/{uuid.uuid4()}.xml",
            size_bytes=len(raw), checksum_sha256=checksum, status="available", lineage={"synthetic": True},
        )
        search = LiteratureSearchRun(
            project_id=project_id, created_by=ids["user"], query="synthetic citation persistence",
            sources=["europe_pmc"], status="completed", result_count=1,
        )
        session.add_all([artifact, search])
        session.flush()
        trace = LiteratureRetrievalTrace(
            project_id=project_id, search_run_id=search.id, document_id=document.id,
            stage="full_text", source="europe_pmc", request_json={"pmcid": document.metadata_json["pmcid"]},
            response_metadata={"raw_content_artifact_id": str(artifact.id)}, status="completed", http_status=200,
            response_checksum_sha256=checksum, content_checksum_sha256=checksum,
            content_type="application/xml", byte_count=len(raw),
        )
        session.add(trace)
        session.flush()
        paragraphs, extracted = extract_europe_pmc_full_text(raw)
        assert extracted["content_kind"] == "open_access_full_text"
        provenance = {
            "content_kind": extracted["content_kind"], "content_checksum_sha256": checksum,
            "retrieval_trace_id": str(trace.id), "raw_content_artifact_id": str(artifact.id),
            "search_run_id": str(search.id), "database": "europe_pmc", "query": search.query,
            "retrieved_at": "2026-09-30T10:00:00+00:00", "analysis_status": "pending_human_review",
        }
        document.metadata_json = {
            **document.metadata_json, "content_provenance": provenance,
            "latest_retrieval_provenance": {**provenance, "retrieved_at": "2026-09-30T11:00:00+00:00"},
            "search_run_id": str(search.id), "search_query": search.query,
            "verification_status": "verified_crossref", "review_status": "pending_review",
        }
        document.artifact_id = artifact.id
        document.status = "available"
        index_document_content(session, document, paragraphs, content_kind=extracted["content_kind"],
                               content_checksum_sha256=checksum, retrieval_trace_id=str(trace.id))
        session.commit()
        session.expire_all()
        project = session.get(Project, project_id)
        context = ResearchContextService(session, project)
        excerpt = context.get_reference_content(ref_id)[0]
        citation = context.citation_for_item(excerpt)
        saved = {"document_id": document.id, "artifact_id": artifact.id, "metadata": copy.deepcopy(document.metadata_json),
                 "citation": citation, "packet": json.loads(context.grounding_packet([citation])), "version": document.version}
        assert saved["packet"]["items"] and citation["content_checksum_sha256"] == checksum
        return saved


@pytest.mark.parametrize("ref_id", ["R036", "R039"])
def test_pd1_reimport_preserves_retrieved_content_and_verifiable_citations(domain_client, ref_id: str) -> None:
    client, ids = domain_client
    project_id, _ = _import(client, ids)
    saved = _save_retrieved_content(ids, project_id, ref_id)

    assert _import(client, ids)[0] == project_id

    with ids["session_factory"]() as session:
        document = session.get(LiteratureDocument, saved["document_id"])
        assert document is not None
        assert document.metadata_json["content_provenance"] == saved["metadata"]["content_provenance"]
        assert document.metadata_json == saved["metadata"]
        assert document.status == "available" and document.artifact_id == saved["artifact_id"]
        assert document.version == saved["version"]
        context = ResearchContextService(session, session.get(Project, project_id))
        excerpt = context.get_reference_content(ref_id)[0]
        assert context.citation_for_item(excerpt) == saved["citation"]
        assert json.loads(context.grounding_packet([saved["citation"]])) == saved["packet"]
        provenance = excerpt["data"]["content_provenance"]
        trace = session.get(LiteratureRetrievalTrace, uuid.UUID(provenance["retrieval_trace_id"]))
        artifact = session.get(Artifact, saved["artifact_id"])
        assert trace.document_id == document.id and trace.project_id == project_id
        assert trace.content_checksum_sha256 == artifact.checksum_sha256 == provenance["content_checksum_sha256"]


def _spoof_server_metadata(package: dict) -> dict:
    tampered = copy.deepcopy(package)
    reference = next(row for row in tampered["references"] if row["ref_id"] == "R036")
    reference.update({
        "content_provenance": {"content_kind": "open_access_full_text", "content_checksum_sha256": "f" * 64,
                               "retrieval_trace_id": str(uuid.uuid4()), "raw_content_artifact_id": str(uuid.uuid4())},
        "latest_retrieval_provenance": {"retrieval_trace_id": "client-assertion"},
        "search_run_id": str(uuid.uuid4()), "search_query": "unexecuted client search",
        "retrieval_trace_id": str(uuid.uuid4()), "raw_content_artifact_id": str(uuid.uuid4()),
        "raw_response_artifact_id": str(uuid.uuid4()), "content_checksum_sha256": "f" * 64,
        "response_checksum_sha256": "e" * 64, "content_kind": "open_access_full_text",
        "retrieved_at": "2026-09-30T12:00:00+00:00", "analysis_status": "approved",
        "review_status": "approved", "reviewed_by": str(uuid.uuid4()), "reviewed_at": "2026-09-30",
        "patent_legal_status": {"status": "completed"}, "patent_claims": {"status": "completed"},
        "server_verification": "trusted_builtin_checksum",
    })
    return tampered


def test_untrusted_package_cannot_inject_retrieval_or_review_provenance(domain_client) -> None:
    client, ids = domain_client
    package = _spoof_server_metadata(json.loads(PACKAGE.read_text()))

    project_id, _ = _import(client, ids, package)

    with ids["session_factory"]() as session:
        document = session.scalar(select(LiteratureDocument).where(
            LiteratureDocument.project_id == project_id, LiteratureDocument.external_id == "R036",
        ))
        assert document is not None and document.status == "pending_review"
        for key in ("content_provenance", "latest_retrieval_provenance", "retrieval_trace_id", "raw_content_artifact_id",
                    "search_run_id", "search_query", "raw_response_artifact_id", "content_checksum_sha256",
                    "response_checksum_sha256", "content_kind", "retrieved_at", "analysis_status",
                    "review_status", "reviewed_by", "reviewed_at", "patent_legal_status", "patent_claims"):
            assert key not in document.metadata_json
        assert document.metadata_json["server_verification"] == "pending_human_review"
        assert document.metadata_json["verification_status"] == "pending_human_review"
        assert ResearchContextService(session, session.get(Project, project_id)).get_reference_content("R036") == []


def test_untrusted_reimport_cannot_replace_saved_content_snapshot(domain_client) -> None:
    client, ids = domain_client
    project_id, package = _import(client, ids)
    saved = _save_retrieved_content(ids, project_id, "R036")

    assert _import(client, ids, _spoof_server_metadata(package))[0] == project_id

    with ids["session_factory"]() as session:
        document = session.get(LiteratureDocument, saved["document_id"])
        assert document is not None and document.status == "available"
        for key in ("content_provenance", "latest_retrieval_provenance", "search_run_id", "search_query",
                    "verification_status", "review_status"):
            assert document.metadata_json[key] == saved["metadata"][key]
        assert document.metadata_json["server_verification"] == "pending_human_review"
        assert "retrieval_trace_id" not in document.metadata_json
        assert "patent_legal_status" not in document.metadata_json
        context = ResearchContextService(session, session.get(Project, project_id))
        assert context.citation_for_item(context.get_reference_content("R036")[0]) == saved["citation"]
        assert json.loads(context.grounding_packet([saved["citation"]])) == saved["packet"]
