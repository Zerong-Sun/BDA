"""Native Rosetta plugin contracts; fake binaries test integration, not scientific accuracy."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from backend_v2.app.registry.plugin_manifest import PluginManifestCatalog
from backend_v2.app.registry.ports import port_definition_errors
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "qm-scripts/plugins/rosetta"
spec = importlib.util.spec_from_file_location("rosetta_runner", PLUGIN / "runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def pdb(chain="A", shift=0):
    return f"ATOM      1  CA  ALA {chain}   1    {1 + shift:8.3f}{2.0:8.3f}{3.0:8.3f}  1.00 80.00           C  \n"


@pytest.fixture
def workspace(tmp_path):
    inp = tmp_path / "input"
    (inp / "s").mkdir(parents=True)
    (inp / "aux").mkdir()
    (inp / "s" / "complex.pdb").write_text(pdb("A") + pdb("B", 4))
    (inp / "aux" / "mut.txt").write_text("total 1\n1\nA 1 V\n")
    (inp / "aux" / "protocol.xml").write_text(
        '<ROSETTASCRIPTS><SCOREFXNS/><PROTOCOLS/><OUTPUT scorefxn="%%weights%%"/></ROSETTASCRIPTS>'
    )
    return inp, tmp_path / "output", tmp_path / "runtime"


def make_plan(workspace, raw):
    return runner.plan(raw, *workspace)


MODE_CONFIGS = [
    {"application": "score_jd2"},
    {"application": "relax"},
    {"application": "InterfaceAnalyzer", "interface": "A_B"},
    {"application": "relax_interface", "interface": "A_B"},
    {"application": "docking_protocol", "dock_partners": "A_B"},
    {"application": "cartesian_ddg", "ddg_mut_file": "mut.txt", "score_weights": "ref2015_cart"},
    {"application": "rosetta_scripts", "parser_protocol": "protocol.xml", "parser_script_vars": "weights=ref2015"},
]


@pytest.mark.parametrize("config", MODE_CONFIGS)
def test_all_modes_generate_documented_validated_argv_without_execution(workspace, config):
    job = make_plan(workspace, config)
    runner.materialize(job)
    assert job["status"] == "generated_not_executed"
    assert not (workspace[1] / "execution.json").exists()
    guide = (workspace[1] / "parameter-explanations.md").read_text()
    assert all(k in guide for k in job["parameters"])
    assert all(isinstance(token, str) for token in job["entries"][0]["argv"])
    assert job["entries"][0]["input_sha256"] == runner.digest(workspace[0] / "s" / "complex.pdb")
    Draft202012Validator(runner.SPEC["schema"]).validate(config)


@pytest.mark.parametrize(
    "bad",
    [
        {"application": "InterfaceAnalyzer"},
        {"application": "cartesian_ddg", "ddg_mut_file": "mut.txt"},
        {"application": "relax", "relax_cartesian": True},
        {"application": "docking_protocol", "dock_partners": "A_B", "dock_search": "global", "dock_local_refine": True},
        {"application": "score_jd2", "interface": "A_B"},
        {"application": "rosetta_scripts", "parser_protocol": "protocol.xml"},
        {"application": "relax", "constraints_file": "../s/complex.pdb"},
        {"application": "score_jd2", "out_scorefile": "../../bad.sc"},
        {"application": "score_jd2", "nstruct": True},
        {"application": "score_jd2", "replicates": 0},
        {"application": "score_jd2", "something_else": 1},
        {"application": "InterfaceAnalyzer", "interface": "A_A"},
        {"application": "InterfaceAnalyzer", "interface": "A_C"},
    ],
)
def test_invalid_or_inapplicable_configuration_is_rejected_before_any_output(workspace, bad):
    with pytest.raises(runner.ConfigurationError):
        make_plan(workspace, bad)
    assert not workspace[1].exists()


def test_false_values_are_explicit_and_seed_families_unique(workspace):
    job = make_plan(
        workspace, {"application": "InterfaceAnalyzer", "interface": "A_B", "pack_separated": False, "replicates": 3}
    )
    assert len({j["seed"] for j in job["entries"]}) == 3
    args = job["entries"][0]["argv"]
    assert args[args.index("-pack_separated") + 1] == "false"
    assert "-packstat:oversample" not in args
    assert args[args.index("-add_regular_scores_to_scorefile") + 1] == "true"


def test_xml_values_are_data_not_shell_commands(workspace, tmp_path):
    marker = tmp_path / "should-not-exist"
    value = f"weights=$(touch {marker})"
    # Spaces require an explicitly quoted single name=value token.
    job = make_plan(
        workspace,
        {"application": "rosetta_scripts", "parser_protocol": "protocol.xml", "parser_script_vars": repr(value)},
    )
    args = job["entries"][0]["argv"]
    assert args[-1] == value
    assert not marker.exists()


def test_mutation_wt_identity_checked_against_pose_order(workspace):
    (workspace[0] / "aux" / "mut.txt").write_text("total 1\n1\nC 1 V\n")
    with pytest.raises(runner.ConfigurationError, match="WT identity"):
        make_plan(workspace, MODE_CONFIGS[5])


def test_mmcif_requires_explicit_conversion_and_no_partial_batch(workspace):
    (workspace[0] / "s" / "second.cif").write_text("data_x\n")
    with pytest.raises(runner.ConfigurationError, match="mmCIF"):
        make_plan(workspace, {})


def test_existing_results_not_overwritten(workspace):
    workspace[1].mkdir()
    (workspace[1] / "data").write_text("keep")
    with pytest.raises(runner.ConfigurationError, match="never overwritten"):
        make_plan(workspace, {})
    assert (workspace[1] / "data").read_text() == "keep"


def fake_runtime(root, missing=False):
    root.mkdir()
    (root / "bin").mkdir()
    source = """#!SHEBANG
