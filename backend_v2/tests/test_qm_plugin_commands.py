"""The qm plugin definitions from migration 0024, checked against the renderer.

These are shell templates that only ever run on a cluster nobody can reach from CI, so
what is testable is the contract between the template and
``compute.scripts.render_script``: a parameter the user sets must reach the command, and
nothing may be written into another account's directory.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from backend_v2.app.compute.scripts import ScriptContext, render_script


def _load_revision(name: str):
    """Load a revision by path: `0024_...` is not an importable module name.

    Reading the definitions out of the migration rather than restating them here is the
    point - a test that copies the command templates would keep passing after the
    migration changed.
    """
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"revision_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_revision("0024_plugins_point_at_qm")
TARGETS = MIGRATION.TARGETS
RENAMES = MIGRATION.RENAMES

# The same rule compute.scripts applies when exporting node parameters.
SAFE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")

# Directories owned by other accounts. Reading is authorised; writing is not.
FOREIGN_ROOTS = ("/work/bme-liz", "/work/bme-rongx", "/work/ccse-yangyc", "/share/apps")


def render_command(
    command: str,
    container_image: str,
    runtime_setup: list,
    resources: dict,
    parameters: dict,
    runtime_mode: str = "conda",
) -> str:
    return render_script(
        ScriptContext(
            job_name="bda-test",
            remote_dir="/opt/bda/bda/jobs/test",
            command=command,
            queue="v3-64",
            backend="lsf",
            runtime_mode=runtime_mode,
            container_image=container_image,
            runtime_setup=runtime_setup,
            resources=resources,
            parameters=parameters,
            staging_mode="ssh",
        )
    )


def render(plugin_key: str, parameters: dict | None = None) -> str:
    target = TARGETS[plugin_key]
    return render_command(
        target["command"],
        target["container_image"],
        target["runtime_setup"],
        target["resources"],
        parameters or {},
    )


@pytest.mark.parametrize("plugin_key", sorted(TARGETS))
def test_no_placeholder_command_survives(plugin_key: str) -> None:
    """`python run.py` against a `bda/*` image is what this migration exists to remove."""
    target = TARGETS[plugin_key]

    assert target["command"].strip() != "python run.py"
    assert not target["container_image"].startswith("bda/")
    assert target["container_image"].startswith("/")


@pytest.mark.parametrize("plugin_key", sorted(TARGETS))
def test_every_renamed_parameter_is_a_name_the_renderer_exports(plugin_key: str) -> None:
    """The whole point of the rename: `inference.num_designs` never reached the script."""
    for old, new in RENAMES.get(plugin_key, {}).items():
        assert not SAFE_NAME.fullmatch(old), f"{old} did not need renaming"
        assert SAFE_NAME.fullmatch(new), f"{new} would still be dropped"


@pytest.mark.parametrize("plugin_key", sorted(TARGETS))
def test_command_writes_only_into_the_job_output_directory(plugin_key: str) -> None:
    """Reading another account's install is authorised; writing into one is not."""
    command = TARGETS[plugin_key]["command"]
    for line in command.splitlines():
        # Redirections and output flags are where a write would appear.
        for match in re.finditer(r"(?:>|--out_dir|--output_dir=?|--out_folder|-out:path:all)\s*\"?([^\s\"]+)", line):
            written = match.group(1)
            if written.startswith("$"):
                continue
            assert not written.startswith(FOREIGN_ROOTS), f"{plugin_key} writes to {written}"


