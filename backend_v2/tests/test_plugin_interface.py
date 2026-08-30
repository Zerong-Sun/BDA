"""Plugin-facing contracts: script rendering, validation, output parsers, GC safety."""

from __future__ import annotations

import uuid

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.compute import adapters, tasks
from backend_v2.app.compute.adapters import ADAPTER_REGISTRY, LSFAdapter, RuntimeJob, adapter_for, register_adapter
from backend_v2.app.compute.parsers import ParseContext, available_parsers, get_parser
from backend_v2.app.compute.scripts import ScriptContext, render_script
from backend_v2.app.core.config import get_settings
from backend_v2.app.registry import tasks as registry_tasks
from backend_v2.app.registry.ports import InputPort, OutputPort, port_definition_errors, ports_compatible


class _Storage:
    def download_url(self, key: str, *, ttl_seconds: int | None = None) -> str:
        return f"https://get/{key}"

    def upload_url(self, key: str, *, ttl_seconds: int | None = None) -> str:
        return f"https://put/{key}"


def _runtime_job(job_id: uuid.UUID) -> RuntimeJob:
    return RuntimeJob(
        id=job_id,
        attempt_number=1,
        model_plugin="ProteinMPNN",
        runtime_spec={
            "command": "run_mpnn.sh --seqs 8",
            "queue": "gpu",
            "input_manifest_key": f"jobs/{job_id}/attempt-1/input-manifest.json",
            "output_manifest_key": f"jobs/{job_id}/attempt-1/output-manifest.json",
            "plugin_snapshot": {"runtime_mode": "container", "resources": {"cpus": 4, "gpu": True}},
        },
    )


def _lsf_adapter() -> LSFAdapter:
    adapter = LSFAdapter.__new__(LSFAdapter)
    adapter.host, adapter.root, adapter.timeout = "qm", "/work/bda", 5
    adapter.ssh_key, adapter.default_queue, adapter.upload_wrapper = "/key", "normal", "/usr/local/bin/upload"
    adapter.staging_mode = "presigned"
    return adapter


def test_preview_and_submitted_script_are_identical(monkeypatch) -> None:
    """A preview that differs from what runs is worse than no preview at all."""
    monkeypatch.setattr(adapters, "ObjectStorage", _Storage)
    job_id = uuid.uuid4()
    adapter = _lsf_adapter()
    job = _runtime_job(job_id)

    submitted = render_script(adapter.script_context(job, adapters._manifest_environment(job)))

    # Render the same job through the preview path's context builder.
    preview = render_script(
        ScriptContext(
            job_name=job.deterministic_name,
            remote_dir=adapter.remote_dir(job),
            command="run_mpnn.sh --seqs 8",
            queue="gpu",
            backend="lsf",
            runtime_mode="container",
            input_manifest_url=f"https://get/jobs/{job_id}/attempt-1/input-manifest.json",
            output_manifest_url=f"https://put/jobs/{job_id}/attempt-1/output-manifest.json",
            upload_wrapper="/usr/local/bin/upload",
            staging_mode="presigned",
            resources={"cpus": 4, "gpu": True},
        )
    )
    assert preview == submitted
    assert "#BSUB -q gpu" in submitted
    assert "#BSUB -n 4" in submitted
    assert 'num=1:mode=exclusive_process' in submitted


def test_script_honours_runtime_mode_for_non_container_sites() -> None:
    """LSF sites commonly use modules or conda, not Docker."""
    base = {
        "job_name": "bda-x",
        "remote_dir": "/work/x",
        "command": "run.sh",
        "queue": "normal",
        "backend": "lsf",
    }
    module = render_script(ScriptContext(**base, runtime_mode="module", container_image="rfdiffusion/1.1.0"))
    conda = render_script(ScriptContext(**base, runtime_mode="conda", container_image="mpnn-env"))
    assert "module load rfdiffusion/1.1.0" in module
    assert "conda activate mpnn-env" in conda


def test_docker_preview_shows_the_actual_invocation() -> None:
    script = render_script(
        ScriptContext(
            job_name="bda-y",
            remote_dir="/tmp",
            command="run.sh",
            queue="normal",
            backend="docker",
            container_image="mpnn:1.0.0",
            resources={"cpus": 2, "memory_gb": 8},
        )
    )
    assert "docker run" in script
    assert "mpnn:1.0.0" in script
    assert "--cpus" in script and "--memory" in script


