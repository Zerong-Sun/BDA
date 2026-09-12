"""Citations: one interpreter, and an identity the protocol can carry.

The structural test here is `test_chat_and_mcp_cite_a_result_identically`. Chat
stores citations on the message row and MCP puts them on the wire; if those two
ever came from different code they would disagree about the same result and
nothing would fail. They come from `citations.citations_for`, once.

The rest pins the `bda://` URI, which is what turns a citation from a label into
an address a client can come back with.
"""

from __future__ import annotations

from dataclasses import dataclass

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