def test_rfdiffusion_parameters_reach_the_rendered_script() -> None:
    """A node setting contigs/num_designs must see them in the submitted command."""
    script = render(
        "RFdiffusion",
        {
            "contigs": "[A1-50/2-4/B1-19/B21-44]",
            "num_designs": 100,
            "partial_t": 5,
            "provide_seq": "[1-1,13-13]",
            "output_prefix": "example_design",
        },
    )

    assert "export contigs='[A1-50/2-4/B1-19/B21-44]'" in script
    assert "export num_designs=100" in script
    assert 'contigmap.contigs="$contigs"' in script
    assert 'inference.num_designs="${num_designs:-10}"' in script
    # The brackets stay inside double quotes, so the shell cannot glob them.
    assert "contigmap.contigs=[A1" not in script
    assert "run_inference.py" in script
    assert 'inference.output_prefix="$BDA_OUTPUT_DIR/${output_prefix:-design}"' in script


def test_alphafold2_multimer_is_a_preset_not_a_separate_model() -> None:
    """Route 3's 'AlphaFold-Multimer' is this plugin with one parameter changed."""
    script = render("AlphaFold2", {"model_preset": "multimer", "use_gpu_relax": True})

    assert "export model_preset=multimer" in script
    assert '--model_preset="${model_preset:-monomer}"' in script
    # Booleans render as 1/"" so an unset flag disappears entirely.
    assert "export use_gpu_relax=1" in script
    assert "${use_gpu_relax:+--use_gpu_relax}" in script


def test_rosetta_application_switches_the_binary() -> None:
    """InterfaceAnalyzer/ddG need no new software - only a different Rosetta binary."""
    script = render("Rosetta", {"application": "rosetta_scripts", "parser_protocol": "score.xml"})

    assert "export application=rosetta_scripts" in script
    assert "${application:-score_jd2}.default.linuxgccrelease" in script
    assert '${parser_protocol:+-parser:protocol "$parser_protocol"}' in script


def test_proteinmpnn_soluble_weights_are_a_flag_on_the_installed_model() -> None:
    """Route A's 'SolMPNN' is this plugin with --use_soluble_model."""
    script = render("ProteinMPNN", {"use_soluble_model": True, "num_seq_per_target": 8})

    assert "export use_soluble_model=1" in script
    assert "${use_soluble_model:+--use_soluble_model}" in script
    assert "export num_seq_per_target=8" in script


def test_runtime_setup_activates_the_environment_before_the_command() -> None:
    script = render("RFdiffusion")
    setup_line = "conda activate /work/bme-liz/miniconda3/envs/SE3nv-gpu"

    assert setup_line in script
    assert script.index(setup_line) < script.index("run_inference.py")


def test_parameter_exports_still_drop_unsafe_names() -> None:
    """Guards the assumption the rename is built on."""
    script = render("RFdiffusion", {"inference.num_designs": 100, "num_designs": 7})

    assert "export num_designs=7" in script
    assert "inference.num_designs=100" not in script


def test_every_plugin_declares_resources_the_scheduler_can_use() -> None:
    for plugin_key, target in TARGETS.items():
        resources = target["resources"]
        assert resources.get("walltime_minutes"), plugin_key
        assert resources.get("cpus"), plugin_key
        if resources.get("gpu"):
            assert resources.get("gpu_count"), plugin_key


def test_bound_node_parameters_are_unaffected_by_the_rename() -> None:
    """The one ProteinMPNN node bound in production uses already-safe keys."""
    node = SimpleNamespace(
        parameters={"pdb_path": "inputs/x.pdb", "out_folder": "outputs/proteinmpnn", "num_seq_per_target": 5}
    )

    assert not set(node.parameters) & set(RENAMES["ProteinMPNN"])


BASH = shutil.which("bash")


@pytest.mark.skipif(BASH is None, reason="bash is not available")
@pytest.mark.parametrize("plugin_key", sorted(TARGETS))
def test_rendered_script_is_valid_shell(plugin_key: str) -> None:
    """`bash -n` the whole rendered job script.

    These templates are quoting-dense - Hydra list values, ${var:+...} guards, nested
    command substitution - and a stray brace or quote would only surface as a cluster job
    that dies on line 1. That failure costs a queue wait to discover, so parse it here.
    """
    script = render(plugin_key, {"input_path": "x", "input_fasta": "x", "settings": "x", "json_path": "x"})

    result = subprocess.run([BASH, "-n"], input=script, capture_output=True, text=True)  # noqa: S603

    assert result.returncode == 0, f"{plugin_key}: {result.stderr}"