def test_adapter_registry_is_extensible() -> None:
    """A site must be able to add a scheduler without editing the compute module."""
    sentinel = object()
    register_adapter("slurm", lambda: sentinel)
    try:
        assert adapter_for("slurm") is sentinel
    finally:
        ADAPTER_REGISTRY.pop("slurm", None)
    with pytest.raises(RuntimeError, match="unsupported_compute_backend"):
        adapter_for("nonexistent")


def test_port_compatibility_uses_kind_and_artifact_type() -> None:
    backbones = OutputPort(name="backbones", kind="protein_structure", artifact_type="backbone_set")
    accepts_structure = InputPort(name="backbone", kind="protein_structure", accepts=["backbone_set"])
    wrong_kind = InputPort(name="seqs", kind="protein_sequence", accepts=["backbone_set"])
    wrong_type = InputPort(name="backbone", kind="protein_structure", accepts=["predicted_structure"])
    open_port = InputPort(name="any", kind="protein_structure")

    assert ports_compatible(backbones, accepts_structure)
    assert ports_compatible(backbones, open_port)
    assert not ports_compatible(backbones, wrong_kind)
    assert not ports_compatible(backbones, wrong_type)


def test_port_definition_errors_flag_bad_declarations() -> None:
    errors = port_definition_errors(
        [{"name": "a", "kind": "protein_structure"}, {"name": "a", "kind": "not_a_kind"}],
        [{"name": "out", "kind": "tabular", "artifact_type": "score_table"}],
    )
    assert "input_ports_names_must_be_unique" in errors
    assert any(item.startswith("input_ports_unknown_kind:") for item in errors)


def test_plugin_validation_writes_to_its_own_columns() -> None:
    """Results used to be stuffed into parameter_schema, corrupting the author's schema."""

    class Plugin:
        container_image = "img:1.0"
        command = "run"
        parameter_schema = {"type": "object", "properties": {"n": {"type": "integer"}}}
        output_schema = {}
        input_ports = [{"name": "in", "kind": "protein_structure"}]
        output_ports = [{"name": "out", "kind": "tabular", "artifact_type": "score_table"}]
        runtime_mode = "container"
        resources = {}

    assert registry_tasks._model_plugin_errors(Plugin()) == []

    class Bad(Plugin):
        container_image = "img-without-tag"
        parameter_schema = {"type": "not-a-real-type"}

    errors = registry_tasks._model_plugin_errors(Bad())
    assert "container_image_tag_required" in errors
    assert any(item.startswith("parameter_schema_not_valid_json_schema") for item in errors)


def test_proteinmpnn_parser_reads_native_fasta() -> None:
    """The platform reads the model's own output instead of demanding BDA-shaped JSON."""
    fasta = (
        ">3HTN, score=1.1387, global_score=1.2686, seq_recovery=0.3448\n"
        "MKTAYIAKQRQISFVK\n"
        ">T=0.1, sample=1, score=0.9126, global_score=1.1197, seq_recovery=0.4310\n"
        "MKTAYIAKQRQISFVL\n"
        ">T=0.1, sample=2, score=0.8011, global_score=1.0102, seq_recovery=0.5100\n"
        "MKTAYIAKQRQISFVM\n"
    )
    context = ParseContext(
        job_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        attempt_number=1,
        outputs=[
            {
                "filename": "designs.fa",
                "object_key": "jobs/x/outputs/designs.fa",
                "artifact_type": "sequence_set",
                "metadata": {},
            }
        ],
        parameters={},
        read_bytes=lambda key: fasta.encode(),
    )
    parsed = get_parser("proteinmpnn_fasta")(context)

    # The first record is the native input sequence, not a design.
    assert len(parsed.candidates) == 2
    keys = {item.candidate_key for item in parsed.candidates}
    assert keys == {"designs_sample1", "designs_sample2"}
    best = min(parsed.candidates, key=lambda item: item.score or 99)
    assert best.candidate_key == "designs_sample2"
    assert best.rank == 1  # lower ProteinMPNN score is better
    assert best.properties["sequence"] == "MKTAYIAKQRQISFVM"
    assert best.scores["seq_recovery"] == pytest.approx(0.51)


def test_unknown_parser_falls_back_to_manifest_metadata() -> None:
    """Plugins registered before the parser interface must keep working unchanged."""
    assert "manifest_metadata" in available_parsers()
    context = ParseContext(
        job_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        attempt_number=1,
        outputs=[
            {
                "filename": "design.pdb",
                "object_key": "k",
                "artifact_type": "candidate_structure",
                "metadata": {
                    "candidate": {"candidate_key": "cand-1", "score": 0.9},
                    "experiment_result": {"experiment_type": "binding", "value": 1.5, "unit": "nM"},
                },
            }
        ],
        parameters={},
        read_bytes=lambda key: b"",
    )
    parsed = get_parser(None)(context)
    other = get_parser("a-parser-that-does-not-exist")(context)

    assert parsed.candidates[0].candidate_key == "cand-1"
    assert parsed.results[0].experiment_type == "binding"
    assert parsed.results[0].candidate_ref == "cand-1"
    assert other.candidates[0].candidate_key == "cand-1"


