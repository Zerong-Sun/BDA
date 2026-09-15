from __future__ import annotations

import hashlib

import httpx
import pytest
from backend_v2.app.research.evidence_tools import EvidenceToolService
from backend_v2.app.research.generation import (
    _ensure_research_targets,
    _ensure_review_sections,
    _external_references,
    _validate_draft,
)
from backend_v2.app.research.schemas import ResearchGenerationCreate
from pydantic import ValidationError


def test_controlled_evidence_tools_retry_and_record_checksum() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(200, json={"resultList": {"result": []}})

    tools = EvidenceToolService(client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = tools.search_europe_pmc("binding protein")
    assert result.audit["attempts"] == 2
    assert len(result.audit["response_checksum_sha256"]) == 64
    assert result.audit["query"]["url"].startswith("https://www.ebi.ac.uk/europepmc/")


def test_controlled_evidence_tools_close_only_the_client_they_create(monkeypatch) -> None:
    owned_client = httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200)))
    close_calls = 0
    original_close = owned_client.close

    def close() -> None:
        nonlocal close_calls
        close_calls += 1
        original_close()

    monkeypatch.setattr(owned_client, "close", close)
    monkeypatch.setattr(
        "backend_v2.app.research.evidence_tools.httpx.Client",
        lambda **_kwargs: owned_client,
    )

    tools = EvidenceToolService()
    tools.close()
    tools.close()

    assert close_calls == 1


def test_europe_pmc_search_requests_core_metadata_and_full_text_is_audited() -> None:
    xml = b"<article><body><p>Measured binding evidence.</p></body></article>"
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"resultList": {"result": []}})
        return httpx.Response(200, content=xml, headers={"content-type": "application/xml"})

    tools = EvidenceToolService(client=httpx.Client(transport=httpx.MockTransport(handler)))
    tools.search_europe_pmc("odorant binding protein")
    content = tools.get_europe_pmc_full_text("PMC12345")

    assert requests[0].url.params["resultType"] == "core"
    assert requests[1].url.path.endswith("/PMC12345/fullTextXML")
    assert content.content == xml
    assert content.audit["http_status"] == 200
    assert content.audit["byte_count"] == len(xml)
    assert content.audit["response_checksum_sha256"] == hashlib.sha256(xml).hexdigest()


def test_external_doi_metadata_mismatch_cannot_become_verified() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.ebi.ac.uk":
            return httpx.Response(
                200,
                json={
                        "resultList": {
                            "result": [{
                                "doi": "10.1000/test",
                                "title": "Original evidence title",
                                "authorString": "Evidence A",
                                "pubYear": "2025",
                            }]
                        }
                },
            )
        return httpx.Response(200, json={"message": {"title": ["Unrelated metadata"]}})

    tools = EvidenceToolService(client=httpx.Client(transport=httpx.MockTransport(handler)))
    references, issues = _external_references("Original evidence", tools)
    assert references[0]["verification_status"] == "unverified"
    assert any(issue["kind"] == "metadata_mismatch" for issue in issues)


def test_external_search_rejects_unrelated_conference_abstract_collections() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "resultList": {
                    "result": [{
                        "pmid": "33590571",
                        "title": "Abstracts of the 79th Annual Meeting of the Japanese Cancer Association.",
                        "authorString": "Conference Group",
                        "abstractText": "PD-1 appears in one conference abstract.",
                    }]
                }
            },
        )

    tools = EvidenceToolService(client=httpx.Client(transport=httpx.MockTransport(handler)))
    references, issues = _external_references("PD-1 glycosylation", tools)

    assert references == []
    assert {issue["kind"] for issue in issues} == {"irrelevant_references_rejected"}
    assert issues[0]["detail"].startswith("1 search result")


def test_external_search_applies_evidence_cutoff_to_query() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"resultList": {"result": []}})

    tools = EvidenceToolService(client=httpx.Client(transport=httpx.MockTransport(handler)))
    references, issues = _external_references(
        "PD-1 binder design",
        tools,
        evidence_cutoff="2025-06-30",
    )

    assert references == []
    assert issues == []
    assert "FIRST_PDATE:[1900-01-01 TO 2025-06-30]" in requests[0].url.params["query"]
    assert "PUB_YEAR:[1900 TO 2025]" in requests[0].url.params["query"]


def test_generation_request_rejects_invalid_evidence_cutoff() -> None:
    with pytest.raises(ValidationError):
        ResearchGenerationCreate(topic="PD-1 binder design", evidence_cutoff="not-a-date")


def test_legacy_invalid_evidence_cutoff_is_reported_without_searching() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"resultList": {"result": []}})

    tools = EvidenceToolService(client=httpx.Client(transport=httpx.MockTransport(handler)))
    references, issues = _external_references(
        "PD-1 binder design",
        tools,
        evidence_cutoff="not-a-date",
    )

    assert references == []
    assert requests == []
    assert issues[0]["kind"] == "invalid_evidence_cutoff"