@pytest.mark.skipif(BASH is None, reason="bash is not available")
def test_rfdiffusion_arguments_expand_the_way_hydra_needs() -> None:
    """Run the command with the model replaced by echo, and inspect the real argv.

    Asserting on the template text cannot catch a quoting bug: "[A1-50/2-4]" unquoted is
    a glob, and an empty optional would become an empty argument Hydra rejects. Executing
    the expansion is the only way to see what the model would actually receive.
    """
    command = TARGETS["RFdiffusion"]["command"].replace(
        "/work/bme-liz/software/RFdiffusion/scripts/run_inference.py",
        'printf "%s\\n"',
    )
    script = "\n".join(
        [
            "set -u",
            'export BDA_INPUT_DIR=/nonexistent/inputs',
            'export BDA_OUTPUT_DIR=/tmp/out',
            "export contigs='[A1-50/2-4/B1-19/B21-44]'",
            "export num_designs=100",
            "export partial_t=5",
            "export hotspot_res=''",  # empty optional must vanish, not become ""
            command,
        ]
    )

    result = subprocess.run([BASH], input=script, capture_output=True, text=True)  # noqa: S603
    argv = result.stdout.split("\n")

    assert result.returncode == 0, result.stderr
    # The bracketed contig survives as one argument, unglobbed.
    assert "contigmap.contigs=[A1-50/2-4/B1-19/B21-44]" in argv
    assert "inference.num_designs=100" in argv
    assert "diffuser.partial_T=5" in argv
    assert "inference.output_prefix=/tmp/out/design" in argv
    # No empty argument, and no half-expanded optional.
    assert "" not in [item for item in argv if item != argv[-1]]
    assert not any(item.startswith("ppi.hotspot_res") for item in argv)
    # An absent input structure drops the flag rather than passing an empty path.
    assert not any(item.startswith("inference.input_pdb") for item in argv)


MIGRATION_0025 = _load_revision("0025_qm_paths_verified")


def test_corrections_do_not_point_at_our_own_empty_directories() -> None:
    """0024 trusted the curated example configs; the cluster said otherwise.

    /opt/bda/software is empty and our only conda env is `gemmi`, so any plugin
    claiming BindCraft or Boltz lives under our account was unrunnable.
    """
    for plugin_key, target in MIGRATION_0025.REPOINT.items():
        assert target["container_image"].startswith("/work/bme-liz/"), plugin_key
        assert "/opt/bda/" not in target["command"], plugin_key


def test_absent_software_is_disabled_rather_than_left_pointing_nowhere() -> None:
    """A plugin naming software that does not exist passes preflight and fails at run."""
    assert set(MIGRATION_0025.DISABLE) == {"Chai-1", "AlphaFold2"}
    for reason in MIGRATION_0025.DISABLE.values():
        assert reason


@pytest.mark.skipif(BASH is None, reason="bash is not available")
def test_superfold_command_is_valid_shell_and_carries_the_initial_guess_flag() -> None:
    """superfold is the AF2 initial-guess the routes are specified against."""
    script = render_command(
        MIGRATION_0025.SUPERFOLD["command"],
        MIGRATION_0025.SUPERFOLD["container_image"],
        MIGRATION_0025.SUPERFOLD["runtime_setup"],
        MIGRATION_0025.SUPERFOLD["resources"],
        {"initial_guess": True, "mock_msa_depth": 1},
        runtime_mode=MIGRATION_0025.SUPERFOLD["runtime_mode"],
    )

    result = subprocess.run([BASH, "-n"], input=script, capture_output=True, text=True)  # noqa: S603
    assert result.returncode == 0, result.stderr
    assert "export initial_guess=1" in script
    assert "${initial_guess:+--initial_guess}" in script
    assert "/work/bme-liz/software/superfold/superfold" in script