def test_gc_never_deletes_a_live_jobs_working_files() -> None:
    """The orphan sweep used to delete input manifests out from under queued jobs."""
    live = (f"jobs/{uuid.uuid4()}/",)
    assert tasks._gc_protected(f"{live[0]}attempt-1/input-manifest.json", live)
    assert tasks._gc_protected(f"{live[0]}attempt-1/outputs/design.pdb", live)
    # Deliberately-written non-artifact prefixes are also held back.
    assert tasks._gc_protected("projects/abc/literature/searches/x.json", live)
    assert tasks._gc_protected("research-generations/1/structures/x.pending", live)
    # A genuine orphan from a finished job is still collectable.
    assert not tasks._gc_protected(f"jobs/{uuid.uuid4()}/attempt-1/input-manifest.json", live)
    assert not tasks._gc_protected("staging/deadbeef", live)


def _ssh_staged_context(**overrides) -> ScriptContext:
    base = dict(
        job_name="bda-abc-a1",
        remote_dir="/work/bda/jobs/abc/attempt-1",
        command="run_model.sh",
        queue="v3-64",
        backend="lsf",
        staging_mode="ssh",
    )
    return ScriptContext(**{**base, **overrides})


def test_ssh_staged_script_needs_no_network_or_cluster_wrapper() -> None:
    """Compute nodes often cannot reach the object store, so the job must not try.

    The manifest emitter is inlined instead of installed, so onboarding a cluster needs
    only SSH access - no software installation.
    """
    script = render_script(_ssh_staged_context())
    assert "BDA_INPUT_MANIFEST_URL" not in script
    assert "BDA_OUTPUT_MANIFEST_URL" not in script
    assert "BDA_UPLOAD_WRAPPER" not in script
    assert 'export BDA_INPUT_DIR=/work/bda/jobs/abc/attempt-1/inputs' in script
    assert 'export BDA_OUTPUT_DIR=/work/bda/jobs/abc/attempt-1/outputs' in script
    # The job writes its own manifest before exiting.
    assert "output-manifest.json" in script
    assert "hashlib" in script and "sha256" in script


def test_presigned_script_keeps_the_url_contract() -> None:
    """Sites whose nodes can reach the object store keep the original behaviour."""
    script = render_script(_ssh_staged_context(staging_mode="presigned", upload_wrapper="/usr/local/bin/up"))
    assert "BDA_INPUT_MANIFEST_URL" in script
    assert "BDA_UPLOAD_WRAPPER" in script
    assert "hashlib" not in script


def test_slot_count_ptile_and_thread_budget_never_disagree() -> None:
    """``-n``, ``span[ptile]`` and ``$BDA_CPUS`` are one number, written three times.

    ptile is slots PER HOST: ``-n 8`` without a span lets LSF scatter eight slots over
    eight machines, which either stays PEND on the spanning requirement or runs a job
    whose threads cannot see each other. This renderer used to emit ``-n`` alone while
    every hand-written job in the project wrote the pair, so a plugin declaring eight
    cpus produced directives no reviewer of those jobs would have signed off.

    ``$BDA_CPUS`` joins them because a tool told to use a different number of threads
    than the scheduler reserved is the same defect one layer down - it is what produces
    the low-utilisation mail this project treats as a violation.
    """
    for declared, expected in (({}, 1), ({"cpus": 1}, 1), ({"cpus": 8}, 8)):
        script = render_script(_ssh_staged_context(resources=declared))
        assert f"#BSUB -n {expected}" in script
        assert f'#BSUB -R "span[ptile={expected}]"' in script
        assert f"export BDA_CPUS={expected}" in script


def test_ssh_staged_script_creates_the_output_directory() -> None:
    """The emitter walks $BDA_OUTPUT_DIR, so a job producing nothing must still succeed."""
    script = render_script(_ssh_staged_context())
    assert 'mkdir -p "$BDA_OUTPUT_DIR"' in script
    assert script.index('mkdir -p "$BDA_OUTPUT_DIR"') < script.index("run_model.sh")


