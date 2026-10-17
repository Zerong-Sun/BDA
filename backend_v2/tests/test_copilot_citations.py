"""Citations: one interpreter, and an identity the protocol can carry.

The structural test here is `test_chat_and_mcp_cite_a_result_identically`. Chat
stores citations on the message row and MCP puts them on the wire; if those two
ever came from different code they would disagree about the same result and
nothing would fail. They come from `citations.citations_for`, once.

The rest pins the `bda://` URI, which is what turns a citation from a label into
an address a client can come back with.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot import citations
from backend_v2.app.copilot.project_context import ProjectContextService


@dataclass(frozen=True)
class _Spec:
    citation: str


class _Research:
    """Just the one method `citations_for` reaches for."""

    @staticmethod
    def citation_for_item(item: dict) -> dict:
        return {
            "source_type": "research_workspace",
            "workspace_type": item["kind"],
            "entity_id": item["id"],
            "label": item["label"],
        }


CANDIDATE = {
    "kind": "candidate",
    "id": "11111111-1111-1111-1111-111111111111",
    "label": "Binder 7",
    "data": {"structure_artifact_id": "22222222-2222-2222-2222-222222222222"},
}


def test_chat_and_mcp_cite_a_result_identically() -> None:
    """Both surfaces call this function; there is no second interpretation."""
    spec = _Spec(citation="project_items")
    produced = citations.citations_for(spec, [CANDIDATE], _Research(), ProjectContextService)

    assert produced == [
        {
            "source_type": "project_database",
            "workspace_type": "candidate",
            "entity_id": CANDIDATE["id"],
            "label": "Binder 7",
            "artifact_id": "22222222-2222-2222-2222-222222222222",
        }
    ]


def test_compute_status_cites_both_halves_of_its_result() -> None:
    """`get_compute_status` answers with drafts and jobs; both are evidence."""
    produced = citations.citations_for(
        _Spec(citation="project_compute"),
        {
            "drafts": [{"kind": "compute_draft", "id": "d1", "label": "draft", "data": {}}],
            "jobs": [{"kind": "job", "id": "j1", "label": "job", "data": {}}],
        },
        _Research(),
        ProjectContextService,
    )
    assert [item["entity_id"] for item in produced] == ["d1", "j1"]


def test_a_dataset_cites_itself_as_one_entity() -> None:
    """A slice of rows is one citable thing, not one per row."""
    produced = citations.citations_for(
        _Spec(citation="research_dataset"),
        {"id": "ds-1", "title": {"default": "Binding assay"}, "data": [1, 2, 3]},
        _Research(),
        None,
    )
    assert produced == [
        {
            "source_type": "research_workspace",
            "workspace_type": "dataset",
            "entity_id": "ds-1",
            "label": "Binding assay",
        }
    ]


def test_a_reference_is_cited_by_document_id() -> None:
    """The document id is what survives; `ref_id` is a local label."""
    produced = citations.citations_for(
        _Spec(citation="research_reference"),
        {"document_id": "doc-9", "ref_id": "R3", "title": {}},
        _Research(),
        None,
    )
    assert produced[0]["entity_id"] == "doc-9"
    assert produced[0]["label"] == "R3"


def test_an_unknown_policy_cites_nothing_rather_than_guessing() -> None:
    assert citations.citations_for(_Spec(citation="invented"), [CANDIDATE], _Research(), None) == []


def test_a_tool_that_cites_nothing_cites_nothing() -> None:
    """`none` is a statement about the tool, not a default to fall into."""
    assert citations.citations_for(_Spec(citation="none"), [CANDIDATE], _Research(), None) == []


def test_dedupe_keeps_the_first_of_a_repeated_entity() -> None:
    one = {"workspace_type": "candidate", "entity_id": "a", "label": "first"}
    two = {"workspace_type": "candidate", "entity_id": "a", "label": "second"}
    three = {"workspace_type": "finding", "entity_id": "a", "label": "other kind"}
    assert citations.dedupe([one, two, three]) == [one, three]


def test_dedupe_does_not_merge_distinct_chunks_from_one_full_text_snapshot():
    first = {"entity_id": "paper", "chunk_id": "chunk-a", "content_checksum_sha256": "same-full-text"}
    second = {**first, "chunk_id": "chunk-b"}
    assert citations.dedupe([first, second, first]) == [first, second]


def test_followup_markers_keep_original_source_identity_when_catalogue_changes():
    old = [{"entity_id": "old-a"}, {"entity_id": "old-b"}]
    current = [{"entity_id": "new"}, old[1], old[0]]
    assert citations.rebase_history_markers('A [cite:1], B [cite:2].', old, current) == 'A [cite:3], B [cite:2].'


def test_unresolved_history_marker_cannot_silently_point_at_new_source():
    assert citations.rebase_history_markers('Unknown [cite:1].', [], [{"entity_id": "new"}]) == 'Unknown [unverified prior citation 1].'


# --- The URI ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source_type", "expected"),
    [
        ("research_workspace", "bda://research/finding/abc"),
        ("project_database", "bda://project/finding/abc"),
        ("scientific_literature", "bda://literature/finding/abc"),
    ],
)
def test_the_source_is_part_of_the_identity(source_type: str, expected: str) -> None:
    """A research `finding` and a project `finding` are different rows."""
    uri = citations.citation_uri(
        {"source_type": source_type, "workspace_type": "finding", "entity_id": "abc"}
    )
    assert uri == expected


def test_uri_round_trips_through_parse() -> None:
    citation = {
        "source_type": "research_workspace",
        "workspace_type": "review_finding",
        "entity_id": "id/with/slashes",
    }
    source, kind, identifier = citations.parse_uri(citations.citation_uri(citation))
    assert (source, kind, identifier) == ("research", "review_finding", "id/with/slashes")


@pytest.mark.parametrize(
    "uri",
    [
        "file:///etc/passwd",
        "https://example.com/x",
        "bda://research/finding",
        "bda://nowhere/finding/abc",
        "bda://research//abc",
    ],
)
def test_parse_refuses_anything_this_module_did_not_mint(uri: str) -> None:
    with pytest.raises(ValueError):
        citations.parse_uri(uri)


def test_resource_link_shows_what_weighs_the_evidence() -> None:
    """A link reading only "finding" would make a draft and a reviewed result alike."""
    link = citations.resource_link(
        {
            "source_type": "research_workspace",
            "workspace_type": "finding",
            "entity_id": "abc",
            "label": "Binding improves at pH 6",
            "evidence_grade": "B",
            "review_status": "pending_review",
        }
    )
    assert link["type"] == "resource_link"
    assert link["uri"] == "bda://research/finding/abc"
    assert link["description"] == "finding · B · pending_review"


def test_a_literature_link_carries_its_checksum() -> None:
    """The id can be re-minted; the checksum is what survives a re-fetch."""
    link = citations.resource_link(
        {
            "source_type": "scientific_literature",
            "workspace_type": "literature_excerpt",
            "entity_id": "abc",
            "label": "Excerpt",
            "content_checksum_sha256": "f" * 64,
        }
    )
    assert link["_meta"]["contentChecksumSha256"] == "f" * 64


def test_dedupe_keeps_distinct_origins_and_source_snapshots() -> None:
    first = {"source_type": "research_workspace", "workspace_type": "finding", "entity_id": "same", "content_checksum_sha256": "a"}
    other_origin = {**first, "source_type": "project_database"}
    other_snapshot = {**first, "content_checksum_sha256": "b"}
    assert citations.dedupe([first, first, other_origin, other_snapshot]) == [first, other_origin, other_snapshot]


def test_inline_catalogue_never_claims_every_sentence_is_supported() -> None:
    prompt = citations.inline_citation_instructions([{"entity_id": "one", "label": "Paper"}])
    assert '[cite:1]' in prompt
    assert 'immediately after the supported sentence' in prompt
    assert 'abstracts are not full text' in prompt
    assert 'Do not invent' in prompt
    assert '[cite:2]' not in prompt


def test_literature_citation_keeps_the_evidence_snapshot_and_exact_excerpt() -> None:
    from backend_v2.app.copilot.research_context import ResearchContextService

    citation = ResearchContextService._citation({
        "kind": "literature_evidence", "id": "evidence-one", "label": "Paper",
        "data": {
            "document_id": "doc-one", "chunk_id": "chunk-one", "excerpt": "The original sentence.",
            "source_ref": {"content_kind": "database_abstract", "content_checksum_sha256": "old", "retrieval_trace_id": "old-trace"},
            "content_provenance": {"content_kind": "open_access_full_text", "content_checksum_sha256": "new", "retrieval_trace_id": "new-trace", "raw_content_artifact_id": "new-artifact", "retrieved_at": "2026-09-30"},
        },
    })
    assert citation["content_kind"] == "database_abstract"
    assert citation["content_checksum_sha256"] == "old"
    assert citation["retrieval_trace_id"] == "old-trace"
    assert citation["excerpt"] == "The original sentence."
    assert len(citation["excerpt_checksum_sha256"]) == 64
    assert citation["raw_content_artifact_id"] is None
    assert citation["retrieved_at"] is None


def test_a_bibliography_lookup_does_not_claim_to_have_read_full_text() -> None:
    from backend_v2.app.copilot.research_context import ResearchContextService

    citation = ResearchContextService._citation({
        "kind": "reference", "id": "doc-one", "label": "Paper",
        "data": {"metadata": {"content_provenance": {"content_kind": "open_access_full_text"}}},
    })
    assert citation["content_kind"] == "metadata_only"
    assert citation["excerpt"] == ""


def test_legacy_evidence_without_a_checksum_does_not_inherit_current_snapshot() -> None:
    from backend_v2.app.copilot.research_context import ResearchContextService

    citation = ResearchContextService._citation({
        "kind": "literature_evidence", "id": "old-evidence", "label": "Paper",
        "data": {
            "excerpt": "Original legacy text.", "source_ref": {"chunk_position": 0},
            "content_provenance": {"content_kind": "open_access_full_text", "content_checksum_sha256": "new", "raw_content_artifact_id": "new-artifact"},
        },
    })
    assert citation["content_kind"] is None
    assert citation["content_checksum_sha256"] is None
    assert citation["raw_content_artifact_id"] is None


def test_grounding_packet_refuses_unversioned_or_mismatched_sources() -> None:
    from backend_v2.app.copilot.research_context import ResearchContextService
    from backend_v2.app.literature.models import LiteratureChunk

    project_id, document_id, chunk_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    chunk = SimpleNamespace(id=chunk_id, document_id=document_id, content="Saved text.")
    document = SimpleNamespace(id=document_id, project_id=project_id, title="Paper", metadata_json={
        "content_provenance": {"content_kind": "database_abstract", "content_checksum_sha256": "saved", "retrieval_trace_id": "trace"},
    })
    context = ResearchContextService.__new__(ResearchContextService)
    context.project_id = project_id
    context.session = SimpleNamespace(get=lambda model, _id: chunk if model is LiteratureChunk else document)
    citation = {"source_type": "scientific_literature", "chunk_id": str(chunk_id), "document_id": str(document_id)}
    for checksum in (None, "wrong"):
        packet = json.loads(context.grounding_packet([{**citation, "content_checksum_sha256": checksum}]))
        assert packet["items"] == []
    packet = json.loads(context.grounding_packet([{**citation, "content_checksum_sha256": "saved"}]))
    assert packet["items"][0]["excerpt"] == "Saved text."


def test_grounding_review_preserves_original_markers_after_filtering_and_reordering() -> None:
    from backend_v2.app.copilot.research_context import ResearchContextService
    from backend_v2.app.literature.models import LiteratureChunk

    project_id, document_id = uuid.uuid4(), uuid.uuid4()
    first_id, second_id = uuid.uuid4(), uuid.uuid4()
    chunks = {
        first_id: SimpleNamespace(id=first_id, document_id=document_id, content="First saved excerpt."),
        second_id: SimpleNamespace(id=second_id, document_id=document_id, content="Second saved excerpt."),
    }
    document = SimpleNamespace(id=document_id, project_id=project_id, title="Paper", metadata_json={
        "content_provenance": {"content_kind": "database_abstract", "content_checksum_sha256": "saved", "retrieval_trace_id": "trace"},
    })
    context = ResearchContextService.__new__(ResearchContextService)
    context.project_id = project_id
    context.session = SimpleNamespace(get=lambda model, identity: chunks.get(identity) if model is LiteratureChunk else document)
    source = {"source_type": "scientific_literature", "document_id": str(document_id),
              "content_checksum_sha256": "saved"}
    catalog = [
        {"source_type": "project_database", "entity_id": "project"},
        {**source, "workspace_type": "literature_evidence", "entity_id": "claim-1", "chunk_id": str(first_id)},
        {**source, "workspace_type": "literature_excerpt", "entity_id": str(second_id), "chunk_id": str(second_id)},
        {**source, "workspace_type": "literature_excerpt", "entity_id": str(first_id), "chunk_id": str(first_id)},
        {**source, "workspace_type": "literature_evidence", "entity_id": "old-claim", "chunk_id": str(first_id),
         "content_checksum_sha256": "old"},
    ]

    packet = json.loads(context.grounding_packet(catalog))

    assert [item["chunk_id"] for item in packet["items"]] == [str(second_id), str(first_id)]
    assert packet["items"][0]["citation_markers"] == ["[cite:3]"]
    assert packet["items"][1]["citation_markers"] == ["[cite:2]", "[cite:4]"]
    assert "[cite:1]" not in json.dumps(packet)
    assert "[cite:5]" not in json.dumps(packet)
