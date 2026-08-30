"""Single source of truth for the script a job actually runs.

Preview and execution used to render independently: the preview endpoint returned
``#!/bin/sh`` plus the raw command, while LSF submitted a bash script with #BSUB
headers and manifest environment. A scientist reviewing the preview was therefore not
reviewing what ran. Both paths now call :func:`render_script`.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field

# Placeholder substituted into previews where a real job id is not known yet. Keeping
# it a fixed token is what lets a test assert preview and submission agree.
PREVIEW_JOB_ID = "PREVIEW"

# Parameters are exported under their own names so a plugin command reads naturally as
# "$num_designs". Restricting to lowercase keeps them clear of PATH, HOME, LD_* and the
# rest of the conventional environment.
_SAFE_PARAMETER_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def parameter_environment(parameters: dict) -> dict[str, str]:
    """Node parameters as environment values, keyed by variable name.

    Values are only ever *assigned*, never interpolated into the command, which is what
    keeps a free-text parameter - a SMILES string, a residue list - from being re-parsed
    as shell. Booleans become "1"/"" so an optional flag can be written as
    ``${flag:+--flag}`` and a false value simply disappears.

    Shared with the container backend so a plugin command reads the same parameter under
    the same name whichever backend runs it.
    """
    environment: dict[str, str] = {}
    for name in sorted(parameters):
        if not _SAFE_PARAMETER_NAME.fullmatch(name):
            continue
        value = parameters[name]
        if isinstance(value, bool):
            environment[name] = "1" if value else ""
        elif value is None:
            environment[name] = ""
        elif isinstance(value, int | float | str):
            environment[name] = str(value)
        # Structured values have no faithful shell form; the command should read them
        # from the input manifest instead.
    return environment


def _parameter_exports(parameters: dict) -> list[str]:
    """Export node parameters for the command to reference, shell-quoted."""
    return [f"export {name}={shlex.quote(value)}" for name, value in parameter_environment(parameters).items()]


@dataclass(frozen=True)
class ScriptContext:
    job_name: str
    remote_dir: str
    command: str
    queue: str
    backend: str
    runtime_mode: str = "container"
    container_image: str | None = None
    input_manifest_url: str = "$BDA_INPUT_MANIFEST_URL"
    output_manifest_url: str = "$BDA_OUTPUT_MANIFEST_URL"
    upload_wrapper: str = ""
    resources: dict = field(default_factory=dict)
    # Verbatim shell lines emitted before the command, declared by the plugin.
    runtime_setup: list[str] = field(default_factory=list)
    # Resolved node parameters, exported so a command can reference them as "$name".
    parameters: dict = field(default_factory=dict)
    # "ssh": the API has already staged inputs onto the shared filesystem and will
    # collect outputs the same way, so the job needs no network access at all.
    # "presigned": the job fetches and pushes against the object store itself.
    staging_mode: str = "presigned"


# Emitted at the end of an ssh-staged job. Walks the output directory and writes the
# manifest the collector reads. Inlined rather than installed as a cluster-side wrapper
# so that onboarding a cluster requires no software installation - only SSH access.
_MANIFEST_EMITTER = '''
python3 - "$BDA_OUTPUT_DIR" "$BDA_REMOTE_DIR/output-manifest.json" <<'BDA_EMIT_MANIFEST'
import hashlib, json, os, sys

output_dir, manifest_path = sys.argv[1], sys.argv[2]
entries = []
for root, _dirs, files in os.walk(output_dir):
    for name in sorted(files):
        path = os.path.join(root, name)
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        entries.append({
            "relative_path": os.path.relpath(path, output_dir),
            "filename": name,
            "size_bytes": os.path.getsize(path),
            "checksum_sha256": digest.hexdigest(),
        })
with open(manifest_path, "w") as handle:
    json.dump({"schema_version": "1", "outputs": entries}, handle)
print(f"bda: wrote manifest for {len(entries)} output(s)")
BDA_EMIT_MANIFEST
'''.strip()


def preview_context(node, plugin, backend: str, command: str, parameters: dict | None = None) -> ScriptContext:
    """Build the render inputs for a node that has not been submitted yet.

    Job-derived values (id, attempt, presigned URLs) are stand-ins, so a preview differs
    from the submitted script only in those tokens. Everything a reviewer cares about -
    directives, resources, runtime preamble, the command - is rendered by the same code
    that LSFAdapter uses.
    """
    from ..core.config import get_settings

    settings = get_settings()
    resources = plugin.resources if plugin and isinstance(plugin.resources, dict) else {}
    return ScriptContext(
        job_name=f"bda-{PREVIEW_JOB_ID}",
        remote_dir=f"{settings.lsf_remote_root.rstrip('/')}/jobs/{PREVIEW_JOB_ID}",
        command=command,
        queue=str(node.queue or settings.lsf_queue),
        backend=backend,
        runtime_mode=str(getattr(plugin, "runtime_mode", None) or "container"),
        container_image=node.container_image or (plugin.container_image if plugin else None),
        upload_wrapper=settings.lsf_upload_wrapper,
        resources=resources,
        runtime_setup=list(getattr(plugin, "runtime_setup", None) or []),
        parameters=parameters if parameters is not None else dict(node.parameters or {}),
    )


def render_script(ctx: ScriptContext) -> str:
    if ctx.backend == "lsf":
        return _render_lsf(ctx)
    if ctx.backend == "docker":
        return _render_docker(ctx)
    return _render_plain(ctx)


def declared_cpus(resources: dict) -> int:
    """Slots this plugin asks for. One unless it declares otherwise.

    A single number drives three things that must never disagree: ``-n``, ``span[ptile]``
    and the thread count the tool itself is told to use (``$BDA_CPUS``). Reading them all
    from here is what keeps them equal.
    """
    cpus = resources.get("cpus")
    return cpus if isinstance(cpus, int) and cpus > 0 else 1


def _resource_directives(resources: dict) -> list[str]:
    """Translate a plugin's declared resources into #BSUB directives."""
    directives: list[str] = []
    cpus = declared_cpus(resources)
    directives.append(f"#BSUB -n {cpus}")
    # ptile is slots PER HOST, so omitting it lets LSF scatter -n slots across -n hosts.
    # Every plugin here is single-node, and a scattered single-GPU job either stays PEND
    # on "Not enough hosts to meet the job's spanning requirement" or runs with its
    # threads on machines that cannot see each other. The hand-written jobs in this
    # project have always written the two together (qm-scripts/library/qm_job.py does the
    # same); this renderer emitted -n alone, so a plugin declaring 8 cpus produced a
    # directive set no reviewer of those jobs would have accepted.
    directives.append(f'#BSUB -R "span[ptile={cpus}]"')
    memory = resources.get("memory_gb")
    if isinstance(memory, int | float) and memory > 0:
        directives.append(f'#BSUB -R "rusage[mem={int(memory) * 1024}]"')
    gpu = resources.get("gpu")
    if gpu:
        count = resources.get("gpu_count") or 1
        directives.append(f'#BSUB -gpu "num={count}:mode=exclusive_process"')
    walltime = resources.get("walltime_minutes")
    if isinstance(walltime, int) and walltime > 0:
        directives.append(f"#BSUB -W {walltime}")
    return directives


