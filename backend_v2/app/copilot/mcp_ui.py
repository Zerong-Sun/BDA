"""The residue picker, as an MCP Apps resource.

An external MCP client can already read this project's structures: `analyse`,
`contacts`, `site` and now `render_structure_view` are all `read` tools on the
grant. What it could not do is let the *person* on the other end answer - and
"which residues should this bind?" is a question only they can settle.

MCP Apps (the extension published 2026-01-26) is the standard shape for that: a
server declares a `ui://` resource, a tool points at it through
`_meta.ui.resourceUri`, and the host renders it in a sandboxed iframe that talks
back over postMessage using MCP's own JSON-RPC. Adopting it rather than
inventing a protocol is the whole reason this file is small.

Two boundaries are deliberate and are the reason this is not simply "a viewer in
an iframe":

**The app can propose; it cannot confirm.** The page's submit sends `ui/message`
- a message into the conversation naming the chosen residues. Confirming a
hotspot set is a REST call behind `require_command`, unreachable from any tool
and therefore unreachable from here. A picker that could confirm would hand a
model's UI the one action the whole hotspot table exists to reserve for a
person.

**No script, style or font comes from anywhere else.** The page is inline and
self-contained, so the host's CSP has nothing to allow, and a structure viewer
is deliberately *not* embedded: this picker lists residues the server already
measured. Shipping a 500 KB molecular viewer into a sandboxed frame to re-derive
what `list_structure_contacts` just returned would be slower, heavier and no
more true.
"""

from __future__ import annotations

from typing import Any

#: The scheme MCP Apps reserves for UI resources.
UI_RESOURCE_URI = "ui://bda/structure-picker"

#: The MIME type the extension defines for an app page. The profile parameter is
#: what tells a host this HTML is an MCP app rather than a document to display.
UI_MIME_TYPE = "text/html;profile=mcp-app"

#: Tools whose results this page knows how to render. Declared rather than
#: implied so that pointing a second tool at the picker is a deliberate edit.
UI_TOOLS = ("render_structure_view",)


def tool_meta() -> dict[str, Any]:
    """`_meta` for a tool that renders through the picker.

    `visibility` lists both audiences: the model may call the tool, and the app
    may call it too - which is what lets the page re-render after the person
    changes the chain they are looking at.
    """
    return {
        "ui": {
            "resourceUri": UI_RESOURCE_URI,
            "visibility": ["model", "app"],
        }
    }


def descriptor() -> dict[str, Any]:
    """The entry `resources/list` returns for the picker."""
    return {
        "uri": UI_RESOURCE_URI,
        "name": "Structure residue picker",
        "description": (
            "Pick residues on a rendered structure and send the selection back "
            "into the conversation. Proposing only: confirming a hotspot set is "
            "a signed-in action in BDA."
        ),
        "mimeType": UI_MIME_TYPE,
        "_meta": {
            "ui": {
                # No external origin is needed, so none is allowed. A host that
                # builds its CSP from this declaration ends up with a frame that
                # can reach nothing.
                "csp": {"connect-src": [], "script-src": [], "style-src": []},
                "permissions": [],
                "prefersBorder": True,
            }
        },
    }


#: The page. Inline and dependency-free on purpose - see the module docstring.
#:
#: It listens for the two notifications the host sends (`tool-input` so it can
#: show what was asked before the answer arrives, `tool-result` for the scene)
#: and sends exactly one request back: `ui/message`, carrying the residues the
#: person ticked. Every value it renders comes from the tool result; the page
#: derives no chemistry of its own.
_PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Structure residues</title>
<style>
  :root { color-scheme: light dark; font-family: ui-sans-serif, system-ui, sans-serif; }
  body { margin: 0; padding: 12px; font-size: 13px; }
  h1 { font-size: 14px; margin: 0 0 4px; }
  p.meta { margin: 0 0 10px; opacity: .7; font-family: ui-monospace, monospace; font-size: 11px; }
  ul { list-style: none; margin: 0 0 10px; padding: 0; display: grid; gap: 4px; max-height: 320px; overflow: auto; }
  li { display: flex; align-items: center; gap: 8px; border: 1px solid rgba(128,128,128,.35); border-radius: 6px; padding: 6px 8px; }
  li code { font-family: ui-monospace, monospace; }
  button { font: inherit; padding: 6px 12px; border-radius: 6px; border: 1px solid rgba(128,128,128,.5); background: transparent; cursor: pointer; }
  button[disabled] { opacity: .5; cursor: default; }
  .empty { opacity: .7; }
</style>
<h1 id="title">Structure residues</h1>
<p class="meta" id="meta">Waiting for a structure view…</p>
<ul id="residues"></ul>
<button id="send" disabled>Send selection</button>
<script>
(function () {
  var pending = new Map();
  var nextId = 1;
  var residues = [];

  function call(method, params) {
    var id = nextId++;
    window.parent.postMessage({ jsonrpc: "2.0", id: id, method: method, params: params || {} }, "*");
    return new Promise(function (resolve) { pending.set(id, resolve); });
  }

  function render(result) {
    var content = (result && result.structuredContent) || result || {};
    residues = Array.isArray(content.highlighted) ? content.highlighted : [];
    document.getElementById("title").textContent = content.filename || "Structure residues";
    document.getElementById("meta").textContent = residues.length
      ? (content.format || "structure") + " · " + residues.length + " residue(s) shown"
      : "This view highlights no residues.";
    var list = document.getElementById("residues");
    list.textContent = "";
    if (!residues.length) {
      var empty = document.createElement("li");
      empty.className = "empty";
      empty.textContent = "Nothing to pick: ask for a view with residues in it.";
      list.appendChild(empty);
    }
    residues.forEach(function (residue, index) {
      var row = document.createElement("li");
      var box = document.createElement("input");
      box.type = "checkbox";
      box.id = "r" + index;
      box.addEventListener("change", refresh);
      var label = document.createElement("label");
      label.htmlFor = box.id;
      var code = document.createElement("code");
      code.textContent = String(residue.chain) + String(residue.seq);
      label.appendChild(code);
      if (residue.name) { label.appendChild(document.createTextNode(" " + residue.name)); }
      row.appendChild(box);
      row.appendChild(label);
      list.appendChild(row);
    });
    refresh();
  }

  function chosen() {
    return residues.filter(function (_r, index) {
      var box = document.getElementById("r" + index);
      return box && box.checked;
    });
  }

  function refresh() {
    document.getElementById("send").disabled = chosen().length === 0;
  }

  document.getElementById("send").addEventListener("click", function () {
    var picked = chosen();
    if (!picked.length) return;
    var text = picked.map(function (r) { return String(r.chain) + String(r.seq); }).join(", ");
    // A message, not a write. Confirming a hotspot set is a signed-in action in
    // BDA and is not reachable from this frame. The params shape is the
    // extension's: a role and a content block, not a bare string.
    call("ui/message", {
      role: "user",
      content: { type: "text", text: "Use these residues: " + text }
    });
    document.getElementById("send").disabled = true;
  });

  window.addEventListener("message", function (event) {
    var data = event.data || {};
    if (data.id && pending.has(data.id)) { pending.get(data.id)(data); pending.delete(data.id); return; }
    if (data.method === "ui/notifications/tool-result") { render(data.params); }
    if (data.method === "ui/notifications/tool-input") {
      document.getElementById("meta").textContent = "Rendering the requested view…";
    }
  });
})();
</script>
"""


def contents() -> dict[str, Any]:
    """The `resources/read` payload for the picker."""
    return {"uri": UI_RESOURCE_URI, "mimeType": UI_MIME_TYPE, "text": _PAGE}