import pathlib,sys,shutil
args=sys.argv[1:]
def get(key,default=None):return args[args.index(key)+1] if key in args else default
out=pathlib.Path(get('-out:path:all'));score=pathlib.Path(get('-out:file:scorefile'))
n=int(get('-nstruct','1'))
if MISSING:
 sys.exit(0)
if 'cartesian_ddg' in sys.argv[0]:
 (out/'mut.ddg').write_text('COMPLEX: Round1: WT: -10\\nCOMPLEX: Round1: MUT_1VAL: -9\\n')
else:
 score.write_text('SCORE: total_score dG_separated description\\n'+''.join(f'SCORE: -10 -3 decoy_{i}\\n' for i in range(n)))
 for i in range(n):shutil.copyfile(get('-in:file:s'),out/f'decoy_{i}.pdb')
""".replace("SHEBANG", sys.executable).replace("MISSING", str(missing))
    for binary in ["score_jd2", "relax", "InterfaceAnalyzer", "docking_protocol", "cartesian_ddg", "rosetta_scripts"]:
        p = root / "bin" / (binary + ".default.linuxgccrelease")
        p.write_text(source)
        p.chmod(0o755)


@pytest.mark.parametrize("config", MODE_CONFIGS)
def test_fake_binary_end_to_end_preserves_raw_outputs_and_execution_status(workspace, config):
    fake_runtime(workspace[2])
    job = make_plan(workspace, config)
    runner.materialize(job)
    evidence = runner.execute(job)
    assert evidence["status"] == "execution_complete_raw_outputs_checked"
    assert (workspace[1] / "checksums.json").is_file()
    if config["application"] == "relax_interface":
        stage = evidence["jobs"][0]["interface_commands"][0]
        argv = stage["argv"]
        relaxed = Path(argv[argv.index("-in:file:s") + 1])
        assert relaxed.parent.name == "relax"
        assert stage["input_sha256"] == runner.digest(relaxed)
        assert argv[argv.index("-fa_max_dis") + 1] == "9.0"


def test_success_exit_without_scores_is_failure(workspace):
    fake_runtime(workspace[2], missing=True)
    job = make_plan(workspace, {})
    runner.materialize(job)
    with pytest.raises(runner.ConfigurationError, match="Fewer SCORE"):
        runner.execute(job)
    assert json.loads((workspace[1] / "execution.json").read_text())["status"] == "failed"


def test_manifest_embedded_runner_runs_without_source_checkout(workspace):
    manifest = next(
        m
        for m in PluginManifestCatalog(ROOT / "backend_v2/plugin_manifests").manifests()
        if m.plugin_version == "2024.09-bda.1"
    )
    assert port_definition_errors(manifest.inputs, manifest.outputs) == []
    fake_runtime(workspace[2])
    env = {
        **os.environ,
        "BDA_INPUT_DIR": str(workspace[0]),
        "BDA_OUTPUT_DIR": str(workspace[1]),
        "BDA_PLUGIN_ROOT": str(workspace[2]),
        "application": "score_jd2",
    }
    result = subprocess.run(["bash", "-c", manifest.command_template], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (
        json.loads((workspace[1] / "execution.json").read_text())["status"] == "execution_complete_raw_outputs_checked"
    )


def test_generated_schema_manifest_and_docs_are_in_sync():
    result = subprocess.run([sys.executable, str(PLUGIN / "build.py"), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    for row in runner.SPEC["schema"]["properties"].values():
        assert row["description"] and row["x-bda-source"].startswith("https://")
        assert row["x-bda-unit"] and row["x-bda-flag"]


def test_geometry_matches_bruteforce_distances_and_defined_right_angle(workspace):
    points = [("A", 1, (0, 0, 0)), ("A", 2, (1, 0, 0)), ("B", 1, (0, 2, 0)), ("B", 2, (0, 3, 0))]
    lines = []
    for chain, resid, xyz in points:
        line = pdb(chain)
        lines.append(line[:22] + f"{resid:4d}" + line[26:30] + "".join(f"{v:8.3f}" for v in xyz) + line[54:])
    path = workspace[0] / "s" / "complex.pdb"
    path.write_text("".join(lines))
    p = runner.normalize(
        {"application": "InterfaceAnalyzer", "interface": "A_B", "receptor_axis": "A:1,A:2", "binder_axis": "B:1,B:2"}
    )
    result = runner.interface_geometry(path, p)
    assert result["anchored_angle_degrees"] == pytest.approx(90)
    assert result["minimum_distance_within_cutoff_angstrom"] == pytest.approx(2)
    expected = sorted([2, 3, 5**0.5, 10**0.5])
    assert sorted(r["distance_angstrom"] for r in result["atom_contacts"]) == pytest.approx(expected)
    assert result["coordinate_sha256"] == runner.digest(path)


def test_geometry_without_anchors_reports_missing_angle_not_zero(workspace):
    p = runner.normalize({"application": "InterfaceAnalyzer", "interface": "A_B"})
    result = runner.interface_geometry(workspace[0] / "s" / "complex.pdb", p)
    assert result["anchored_angle_degrees"] is None
    assert result["angle_status"].startswith("not_computed")


def test_geometry_requires_both_axes(workspace):
    with pytest.raises(runner.ConfigurationError, match="both receptor_axis"):
        make_plan(workspace, {"application": "InterfaceAnalyzer", "interface": "A_B", "receptor_axis": "A:1,A:2"})


def test_unknown_string_scores_preserved_but_nonfinite_energies_rejected(tmp_path):
    score = tmp_path / "test.sc"
    score.write_text("SCORE: total_score custom_label description\nSCORE: -2 native_control model1\n")
    assert runner.score_rows(score)[0]["custom_label"] == "native_control"
    score.write_text("SCORE: total_score description\nSCORE: nan model1\n")
    with pytest.raises(runner.ConfigurationError, match="nonfinite"):
        runner.score_rows(score)
