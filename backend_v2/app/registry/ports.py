"""Declarative I/O port contract for model plugins.

A plugin declares what it consumes (``input_ports``) and produces (``output_ports``).
This is what makes workflow edges type-checkable and lets the scheduler wire an
upstream node's outputs into a downstream node's inputs without a bespoke wrapper.

Compatibility is decided by ``kind`` (semantic type) and ``accepts`` (artifact_type
allowlist). ``content_types`` is deliberately advisory only: real uploads in this
deployment carry browser-sniffed types such as ``application/vnd.palm`` for ``.pdb``
files, so gating on content type would reject valid scientific data.
"""

from __future__ import annotations

from fnmatch import fnmatch

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# Semantic types a port can carry. Extend this list when adding a plugin whose data
# does not fit an existing kind; the value is what makes two ports connectable.
PORT_KINDS = frozenset(
    {
        "protein_structure",
        "protein_sequence",
        "nucleotide_sequence",
        "ligand",
        "msa",
        "tabular",
        "params",
        "archive",
        "opaque",
    }
)


class InputPort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(min_length=1, max_length=80)
    accepts: list[str] = Field(default_factory=list)
    content_types: list[str] = Field(default_factory=list)
    required: bool = False
    multiple: bool = False
    description: str = ""
    # Ports sharing a group are alternatives: at most one may be bound, and if any
    # member is required then exactly one must be. Models frequently accept the same
    # data through more than one route (ProteinMPNN takes either a single PDB or a
    # parsed JSONL), which a per-port `required` flag cannot express.
    exclusive_group: str | None = Field(default=None, max_length=120)


class OutputPort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(min_length=1, max_length=80)
    artifact_type: str = Field(min_length=1, max_length=80)
    filename_glob: str = "*"
    description: str = ""


def parse_input_ports(raw: object) -> list[InputPort]:
    return [InputPort.model_validate(item) for item in _as_list(raw)]


def parse_output_ports(raw: object) -> list[OutputPort]:
    return [OutputPort.model_validate(item) for item in _as_list(raw)]


def _as_list(raw: object) -> list:
    return raw if isinstance(raw, list) else []


def port_definition_errors(input_ports: object, output_ports: object) -> list[str]:
    """Structural problems in a plugin's port declaration, for registry validation."""
    errors: list[str] = []
    for label, raw, parser in (
        ("input_ports", input_ports, parse_input_ports),
        ("output_ports", output_ports, parse_output_ports),
    ):
        if raw and not isinstance(raw, list):
            errors.append(f"{label}_must_be_array")
            continue
        try:
            ports = parser(raw)
        except ValidationError as exc:
            errors.extend(f"{label}_invalid:{item['loc'][-1]}:{item['type']}" for item in exc.errors())
            continue
        names = [port.name for port in ports]
        if len(names) != len(set(names)):
            errors.append(f"{label}_names_must_be_unique")
        errors.extend(f"{label}_unknown_kind:{port.kind}" for port in ports if port.kind not in PORT_KINDS)
    return errors


def ports_compatible(source: OutputPort, target: InputPort) -> bool:
    """Whether ``source``'s output can feed ``target``'s input."""
    if source.kind != target.kind:
        return False
    return not target.accepts or source.artifact_type in target.accepts


def artifact_accepted(port: InputPort, artifact_type: str) -> bool:
    """Whether a directly bound artifact satisfies ``port``."""
    return not port.accepts or artifact_type in port.accepts


def output_port_for_artifact(ports: list[OutputPort], artifact_type: str, filename: str) -> OutputPort | None:
    """Best-effort reverse lookup used when collected outputs carry no explicit port."""
    typed = [port for port in ports if port.artifact_type == artifact_type]
    for port in typed:
        if fnmatch(filename, port.filename_glob):
            return port
    return typed[0] if typed else None