def _render_lsf(ctx: ScriptContext) -> str:
    header = [
        "#!/bin/bash",
        f"#BSUB -J {ctx.job_name}",
        f"#BSUB -q {ctx.queue}",
        f"#BSUB -o {ctx.remote_dir}/stdout.log",
        f"#BSUB -e {ctx.remote_dir}/stderr.log",
        *_resource_directives(ctx.resources),
        "set -Eeuo pipefail",
    ]
    if ctx.staging_mode == "ssh":
        body = [
            f"export BDA_REMOTE_DIR={shlex.quote(ctx.remote_dir)}",
            f"export BDA_INPUT_DIR={shlex.quote(ctx.remote_dir + '/inputs')}",
            f"export BDA_INPUT_MANIFEST={shlex.quote(ctx.remote_dir + '/input-manifest.json')}",
            f"export BDA_OUTPUT_DIR={shlex.quote(ctx.remote_dir + '/outputs')}",
            f"export BDA_JOB_NAME={shlex.quote(ctx.job_name)}",
            f"export BDA_CPUS={declared_cpus(ctx.resources)}",
            'mkdir -p "$BDA_OUTPUT_DIR"',
            *_parameter_exports(ctx.parameters),
            *_runtime_preamble(ctx),
            ctx.command,
            _MANIFEST_EMITTER,
            "",
        ]
    else:
        body = [
            f"export BDA_INPUT_MANIFEST_URL={shlex.quote(ctx.input_manifest_url)}",
            f"export BDA_OUTPUT_MANIFEST_URL={shlex.quote(ctx.output_manifest_url)}",
            f"export BDA_UPLOAD_WRAPPER={shlex.quote(ctx.upload_wrapper)}",
            f"export BDA_JOB_NAME={shlex.quote(ctx.job_name)}",
            f"export BDA_CPUS={declared_cpus(ctx.resources)}",
            *_parameter_exports(ctx.parameters),
            *_runtime_preamble(ctx),
            ctx.command,
            "",
        ]
    return "\n".join([*header, *body])