def test_graph_evidence_fills_review_and_target_preview_categories() -> None:
    workspace = {
        "review_sections": [],
        "research_targets": [],
        "graph_nodes": [{
            "id": "PD-1",
            "kind": "protein",
            "label": {"default": "PD-1"},
            "description": {"default": "Programmed cell death protein 1"},
            "reference_ids": [],
        }],
        "graph_edges": [{
            "id": "edge-1",
            "source": "PD-1",
            "target": "PD-L1",
            "predicate": "binds",
            "summary": {"default": "PD-1 binds PD-L1"},
            "reference_ids": ["PMID:18287011"],
            "source_urls": ["https://pubmed.ncbi.nlm.nih.gov/18287011/"],
            "assertion": "established_fact",
            "evidence_grade": "A",
        }],
    }

    sections = _ensure_review_sections(workspace)
    targets = _ensure_research_targets(workspace, limit=10, strata="")

    assert sections[0]["items"][0]["evidence"]["derived_from_graph_edge"] == "edge-1"
    assert targets[0]["name"]["default"] == "PD-1"
    assert targets[0]["reference_ids"] == ["PMID:18287011"]


def test_draft_validation_rejects_unknown_nodes_and_citation_closure() -> None:
    issues, coverage = _validate_draft(
        {
            "references": [],
            "graph_nodes": [{"id": "known", "reference_ids": []}],
            "graph_edges": [
                {
                    "id": "edge-1",
                    "source": "known",
                    "target": "missing",
                    "reference_ids": ["PMID:fake"],
                }
            ],
            "research_targets": [],
            "review_sections": [],
            "structures": [],
        }
    )
    assert {issue["kind"] for issue in issues} == {"unknown_node", "unknown_reference"}
    assert coverage == 0.5


# --- Druggability and trial-landscape sources --------------------------------


def _tools(handler) -> EvidenceToolService:
    return EvidenceToolService(client=httpx.Client(transport=httpx.MockTransport(handler)), max_retries=2)


def test_the_open_targets_query_is_fixed_and_its_body_is_in_the_audit() -> None:
    """For GraphQL the body is the question; an audit with only the URL records nothing."""
    import json as _json

    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(_json.loads(request.content))
        return httpx.Response(200, json={"data": {"target": {"id": "ENSG00000188389"}}})

    tools = _tools(handler)
    result = tools.get_open_targets_druggability("ensg00000188389")

    assert bodies[0]["variables"] == {"ensemblId": "ENSG00000188389"}
    assert bodies[0]["query"] == EvidenceToolService.OPEN_TARGETS_DRUGGABILITY_QUERY
    assert result.audit["query"]["body"] == bodies[0]
    assert result.audit["status"] == "completed"
    assert len(result.audit["response_checksum_sha256"]) == 64


def test_a_graphql_error_is_a_failure_and_is_not_retried() -> None:
    """GraphQL answers 200 with errors; saving that as evidence would record an empty report."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"errors": [{"message": "Cannot query field"}]})

    tools = _tools(handler)
    with pytest.raises(RuntimeError, match="open_targets.druggability_failed"):
        tools.get_open_targets_druggability("ENSG00000188389")

    assert calls == 1
    assert tools.audits[-1]["status"] == "failed"
    assert "graphql_error" in tools.audits[-1]["error"]


def test_a_server_error_on_post_is_retried_then_recorded() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"error": "busy"})

    tools = _tools(handler)
    with pytest.raises(RuntimeError):
        tools.get_open_targets_druggability("ENSG00000188389")

    assert calls == 3
    assert tools.audits[-1]["attempts"] == 3


def test_an_identifier_that_is_not_an_ensembl_gene_is_refused_before_any_call() -> None:
    tools = _tools(lambda request: pytest.fail("no request should be made"))

    with pytest.raises(ValueError, match="invalid_ensembl_gene_identifier"):
        tools.get_open_targets_druggability("ENST00000334409")


def test_trial_counts_are_filtered_server_side_by_phase_and_by_start_year() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"totalCount": 7})

    tools = _tools(handler)
    tools.count_clinical_trials("PD-1", phase="PHASE3")
    tools.count_clinical_trials("PD-1", start_year=2023)

    assert seen[0].url.params["filter.advanced"] == "AREA[Phase]PHASE3"
    assert seen[0].url.params["pageSize"] == "1"
    assert seen[1].url.params["filter.advanced"] == "AREA[StartDate]RANGE[2023-01-01,2023-12-31]"


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"intervention": "PD-1", "phase": "PHASE9"}, "invalid_clinical_trials_phase"),
        ({"intervention": "PD-1", "start_year": 1850}, "invalid_clinical_trials_year"),
        ({"intervention": "   "}, "invalid_clinical_trials_query"),
    ],
)
def test_malformed_trial_count_requests_are_refused(kwargs, error) -> None:
    tools = _tools(lambda request: pytest.fail("no request should be made"))

    with pytest.raises(ValueError, match=error):
        tools.count_clinical_trials(**kwargs)


def test_sponsor_pages_ask_only_for_sponsor_fields_and_validate_the_token() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"studies": [], "nextPageToken": None})

    tools = _tools(handler)
    tools.list_clinical_trial_sponsors("PD-1", page_token="NF0g5JKDlvQ")

    assert seen[0].url.params["fields"] == "NCTId,LeadSponsorName,LeadSponsorClass"
    assert seen[0].url.params["pageToken"] == "NF0g5JKDlvQ"
    with pytest.raises(ValueError, match="invalid_clinical_trials_page_token"):
        tools.list_clinical_trial_sponsors("PD-1", page_token="../../etc")
