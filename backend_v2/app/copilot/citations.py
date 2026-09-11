"""How a tool result becomes citable evidence, declared once.

`ToolSpec.citation` states the policy at the point a tool is declared; this
module is the one interpreter of it. It used to live inside `research_agent`,
which was fine while chat was the only consumer. MCP is the second, and a second
copy of this logic would be the same mistake `registry.py` was written to end -
the chat answer and the MCP answer would cite the same result differently, and
nothing would fail.

The MCP half is the `bda://` URI. A citation already names an addressable object
(`entity_id`, plus a content checksum for literature), which is exactly what the
project's decision-record rule asks evidence to be; the URI is that identity in a
form the protocol can carry and a client can hold on to and come back with.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, unquote

#: `source_type` on a citation -> the first URI segment. Explicit rather than
#: derived, so a new source has to choose a segment instead of inheriting one.
URI_SOURCES = {
    "research_workspace": "research",
    "project_database": "project",
    "scientific_literature": "literature",
}
URI_SCHEME = "bda"


def citations_for(
    spec: Any,
    result: Any,
    context: Any,
    project_context: Any | None,
) -> list[dict[str, Any]]:
    """Turn a tool result into citations, following the tool's declared policy.

    The policy lives on the ToolSpec rather than in a branch here, so a new tool
    states how it is cited at the point it is declared and cannot be added
    without answering the question.
    """
    policy = getattr(spec, "citation", "none")
    if policy == "none" or result is None:
        return []
    if policy == "project_items" and project_context is not None:
        return [project_context.citation_for_item(item) for item in result]
    if policy == "project_compute" and project_context is not None:
        rows = [*result.get("drafts", []), *result.get("jobs", [])]
        return [project_context.citation_for_item(item) for item in rows]
    if policy == "research_items":
        return [context.citation_for_item(item) for item in result]
    if policy == "research_dataset":
        return [
            context.citation_for_item(
                {
                    "kind": "dataset",
                    "id": str(result.get("id")),
                    "label": str(
                        (result.get("title") or {}).get("default") or result.get("key") or "dataset"
                    ),
                    "data": result,
                }
            )
        ]
    if policy == "research_reference":
        return [
            context.citation_for_item(
                {
                    "kind": "reference",
                    "id": str(result.get("document_id")),
                    "label": str(
                        (result.get("title") or {}).get("default") or result.get("ref_id")
                    ),
                    "data": result,
                }
            )
        ]
    return []


def dedupe(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for citation in citations:
        key = (str(citation.get("workspace_type")), str(citation.get("entity_id")))
        if key not in seen:
            result.append(citation)
            seen.add(key)
    return result


def citation_uri(citation: dict[str, Any]) -> str:
    """`bda://<source>/<kind>/<id>` - stable, and resolvable by `resources/read`.

    The source segment is part of the identity rather than something a resolver
    guesses: a research `finding` and a project `finding` would otherwise collide
    on one URI while being different rows.
    """
    source = URI_SOURCES.get(str(citation.get("source_type")), "project")
    kind = quote(str(citation.get("workspace_type") or "item"), safe="")
    identifier = quote(str(citation.get("entity_id") or ""), safe="")
    return f"{URI_SCHEME}://{source}/{kind}/{identifier}"


def parse_uri(uri: str) -> tuple[str, str, str]:
    """The inverse. Raises ValueError on anything this module did not mint."""
    prefix = f"{URI_SCHEME}://"
    if not uri.startswith(prefix):
        raise ValueError("citation_uri_scheme")
    parts = uri[len(prefix) :].split("/")
    if len(parts) != 3 or not all(parts):
        raise ValueError("citation_uri_shape")
    source, kind, identifier = parts
    if source not in set(URI_SOURCES.values()):
        raise ValueError("citation_uri_source")
    return source, unquote(kind), unquote(identifier)


def resource_link(citation: dict[str, Any]) -> dict[str, Any]:
    """One citation as an MCP `resource_link` content block.

    `description` carries the qualifiers a reader needs to weigh the evidence
    without dereferencing it - the review status and evidence grade the platform
    already refuses to let a claim outrun. A link that says only "finding" would
    make a pending draft and a reviewed result look alike.
    """
    qualifiers = [
        str(value)
        for value in (citation.get("evidence_grade"), citation.get("review_status"))
        if value
    ]
    kind = str(citation.get("workspace_type") or "item")
    description = " · ".join([kind, *qualifiers])
    link: dict[str, Any] = {
        "type": "resource_link",
        "uri": citation_uri(citation),
        "name": str(citation.get("label") or kind),
        "description": description,
        "mimeType": "application/json",
    }
    checksum = citation.get("content_checksum_sha256")
    if checksum:
        # Literature content is addressed by checksum as well as by id, and the
        # checksum is the half that survives the text being re-fetched.
        link["_meta"] = {"contentChecksumSha256": checksum}
    return link