def _render_docker(ctx: ScriptContext) -> str:
    """The equivalent `docker run` for review purposes.

    DockerAdapter drives the API directly rather than shelling out, so this is a
    faithful transcription of the call it makes, not a script that is itself executed.
    """
    argv = [
        "docker",
        "run",
        "--rm",
        "--name",
        ctx.job_name,
        "-e",
        f"BDA_INPUT_MANIFEST_URL={ctx.input_manifest_url}",
        "-e",
        f"BDA_OUTPUT_MANIFEST_URL={ctx.output_manifest_url}",
        # Same name the LSF script exports, so a command that passes its thread count
        # as "$BDA_CPUS" reads the same number whichever backend runs it.
        "-e",
        f"BDA_CPUS={declared_cpus(ctx.resources)}",
        *_docker_parameter_args(ctx),
        *_docker_resource_args(ctx.resources),
        ctx.container_image or "<container_image unset>",
    ]
    rendered = " ".join(shlex.quote(item) for item in argv)
    return f"#!/bin/sh\nset -eu\n{rendered} {ctx.command}\n"


def _docker_parameter_args(ctx: ScriptContext) -> list[str]:
    args: list[str] = []
    for name, value in parameter_environment(ctx.parameters).items():
        args.extend(["-e", f"{name}={value}"])
    return args


def _docker_resource_args(resources: dict) -> list[str]:
    args: list[str] = []
    cpus = resources.get("cpus")
    if isinstance(cpus, int | float) and cpus > 0:
        args.extend(["--cpus", str(cpus)])
    memory = resources.get("memory_gb")
    if isinstance(memory, int | float) and memory > 0:
        args.extend(["--memory", f"{int(memory)}g"])
    if resources.get("gpu"):
        args.extend(["--gpus", str(resources.get("gpu_count") or "all")])
    return args


def _render_plain(ctx: ScriptContext) -> str:
    return "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            f"export BDA_CPUS={declared_cpus(ctx.resources)}",
            *_parameter_exports(ctx.parameters),
            *_runtime_preamble(ctx),
            ctx.command,
            "",
        ]
    )


def _runtime_preamble(ctx: ScriptContext) -> list[str]:
    """Environment setup for non-container runtimes on HPC nodes.

    An explicit ``runtime_setup`` wins over the mode default, because a conda install
    belonging to another user is not on PATH and ``conda shell.bash hook`` would fail;
    such a site has to source the profile by absolute path.
    """
    if ctx.runtime_setup:
        return list(ctx.runtime_setup)
    if ctx.runtime_mode == "module" and ctx.container_image:
        return [f"module load {ctx.container_image}"]
    if ctx.runtime_mode == "conda" and ctx.container_image:
        return ['eval "$(conda shell.bash hook)"', f"conda activate {ctx.container_image}"]
    return []
