"""The residue picker as an MCP Apps resource.

What is worth pinning here is not that the HTML renders - a test cannot know
that - but the three properties that make shipping a page to somebody else's
host defensible:

* the page reaches nothing. No script, style, font or fetch from another
  origin, so the host's CSP has nothing to allow and the frame can talk only to
  its parent;
* the page cannot confirm anything. Confirming a hotspot set is a REST call
  behind `require_command`; if this page could reach a write, the separation
  between an operator's proposal and a person's decision would exist only in
  the parts of the system nobody is looking at;
* the tool still carries its data. A host that has never heard of MCP Apps must
  get the scene from the tool result, not a pointer to a page it cannot render.
"""

from __future__ import annotations

import re

from backend_v2.app.copilot import mcp, mcp_ui
from backend_v2.app.copilot import tools as _tools  # noqa: F401  (registers the catalogue)
from backend_v2.app.copilot.registry import REGISTRY


def _page() -> str:
    return mcp_ui.contents()["text"]


def test_the_picker_is_listed_so_a_host_can_find_it() -> None:
    listing = mcp.resource_listing()

    assert [entry["uri"] for entry in listing] == [mcp_ui.UI_RESOURCE_URI]
    assert listing[0]["mimeType"] == "text/html;profile=mcp-app"


def test_the_page_is_served_as_html_rather_than_as_encoded_data() -> None:
    contents = mcp_ui.contents()

    assert contents["mimeType"].startswith("text/html")
    assert contents["text"].lstrip().startswith("<!doctype html>")
    assert "payload" not in contents


def test_the_page_loads_nothing_from_anywhere_else() -> None:
    """A self-contained page is what makes an empty CSP declaration honest."""
    page = _page()

    assert not re.search(r"https?://", page)
    assert "<script src" not in page
    assert "<link" not in page
    assert "@import" not in page
    assert "fetch(" not in page


def test_the_page_declares_that_it_needs_no_origins_and_no_permissions() -> None:
    ui = mcp_ui.descriptor()["_meta"]["ui"]

    assert ui["csp"] == {"connect-src": [], "script-src": [], "style-src": []}
    assert ui["permissions"] == []


def test_the_page_can_speak_to_the_conversation_and_cannot_write() -> None:
    """`ui/message` is the only request it sends: propose, never confirm."""
    page = _page()

    assert 'call("ui/message"' in page
    assert "tools/call" not in page
    assert "hotspot-sets" not in page
    assert "confirmations" not in page


def test_the_page_speaks_the_shapes_the_extension_defines() -> None:
    """Pinned against the spec, not against a summary of it.

    `ui/message` takes `{role, content: {type, text}}` and the tool-result
    notification carries the `CallToolResult` as its params. Both were written
    from a paraphrase first and were wrong in a way nothing else here would
    catch: the page would render blank and post a message no host reads.
    """
    page = _page()

    assert 'role: "user"' in page
    assert 'content: { type: "text", text:' in page
    assert 'render(data.params)' in page
    assert "data.params.result" not in page


def test_only_the_rendering_tool_is_linked_to_the_picker() -> None:
    specs = [spec for spec in REGISTRY.all() if spec.id in {"render_structure_view", "analyse_structure"}]

    listing = {entry["name"]: entry for entry in mcp.tool_listing(specs)}

    assert listing["render_structure_view"]["_meta"]["ui"]["resourceUri"] == mcp_ui.UI_RESOURCE_URI
    assert listing["render_structure_view"]["_meta"]["ui"]["visibility"] == ["model", "app"]
    assert "_meta" not in listing["analyse_structure"]


def test_a_host_without_the_extension_still_gets_the_tool_and_its_schema() -> None:
    """`_meta` is additive: the listing is a valid plain MCP tool with it removed."""
    spec = next(item for item in REGISTRY.all() if item.id == "render_structure_view")

    entry = mcp.tool_listing([spec])[0]

    assert entry["name"] == "render_structure_view"
    assert entry["inputSchema"] == spec.parameters
    assert entry["annotations"] == {"readOnlyHint": True}


def test_the_picker_renders_only_what_a_tool_result_carried() -> None:
    """No chemistry of its own: the page reads `highlighted` and nothing else."""
    page = _page()

    assert "structuredContent" in page
    assert "content.highlighted" in page
