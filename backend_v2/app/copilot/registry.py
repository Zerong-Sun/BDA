"""One declaration per copilot tool.

A tool used to be described in three places: an OpenAI-style schema in
`research_agent.RESEARCH_TOOLS`, a capability-to-tool mapping in
`capabilities.COPILOT_CAPABILITIES`, and a branch of an `if name == ...` chain
in `research_agent._execute`. Adding one meant editing all three, and nothing
failed if you missed the third - the tool simply became unreachable, or worse,
reachable without its capability check.

Here a tool is one `ToolSpec`. The schema the model sees, the capability that
grants it, whether it reads or writes, and the code that runs are the same
object, so they cannot drift apart. `execute` is the only dispatch point, which
is what makes the capability check and the audit record impossible to skip.

This is what turns the copilot from an assistant that answers into an agent
that acts: adding a capability is adding a row, and the guardrails come with it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..core.problem import DomainError

#: What a tool does to the system. Read tools are always available to a session
#: that has the capability; draft and queue tools additionally require the user
#: to have asked for the action in this turn (see `actions.request_allows`).
ExecutionMode = str  # "read" | "draft" | "queue"


@dataclass(frozen=True)
class ToolContext:
    """Services a handler may use, and the session it runs for.

    Handlers receive this rather than reaching for globals, so a tool can be
    exercised in a test with only the services it actually needs.
    """

    project_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    session: Any = None
    research: Any = None
    project: Any = None
    actions: Any = None
    allowed_kinds: set[str] | None = None
    #: The durable run this tool executes inside, when there is one. Chat turns
    #: leave it unset, which is what makes the suspending tools unreachable from
    #: chat: they declare `requires="agent_run"` and there is nothing to suspend.
    agent_run: Any = None


@dataclass(frozen=True)
class ToolSpec:
    id: str
    description: str
    #: JSON Schema for the arguments, exactly as handed to the model.
    parameters: dict[str, Any]
    #: The capability id that grants this tool. One capability may grant several.
    capability: str
    execution_mode: ExecutionMode
    #: Attribute of `ToolContext` that must be present, or the tool is not
    #: available this turn. Declared rather than checked inside each handler,
    #: which is where the old chain kept forgetting it.
    requires: str
    handler: Callable[[ToolContext, dict[str, Any]], Any]
    #: Write tools record what they did. Reads do not: an audit row per read
    #: would bury the writes that matter.
    audit: bool = False
    #: What this tool leaves running after it returns: "gpu_job", "subagent", or
    #: "" for a tool that answers within the call. A tool that names a kind is
    #: how a run comes to suspend at all - the agent loop reads this rather than
    #: guessing from the result, so the wait is declared with the tool and not
    #: discovered by the caller. Its result carries the id under `resource_id`;
    #: a result without one means the work was already finished and there is
    #: nothing to wait for.
    awaits: str = ""
    #: Bilingual verbs that must appear in the user's own message before a write
    #: runs, so the model cannot talk itself into one.
    request_terms: tuple[str, ...] = field(default_factory=tuple)
    #: How a result turns into citations, declared with the tool rather than
    #: decided by the caller. An answer that cites nothing is not auditable, so
    #: "none" is a statement about the tool (a write, an overview) and not a
    #: default to fall into.
    #:   none               - no citable entities
    #:   project_items      - each returned item, cited through the project service
    #:   project_compute    - drafts and jobs from a compute-status result
    #:   research_items     - each returned item, cited through the research service
    #:   research_dataset   - the returned dataset, cited as one entity
    #:   research_reference - the returned reference, cited as one entity
    citation: str = "none"

    def schema(self) -> dict[str, Any]:
        """The tool as the model sees it."""
        return {
            "type": "function",
            "function": {
                "name": self.id,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> ToolSpec:
        if spec.id in self._specs:
            raise ValueError(f"duplicate copilot tool id: {spec.id}")
        self._specs[spec.id] = spec
        return spec

    def get(self, tool_id: str) -> ToolSpec | None:
        return self._specs.get(tool_id)

    def all(self) -> list[ToolSpec]:
        return sorted(self._specs.values(), key=lambda spec: spec.id)

    def ids(self) -> set[str]:
        return set(self._specs)

    def for_capabilities(self, capabilities: Sequence[str] | set[str]) -> list[ToolSpec]:
        granted = set(capabilities)
        return [spec for spec in self.all() if spec.capability in granted]

    def schemas_for(self, capabilities: Sequence[str] | set[str]) -> list[dict[str, Any]]:
        return [spec.schema() for spec in self.for_capabilities(capabilities)]

    def write_ids(self) -> set[str]:
        return {spec.id for spec in self.all() if spec.execution_mode != "read"}

    def capability_manifest(self) -> dict[str, dict[str, Any]]:
        """Capability -> the tools it grants, derived rather than maintained.

        The old mapping was hand-written beside the registry it described and
        could disagree with it.
        """
        manifest: dict[str, dict[str, Any]] = {}
        for spec in self.all():
            entry = manifest.setdefault(
                spec.capability,
                {"id": spec.capability, "execution_mode": spec.execution_mode, "chat_tools": []},
            )
            entry["chat_tools"].append(spec.id)
            # A capability that grants any write is a write capability.
            if spec.execution_mode != "read":
                entry["execution_mode"] = spec.execution_mode
                entry["requires_explicit_request"] = True
        return manifest

    def execute(
        self,
        tool_id: str,
        context: ToolContext,
        arguments: dict[str, Any],
        *,
        granted: set[str] | None = None,
    ) -> Any:
        """The only way a tool runs.

        Capability, service availability and audit are enforced here, once,
        rather than being repeated (and occasionally omitted) per handler.
        """
        spec = self.get(tool_id)
        if spec is None:
            raise DomainError("copilot_unknown_tool", f"Unknown tool: {tool_id}", status_code=422)
        if granted is not None and spec.capability not in granted:
            raise DomainError(
                "copilot_capability_not_enabled",
                f"{tool_id} requires the {spec.capability} capability.",
                status_code=403,
            )
        if getattr(context, spec.requires, None) is None:
            raise DomainError(
                "copilot_service_not_available",
                f"{tool_id} needs {spec.requires}, which is not enabled for this turn.",
                status_code=409,
            )
        return spec.handler(context, arguments)


#: The process-wide registry. Tools are registered in `tools.py`, which imports
#: the services they call; keeping it out of this module avoids a cycle and
#: leaves this file about the mechanism rather than the catalogue.
REGISTRY = ToolRegistry()
