from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_revision():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/0046_workflow_plugin_ports.py"
    spec = importlib.util.spec_from_file_location("revision_0046_workflow_plugin_ports", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_revision()


def test_existing_bindings_are_rewritten_idempotently() -> None:
    cases = [
        (
            "ProteinMPNN",
            [{"port": "backbone", "source": "upstream", "from_node": "rfd", "from_port": "backbones"}],
            "pdb_path",
        ),
        (
            "Rosetta",
            [{"port": "structure", "source": "upstream", "from_node": "af2", "from_port": "structures"}],
            "s",
        ),
        (
            "superfold",
            [{"port": "structures", "source": "upstream", "from_node": "mpnn", "from_port": "sequences"}],
            "sequences",
        ),
    ]
    for plugin_key, original, expected_port in cases:
        rewritten, changed = MIGRATION.rewrite_bindings(plugin_key, original)
        assert changed is True
        assert rewritten[0]["port"] == expected_port
        again, changed_again = MIGRATION.rewrite_bindings(plugin_key, rewritten)
        assert again == rewritten
        assert changed_again is False


def test_superfold_structure_binding_is_not_rewritten_as_sequence() -> None:
    original = [
        {
            "port": "structures",
            "source": "upstream",
            "from_node": "predictor",
            "from_port": "predicted_structure",
        }
    ]
    assert MIGRATION.rewrite_bindings("superfold", original) == (original, False)


def test_explicit_graph_edges_are_rewritten_idempotently() -> None:
    cases = [
        ("ProteinMPNN", {"source_port": "backbones", "target_port": "backbone"}, "pdb_path"),
        ("Rosetta", {"source_port": "structures", "target_port": "structure"}, "s"),
        ("superfold", {"source_port": "sequences", "target_port": "structures"}, "sequences"),
    ]
    for plugin_key, original, expected_port in cases:
        rewritten, changed = MIGRATION.rewrite_edge(plugin_key, original)
        assert changed is True
        assert rewritten["target_port"] == expected_port
        assert MIGRATION.rewrite_edge(plugin_key, rewritten) == (rewritten, False)


def test_superfold_structure_edge_remains_on_structures() -> None:
    edge = {"source_port": "predicted_structure", "target_port": "structures"}
    assert MIGRATION.rewrite_edge("superfold", edge) == (edge, False)


def test_commands_read_the_declared_staging_directories() -> None:
    assert "$BDA_INPUT_DIR/pdb_path" in MIGRATION.PROTEINMPNN_COMMAND
    assert "$BDA_INPUT_DIR/jsonl_path" in MIGRATION.PROTEINMPNN_COMMAND
    assert "$BDA_INPUT_DIR/fixed_positions" in MIGRATION.PROTEINMPNN_COMMAND
    assert "requires_fixed_positions is true" in MIGRATION.PROTEINMPNN_COMMAND
    assert "$BDA_INPUT_DIR/s" in MIGRATION.ROSETTA_COMMAND
    assert "$BDA_INPUT_DIR/structures" in MIGRATION.SUPERFOLD_COMMAND
    assert "$BDA_INPUT_DIR/sequences" in MIGRATION.SUPERFOLD_COMMAND
    assert {port["name"] for port in MIGRATION.SUPERFOLD_INPUT_PORTS} == {
        "structures",
        "sequences",
    }


def test_legacy_and_inferred_plugin_ports_are_canonicalized_without_losing_options() -> None:
    legacy_mpnn = [
        {"name": "backbone", "kind": "protein_structure", "required": True},
        {"name": "fixed_positions", "kind": "params", "required": False},
    ]
    inferred_mpnn = [
        {"name": "pdb_path", "kind": "protein_structure"},
        {"name": "jsonl_path", "kind": "params"},
        {"name": "pssm_jsonl", "kind": "params"},
        {"name": "fixed_positions", "kind": "params"},
    ]

    legacy_names = [item["name"] for item in MIGRATION.canonical_input_ports("ProteinMPNN", legacy_mpnn)]
    inferred = MIGRATION.canonical_input_ports("ProteinMPNN", inferred_mpnn)
    inferred_names = [item["name"] for item in inferred]

    assert legacy_names == ["pdb_path", "jsonl_path", "fixed_positions"]
    assert inferred_names == ["pdb_path", "jsonl_path", "pssm_jsonl", "fixed_positions"]
    alternatives = inferred[:2]
    assert all(item["required"] is True for item in alternatives)
    assert {item["exclusive_group"] for item in alternatives} == {"backbone_source"}
    assert next(item for item in alternatives if item["name"] == "pdb_path")["multiple"] is True

    assert [item["name"] for item in MIGRATION.canonical_input_ports("Rosetta", [{"name": "complexes"}])] == ["s"]
    rosetta = MIGRATION.canonical_input_ports("Rosetta", [{"name": "s"}, {"name": "parser_protocol", "kind": "params"}])
    assert [item["name"] for item in rosetta] == ["s", "parser_protocol"]
    assert rosetta[0]["required"] is True
    assert rosetta[0]["multiple"] is True


def _command_env(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    input_dir.mkdir()
    output_dir.mkdir()
    env = {
        **os.environ,
        "BDA_INPUT_DIR": str(input_dir),
        "BDA_OUTPUT_DIR": str(output_dir),
    }
    return env, input_dir, output_dir


def _fake_python(tmp_path: Path, env: dict[str, str]) -> Path:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    call_log = tmp_path / "python-calls.log"
    executable = fake_bin / "python"
    executable.write_text('#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$CALL_LOG"\nexit 0\n')
    executable.chmod(0o755)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["CALL_LOG"] = str(call_log)
    return call_log


@pytest.mark.parametrize("source_port", ["pdb_path", "jsonl_path"])
def test_proteinmpnn_runs_with_either_declared_input_mode(tmp_path: Path, source_port: str) -> None:
    env, input_dir, _ = _command_env(tmp_path)
    call_log = _fake_python(tmp_path, env)
    source_dir = input_dir / source_port
    source_dir.mkdir()
    source = source_dir / ("design.pdb" if source_port == "pdb_path" else "design.jsonl")
    source.write_text("input")

    result = subprocess.run(
        ["bash", "-c", MIGRATION.PROTEINMPNN_COMMAND],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    calls = call_log.read_text()
    if source_port == "pdb_path":
        assert "parse_multiple_chains.py" in calls
        assert f"--input_path={source_dir}" in calls
        assert "parsed_pdbs.jsonl" in calls
    else:
        assert "parse_multiple_chains.py" not in calls
        assert f"--jsonl_path {source}" in calls


def test_proteinmpnn_preserves_the_required_fixed_position_guard(tmp_path: Path) -> None:
    env, input_dir, _ = _command_env(tmp_path)
    pdb_dir = input_dir / "pdb_path"
    pdb_dir.mkdir()
    (pdb_dir / "design.pdb").write_text("input")
    env["requires_fixed_positions"] = "1"

    result = subprocess.run(
        ["bash", "-c", MIGRATION.PROTEINMPNN_COMMAND],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 64
    assert "no position map was staged" in result.stderr


@pytest.mark.parametrize("filename", ["design.pdb", "design.cif", "design.mmcif"])
def test_rosetta_stages_structures_from_s(tmp_path: Path, filename: str) -> None:
    env, input_dir, output_dir = _command_env(tmp_path)
    structure_dir = input_dir / "s"
    structure_dir.mkdir()
    structure = structure_dir / filename
    structure.write_text("ATOM")
    call_log = tmp_path / "rosetta-calls.log"
    executable = tmp_path / "fake-rosetta"
    executable.write_text('#!/bin/sh\nprintf \'%s\\n\' "$*" > "$CALL_LOG"\n')
    executable.chmod(0o755)
    env["CALL_LOG"] = str(call_log)
    env["FAKE_ROSETTA"] = str(executable)
    command = MIGRATION.ROSETTA_COMMAND.replace(
        'rosetta_bin="/work/bme-liz/software/rosetta/source/bin/${application:-score_jd2}.default.linuxgccrelease"',
        'rosetta_bin="$FAKE_ROSETTA"',
    )

    result = subprocess.run(["bash", "-c", command], env=env, text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stderr
    assert (output_dir / "inputs.list").read_text().strip() == str(structure)
    assert f"-in:file:l {output_dir / 'inputs.list'}" in call_log.read_text()


@pytest.mark.parametrize(
    ("source_port", "filename"),
    [("structures", "design.pdb"), ("sequences", "design with space.fasta")],
)
def test_superfold_scans_both_declared_input_modes(tmp_path: Path, source_port: str, filename: str) -> None:
    env, input_dir, _ = _command_env(tmp_path)
    source_dir = input_dir / source_port
    source_dir.mkdir()
    source = source_dir / filename
    source.write_text("input")
    call_log = tmp_path / "superfold-calls.log"
    executable = tmp_path / "fake-superfold"
    executable.write_text('#!/bin/sh\nfor argument in "$@"; do printf \'<%s>\\n\' "$argument"; done > "$CALL_LOG"\n')
    executable.chmod(0o755)
    env["CALL_LOG"] = str(call_log)
    env["FAKE_SUPERFOLD"] = str(executable)
    command = MIGRATION.SUPERFOLD_COMMAND.replace("/work/bme-liz/software/superfold/superfold", '"$FAKE_SUPERFOLD"')

    result = subprocess.run(["bash", "-c", command], env=env, text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stderr
    assert f"<{source}>" in call_log.read_text().splitlines()


def test_changed_plugin_declaration_loses_stale_validation_proof(monkeypatch) -> None:
    statements: list[str] = []

    class Result:
        def fetchall(self):
            return [SimpleNamespace(id="plugin-id", input_ports=[])]

    class Bind:
        def execute(self, statement, _params):
            statements.append(str(statement))
            return Result()

    monkeypatch.setattr(MIGRATION.op, "get_bind", lambda: Bind())
    MIGRATION._update_plugin("ProteinMPNN", MIGRATION.PROTEINMPNN_COMMAND)

    statement = statements[1]
    assert "WHERE id = :plugin_id" in statement
    assert "input_ports = CAST(:input_ports AS json)" in statement
    assert "validation_status = 'unknown'" in statement
    assert "validated_at = NULL" in statement
    assert "runtime_validation_status = 'unproven'" in statement
    assert "runtime_validated_at = NULL" in statement
    assert "runtime_validation_evidence" in statement


def test_embedded_graph_bindings_are_rewritten_with_node_bindings(monkeypatch) -> None:
    graph = {
        "nodes": [
            {
                "key": "mpnn",
                "input_bindings": [{"port": "backbone", "source": "upstream", "from_port": "backbones"}],
            }
        ],
        "edges": [
            {
                "source": "rfd",
                "target": "mpnn",
                "source_port": "backbones",
                "target_port": "backbone",
            }
        ],
    }
    row = SimpleNamespace(
        id="node-id",
        workflow_run_id="workflow-id",
        node_key="mpnn",
        model_plugin="ProteinMPNN",
        # This row was already repaired by a partial/manual fix. Migration 0046 must
        # still repair the independently stale embedded graph and its explicit edge.
        input_bindings=[{"port": "pdb_path", "source": "upstream", "from_port": "backbones"}],
    )
    updates: list[tuple[str, dict | None]] = []

    class Result:
        def __init__(self, rows=None, one=None):
            self.rows = rows or []
            self.one = one

        def fetchall(self):
            return self.rows

        def fetchone(self):
            return self.one

    class Bind:
        def execute(self, statement, params=None):
            sql = str(statement)
            updates.append((sql, params))
            if sql.startswith("SELECT id"):
                return Result(rows=[row])
            if sql.startswith("SELECT graph"):
                return Result(one=SimpleNamespace(graph=graph))
            return Result()

    monkeypatch.setattr(MIGRATION.op, "get_bind", lambda: Bind())
    MIGRATION._rewrite_workflow_nodes()

    assert not any(sql.startswith("UPDATE workflow_nodes") for sql, _ in updates)
    graph_update = next(params for sql, params in updates if sql.startswith("UPDATE workflow_runs"))
    rewritten_graph = json.loads(graph_update["graph"])
    assert rewritten_graph["nodes"][0]["input_bindings"][0]["port"] == "pdb_path"
    assert rewritten_graph["edges"][0]["target_port"] == "pdb_path"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not available")
@pytest.mark.parametrize(
    "command",
    [MIGRATION.PROTEINMPNN_COMMAND, MIGRATION.ROSETTA_COMMAND, MIGRATION.SUPERFOLD_COMMAND],
)
def test_corrected_commands_are_valid_shell(command: str) -> None:
    result = subprocess.run(["bash", "-n"], input=command, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
