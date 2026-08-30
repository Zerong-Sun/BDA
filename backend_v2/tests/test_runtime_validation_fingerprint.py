from __future__ import annotations

from types import SimpleNamespace

from backend_v2.app.registry.runtime_validation import (
    plugin_declaration_fingerprint,
    runtime_validation_is_current,
)
from backend_v2.app.registry.tasks import record_runtime_validation


def plugin(**updates):
    values = {
        "plugin_key": "ProteinMPNN",
        "plugin_version": "1",
        "container_image": "/env/mpnn",
        "command": "run --fixed $fixed_positions_jsonl",
        "parameter_schema": {"type": "object"},
        "output_schema": {},
        "input_ports": [{"name": "backbone"}],
        "output_ports": [{"name": "sequences"}],
        "resources": {"cpus": 4},
        "runtime_mode": "conda",
        "runtime_setup": ["source activate mpnn"],
        "output_parser": None,
        "input_adapter": None,
        "runtime_validation_status": "unproven",
        "runtime_validation_evidence": {},
        "runtime_validated_at": None,
        "version": 1,
    }
    values.update(updates)
    return SimpleNamespace(**values)


def test_runtime_proof_is_reused_while_declaration_is_unchanged() -> None:
    model = plugin()
    record_runtime_validation(
        None,
        model,
        proven=True,
        evidence={
            "job_id": "4127185",
            "checks": ["fixed positions honoured", "five sequences per backbone"],
            "ruleset_sha256": "a" * 64,
            "environment_fingerprint": "qm:mlfold:2026-08-11",
        },
    )

    assert model.runtime_validation_evidence["declaration_fingerprint"] == plugin_declaration_fingerprint(model)
    assert runtime_validation_is_current(model) is True


def test_any_executable_contract_change_invalidates_runtime_proof() -> None:
    model = plugin()
    record_runtime_validation(None, model, proven=True, evidence={"checks": ["output port collected"]})
    model.command = "run --different-default"

    assert runtime_validation_is_current(model) is False


def test_legacy_bare_proven_flag_is_not_treated_as_current_proof() -> None:
    model = plugin(runtime_validation_status="proven", runtime_validation_evidence={"job_id": "old"})

    assert runtime_validation_is_current(model) is False
