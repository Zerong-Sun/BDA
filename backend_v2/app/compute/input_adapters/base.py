"""Input adapter contract."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GeneratedInput:
    """A file the adapter produced, to be staged alongside the bound inputs."""

    port: str
    filename: str
    content: bytes
    content_type: str = "application/json"


@dataclass(frozen=True)
class AdapterContext:
    """Everything an adapter may look at.

    ``read_bytes`` is injected rather than imported so adapters stay unit-testable
    without object storage.
    """

    job_id: uuid.UUID
    project_id: uuid.UUID
    attempt_number: int
    # Resolved manifest inputs: {port, artifact_id, filename, object_key, ...}
    inputs: list[dict]
    parameters: dict
    read_bytes: Callable[[str], bytes]
    job_name: str = ""


@dataclass(frozen=True)
class AdapterResult:
    generated: list[GeneratedInput] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


InputAdapter = Callable[[AdapterContext], AdapterResult]

_REGISTRY: dict[str, InputAdapter] = {}


def register_input_adapter(name: str) -> Callable[[InputAdapter], InputAdapter]:
    def decorator(func: InputAdapter) -> InputAdapter:
        _REGISTRY[name] = func
        return func

    return decorator


def get_input_adapter(name: str | None) -> InputAdapter | None:
    """Resolve an adapter. Returns None when the plugin declares none."""
    return _REGISTRY.get(name) if name else None


def available_input_adapters() -> list[str]:
    return sorted(_REGISTRY)