def test_superfold_never_activates_a_conda_environment() -> None:
    """Its wrapper exits outright when CONDA_DEFAULT_ENV is set."""
    assert MIGRATION_0025.SUPERFOLD["runtime_setup"] == []
    assert MIGRATION_0025.SUPERFOLD["runtime_mode"] == "script"

    script = render_command(
        MIGRATION_0025.SUPERFOLD["command"],
        MIGRATION_0025.SUPERFOLD["container_image"],
        MIGRATION_0025.SUPERFOLD["runtime_setup"],
        MIGRATION_0025.SUPERFOLD["resources"],
        {},
        runtime_mode=MIGRATION_0025.SUPERFOLD["runtime_mode"],
    )

    assert "conda activate" not in script


MIGRATION_0027 = _load_revision("0027_ip_and_physics_tools")


@pytest.mark.skipif(BASH is None, reason="bash is not available")
@pytest.mark.parametrize("plugin", MIGRATION_0027.PLUGINS, ids=lambda p: p["plugin_key"])
def test_tool_command_is_valid_shell(plugin: dict) -> None:
    script = render_command(
        plugin["command"],
        plugin["container_image"],
        plugin["runtime_setup"],
        plugin["resources"],
        {"forcefield": "AMBER"},
        runtime_mode=plugin["runtime_mode"],
    )

    result = subprocess.run([BASH, "-n"], input=script, capture_output=True, text=True)  # noqa: S603

    assert result.returncode == 0, f"{plugin['plugin_key']}: {result.stderr}"


@pytest.mark.parametrize("plugin", MIGRATION_0027.PLUGINS, ids=lambda p: p["plugin_key"])
def test_tool_writes_only_into_the_job_output_directory(plugin: dict) -> None:
    """These live under our own account, but their outputs still belong to the job."""
    for line in plugin["command"].splitlines():
        for match in re.finditer(r">\s*\"?([^\s\"]+)", line):
            written = match.group(1)
            if written.startswith(("$", "&")) or written.isdigit():
                continue
            assert not written.startswith(FOREIGN_ROOTS), f"{plugin['plugin_key']} writes to {written}"


@pytest.mark.parametrize("plugin", MIGRATION_0027.PLUGINS, ids=lambda p: p["plugin_key"])
def test_tool_declares_ports_so_its_outputs_can_be_collected(plugin: dict) -> None:
    """A tool with no output ports produces artifacts collection cannot type."""
    assert plugin["input_ports"], plugin["plugin_key"]
    assert plugin["output_ports"], plugin["plugin_key"]
    for port in plugin["output_ports"]:
        assert port.get("artifact_type"), f"{plugin['plugin_key']}:{port['name']}"


@pytest.mark.skipif(BASH is None, reason="bash is not available")
def test_apbs_titration_is_optional_and_drops_cleanly() -> None:
    """--with-ph only makes sense together with the titration method, or not at all."""
    without = render_command(
        MIGRATION_0027.APBS["command"],
        MIGRATION_0027.APBS["container_image"],
        MIGRATION_0027.APBS["runtime_setup"],
        MIGRATION_0027.APBS["resources"],
        {},
        runtime_mode="conda",
    )
    with_ph = render_command(
        MIGRATION_0027.APBS["command"],
        MIGRATION_0027.APBS["container_image"],
        MIGRATION_0027.APBS["runtime_setup"],
        MIGRATION_0027.APBS["resources"],
        {"with_ph": 3.0},
        runtime_mode="conda",
    )

    assert "export with_ph=3.0" in with_ph
    assert "export with_ph" not in without
    # The flag pair is inseparable: propka is what computes the state at that pH.
    assert '${with_ph:+--titration-state-method propka --with-ph "$with_ph"}' in without