def test_adapter_target_overrides_global_settings() -> None:
    """A second cluster must be configuration, not a code change."""
    adapter = LSFAdapter(
        {
            "lsf_ssh_host": "cluster-b.example.edu",
            "lsf_queue": "gpu-a100",
            "lsf_remote_root": "/scratch/bda/",
            "lsf_staging_mode": "ssh",
            "lsf_ssh_password_ref": None,
            "lsf_ssh_key_path": "/keys/cluster-b",
        }
    )
    assert adapter.host == "cluster-b.example.edu"
    assert adapter.default_queue == "gpu-a100"
    assert adapter.root == "/scratch/bda"  # trailing slash normalised
    assert adapter.staging_mode == "ssh"
    # Keys not present in the target still come from global settings.
    assert adapter.timeout == get_settings().lsf_connect_timeout_seconds


def test_adapter_for_passes_the_target_through() -> None:
    seen: dict = {}

    def factory(target: dict | None = None):
        seen["target"] = target
        return object()

    register_adapter("probe-backend", factory)
    try:
        adapter_for("probe-backend", {"lsf_queue": "q1"})
        assert seen["target"] == {"lsf_queue": "q1"}
        adapter_for("probe-backend")
        assert seen["target"] is None
    finally:
        ADAPTER_REGISTRY.pop("probe-backend", None)


def test_adapter_for_tolerates_a_factory_without_target_support() -> None:
    """Adapters registered before target support keep working for the default target."""
    register_adapter("legacy-backend", lambda: "legacy")
    try:
        assert adapter_for("legacy-backend", {"lsf_queue": "ignored"}) == "legacy"
    finally:
        ADAPTER_REGISTRY.pop("legacy-backend", None)


def test_node_parameters_are_validated_against_the_plugin_schema() -> None:
    """A typo'd parameter used to reach the cluster unchallenged."""
    from backend_v2.app.workflows.preflight import parameter_blockers

    class Node:
        node_key = "mpnn"
        id = uuid.uuid4()
        parameters: dict = {}

    class Plugin:
        parameter_schema = {
            "type": "object",
            "properties": {"num_seq": {"type": "integer", "minimum": 1}},
            "required": ["num_seq"],
        }

    node, plugin = Node(), Plugin()

    node.parameters = {"num_seq": 8}
    assert parameter_blockers(node, plugin) == []

    node.parameters = {"num_seq": "eight"}
    assert [item["code"] for item in parameter_blockers(node, plugin)] == ["node_parameters_invalid"]

    node.parameters = {}
    assert parameter_blockers(node, plugin)

    # A plugin with no schema constrains nothing.
    class Unconstrained:
        parameter_schema: dict = {}

    assert parameter_blockers(node, Unconstrained()) == []
    assert parameter_blockers(node, None) == []


def test_a_malformed_plugin_schema_does_not_block_the_workflow_author() -> None:
    """The defect belongs to the plugin, and registry validation reports it there."""
    from backend_v2.app.workflows.preflight import parameter_blockers

    class Node:
        node_key = "n"
        id = uuid.uuid4()
        parameters = {"anything": 1}

    class BrokenSchema:
        parameter_schema = {"type": "not-a-real-type"}

    assert parameter_blockers(Node(), BrokenSchema()) == []


def test_port_declaration_errors_cover_the_malformed_shapes() -> None:
    assert port_definition_errors([], []) == []
    assert "input_ports_must_be_array" in port_definition_errors("nope", [])
    assert "output_ports_must_be_array" in port_definition_errors([], "nope")
    # A port missing its required fields is reported, not silently dropped.
    assert any(item.startswith("input_ports_invalid:") for item in port_definition_errors([{"kind": "x"}], []))
    assert any(
        item.startswith("output_ports_invalid:") for item in port_definition_errors([], [{"name": "o"}])
    )


def test_output_port_lookup_prefers_a_filename_match() -> None:
    from backend_v2.app.registry.ports import output_port_for_artifact, parse_output_ports

    ports = parse_output_ports(
        [
            {"name": "pdbs", "kind": "protein_structure", "artifact_type": "s", "filename_glob": "*.pdb"},
            {"name": "cifs", "kind": "protein_structure", "artifact_type": "s", "filename_glob": "*.cif"},
        ]
    )
    assert output_port_for_artifact(ports, "s", "x.cif").name == "cifs"
    # Same artifact_type but no glob match still resolves, to the first declaration.
    assert output_port_for_artifact(ports, "s", "x.bin").name == "pdbs"
    assert output_port_for_artifact(ports, "other", "x.pdb") is None
    assert output_port_for_artifact([], "s", "x.pdb") is None
