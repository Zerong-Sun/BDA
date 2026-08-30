"""AlphaFold 3 input adaptation.

AF3 reads its sequences from a JSON job specification rather than a FASTA, which left an
AF3 node unable to sit downstream of anything that produces sequences.
"""

from __future__ import annotations

import json
import uuid

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.compute.input_adapters import AdapterContext, available_input_adapters, get_input_adapter
from backend_v2.app.compute.input_adapters.af3_fold_input import build_fold_input, chain_id, parse_fasta

FASTA = ">binder_1 designed\nMKTAYIAKQR\nQISFVK\n>target\nGSHMLEEQ\n"


def _context(inputs: list[dict], payload: bytes = FASTA.encode(), parameters: dict | None = None):
    return AdapterContext(
        job_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        attempt_number=1,
        inputs=inputs,
        parameters=parameters or {},
        read_bytes=lambda key: payload,
        job_name="af3",
    )


def _sequence_input() -> dict:
    return {"port": "sequences", "filename": "designs.fa", "object_key": "k"}


def test_chain_ids_continue_past_the_alphabet() -> None:
    assert [chain_id(i) for i in (0, 1, 25)] == ["A", "B", "Z"]
    assert chain_id(26) == "AA"
    assert chain_id(27) == "AB"


def test_fasta_parsing_joins_wrapped_lines() -> None:
    records = parse_fasta(FASTA)
    assert [name.split()[0] for name, _ in records] == ["binder_1", "target"]
    # A sequence split across lines must be reassembled, not truncated.
    assert records[0][1] == "MKTAYIAKQRQISFVK"


def test_each_record_becomes_its_own_chain() -> None:
    """A multi-record FASTA is a complex - a designed binder plus its target."""
    payload = build_fold_input(parse_fasta(FASTA), name="job")
    assert payload["dialect"] == "alphafold3"
    assert [entry["protein"]["id"] for entry in payload["sequences"]] == ["A", "B"]
    assert payload["sequences"][0]["protein"]["sequence"] == "MKTAYIAKQRQISFVK"


def test_adapter_generates_fold_input_from_bound_sequences() -> None:
    result = get_input_adapter("af3_fold_input")(_context([_sequence_input()]))
    assert len(result.generated) == 1
    generated = result.generated[0]
    assert generated.port == "json_path"
    assert generated.filename == "fold_input.json"
    payload = json.loads(generated.content)
    assert len(payload["sequences"]) == 2


def test_an_explicit_specification_is_never_overwritten() -> None:
    """A hand-tuned fold_input.json must win over the convenience path."""
    result = get_input_adapter("af3_fold_input")(
        _context([{"port": "json_path", "filename": "fold_input.json", "object_key": "k"}])
    )
    assert result.generated == []
    assert any("bound explicitly" in warning for warning in result.warnings)


def test_missing_sequences_warns_rather_than_emitting_an_empty_job() -> None:
    result = get_input_adapter("af3_fold_input")(_context([]))
    assert result.generated == []
    assert result.warnings


def test_non_protein_residues_fail_loudly() -> None:
    """A nucleotide needs a different AF3 entity type; folding it as protein is wrong."""
    with pytest.raises(ValueError, match="non_protein_residues"):
        get_input_adapter("af3_fold_input")(_context([_sequence_input()], payload=b">rna\nAUGCUAGC*\n"))


def test_model_seeds_are_overridable() -> None:
    result = get_input_adapter("af3_fold_input")(
        _context([_sequence_input()], parameters={"model_seeds": [7, 8]})
    )
    assert json.loads(result.generated[0].content)["modelSeeds"] == [7, 8]


def test_plugins_without_an_adapter_are_unaffected() -> None:
    assert get_input_adapter(None) is None
    assert get_input_adapter("nope") is None
    assert "af3_fold_input" in available_input_adapters()