def test_usalign_passes_a_directory_and_relative_names() -> None:
    """`-dir1 "" <absolute paths>` made US-align read zero chains and then segfault.

    It did not exit non-zero with a message - it dumped core, so the job's only symptom
    was an empty output file. US-align concatenates the -dir1 prefix with each name in the
    list, so the prefix must be a real directory (with its trailing slash) and the list
    must hold basenames.
    """
    command = MIGRATION_0027.USALIGN_COMMAND

    assert '-dir1 "$usalign_dir/"' in command
    assert "-printf '%f\\n'" in command
    assert '-dir1 ""' not in command


def test_apbs_rejects_backbone_only_inputs_before_calling_pdb2pqr() -> None:
    """pdb2pqr rebuilds hydrogens, not missing side chains.

    A smoke run against an RFdiffusion backbone died inside pdb2pqr with a bare
    `RuntimeError` wrapping "Found gap in biomolecule structure". The guard turns that into
    a named failure at the top of the script.
    """
    command = MIGRATION_0027.APBS_COMMAND

    assert "looks backbone-only" in command
    assert command.index("looks backbone-only") < command.index("pdb2pqr30")


MIGRATION_0028 = _load_revision("0028_superfold_af3_real_runs")


def test_superfold_preamble_clears_an_active_conda_environment() -> None:
    """superfold's wrapper exits outright when CONDA_DEFAULT_ENV is set.

    0025 left the preamble empty, reasoning that nothing would activate an environment.
    The hand-written job that actually runs on this cluster opens with
    `source deactivate base`, which says the opposite: something does. The unconditional
    unset is the deterministic part - that single variable is what the wrapper tests.
    """
    setup = MIGRATION_0028.SUPERFOLD_SETUP

    assert any("deactivate" in line for line in setup)
    assert "unset CONDA_DEFAULT_ENV" in setup
    assert not any("conda activate" in line for line in setup)


def test_superfold_skips_appledouble_files() -> None:
    """`._foo.pdb` is 4 KB of macOS metadata that parses as neither PDB nor FASTA."""
    assert "! -name '._*'" in MIGRATION_0028.SUPERFOLD_COMMAND


def test_alphafold3_ports_can_tell_its_outputs_apart() -> None:
    """Three ports globbing `*` each match every file, so nothing can be typed."""
    globs = [port["filename_glob"] for port in MIGRATION_0028.AF3_OUTPUT_PORTS]

    assert "*" not in globs
    assert len(globs) == len(set(globs))
    # Taken from what real runs write, per the af3 collector script.
    assert "*_model.cif*" in globs
    assert "*summary_confidences.json" in globs


@pytest.mark.skipif(BASH is None, reason="bash is not available")
def test_corrected_superfold_and_af3_commands_are_valid_shell() -> None:
    for command, params in (
        (MIGRATION_0028.SUPERFOLD_COMMAND, {"initial_guess": True}),
        (MIGRATION_0028.AF3_COMMAND, {"json_path": "fold_input.json"}),
    ):
        script = render_command(command, "/tmp/env", [], {"cpus": 1}, params, runtime_mode="script")
        result = subprocess.run([BASH, "-n"], input=script, capture_output=True, text=True)  # noqa: S603
        assert result.returncode == 0, result.stderr


MIGRATION_0026 = _load_revision("0026_rfd3_and_af3")


def test_rfd3_overrides_match_the_engine_config_keys() -> None:
    """Hydra silently accepts an unknown override only with `+`; a typo here is fatal.

    These five names were checked against `configs/inference_engine/rfdiffusion3.yaml`
    on qm, which declares `# @package _global_` - so they are top-level keys, not nested
    under `inference_engine.`.
    """
    command = MIGRATION_0026.RFD3_COMMAND

    for key in ("inputs=", "out_dir=", "n_batches=", "diffusion_batch_size=", "ckpt_path="):
        assert key in command, key
    # Nested spellings would be wrong for a @package _global_ config.
    assert "inference_engine." not in command
