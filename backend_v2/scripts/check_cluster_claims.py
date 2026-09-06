#!/usr/bin/env python3
"""Fail the build when a job script claims something about the cluster that nothing checks.

Every gate in this directory verifies a repository artifact against another repository
artifact. Nothing verified a job script's claims against what the scheduler actually does,
and on 2026-09-04 that cost about seven GPU-hours: three stage-1 jackhmmer jobs carried the
comment "No GPU is requested - holding an A100 idle through it is the low-utilisation
pattern the cluster rules forbid" while running on ``2v100-32-e5``, whose queue-level
``GPU_REQ: num=1:mode=exclusive_process`` is merged into every job that lands there. The
scripts requested no GPU and were given one anyway. The comment could not fail a build,
so it did not.

The queue is deliberately not in this repository - it is site deployment configuration,
chosen on the bsub command line against a reviewed ``QUEUE_SET_AT_SUBMIT`` placeholder. So
a static checker cannot know which queue a stage will land on, and asking it to is the
wrong shape. What it can require is that **a stage claiming to need no GPU carries a
runtime assertion that it got none**, which turns an unverifiable comment into a job that
kills itself when the claim is false.

Three checks, over every ``#BSUB``-bearing script literal these generators emit:

1. **A no-GPU claim must be self-verifying.** A stage that says it needs no GPU and
   requests none must assert on ``CUDA_VISIBLE_DEVICES``, which LSF sets for jobs it gives
   a GPU to. This is the check that would have caught the seven hours.
2. **Cores, span and threads must agree.** ``-n N`` must equal ``span[ptile=N]`` and any
   thread count the stage exports. CLAUDE.md states this rule and
   ``check_plugin_cpu_declarations.py`` enforces it for the plugin registry; the research
   generators were never covered.
3. **A loop over staged inputs must count its product.** A stage that iterates
   ``dir/*.json`` must compare a count against an expected number. This is what stands
   between the pipeline and a silently wrong directory - macOS ``tar`` writes ``._name``
   sidecars that ``sha256sum -c`` cannot see, because the manifest was built where they do
   not exist, and on 2026-09-03 that turned 64 panel inputs into 128.

The private research overlay holds these generators and is absent from the public
checkout, so this skips rather than fails when it is not there - the same contract
``check_decision_coverage.py`` uses.

    PYTHONPATH=. backend_v2/.venv/bin/python backend_v2/scripts/check_cluster_claims.py

``--live <job-id>`` additionally asks the scheduler whether a running job was given a GPU
its script never requested. It runs **on the login node**, where ``bjobs`` exists - copy
this file there and run it - so it is for the operator at submission time, not for CI.
Verified against both shapes: a CPU stage on a queue with no ``GPU_REQ`` reports
``gpu_allocated=False gpu_requested=False``, and an AF3 panel that asks for a GPU reports
``True/True``. The failing combination is allocated-but-not-requested, which is what the
seven GPU-hours looked like.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

#: --live is meant to be run on the login node, where this file gets copied to whatever
#: path is convenient, so the repository root must not be assumed to exist above it.
_HERE = Path(__file__).resolve()
REPOSITORY_ROOT = _HERE.parents[2] if len(_HERE.parents) > 2 else _HERE.parent
SEARCH_ROOTS = (
    REPOSITORY_ROOT / "private/legacy-overlay/backend_v2/scripts",
    REPOSITORY_ROOT / "backend_v2/scripts",
)

#: Phrases a stage uses to claim it needs no GPU. Matched against the script literal only,
#: not the surrounding Python, so a module docstring discussing GPUs is not a claim.
NO_GPU_CLAIM = re.compile(
    r"No GPU|no GPU is requested|gpus=0|holding an A100|holding a GPU|不请求 *GPU|0 *GPU",
    re.IGNORECASE,
)
#: LSF sets CUDA_VISIBLE_DEVICES for jobs it allocates a GPU to, so a CPU-only stage can
#: refuse to run when it is set. Any exit within a few lines of the variable counts.
GPU_GUARD = re.compile(r"CUDA_VISIBLE_DEVICES(?:.*\n){0,3}?.*exit", re.MULTILINE)

BSUB_CORES = re.compile(r"^#BSUB\s+-n\s+(\S+)", re.MULTILINE)
BSUB_SPAN = re.compile(r"^#BSUB\s+-R\s+\"span\[ptile=([^\]]+)\]\"", re.MULTILINE)
BSUB_GPU = re.compile(r"^#BSUB\s+-gpu", re.MULTILINE)
BSUB_NAME = re.compile(r"^#BSUB\s+-J\s+(\S+)", re.MULTILINE)
#: Thread counts a stage hands to the tool it runs. Each must equal the slot request.
THREADS = re.compile(r"(?:--cpu|OMP_NUM_THREADS|--nthreads|-nt)[= ](\S+)")

#: AF3's data pipeline is the exception to "-n equals the thread count", and getting this
#: wrong is silent. ``_get_protein_msa_and_templates`` in alphafold3/data/pipeline.py runs
#: its four database searches inside one ``ThreadPoolExecutor(max_workers=4)``, handing each
#: subprocess ``--cpu <n_cpu>``. So a stage with ``--jackhmmer_n_cpu=2`` starts **eight**
#: worker threads, not two. Measured on 2026-09-05 in 4246366.err: four concurrent
#: ``Launching subprocess ... jackhmmer ... --cpu 2`` lines for a single chain. That job
#: requested ``-n 2`` and oversubscribed its slots fourfold; job 4245072 requested ``-n 8``
#: with ``--jackhmmer_n_cpu=8`` and oversubscribed by the same factor. Both passed the
#: original form of this check, because it compared -n against the per-process flag.
AF3_SEARCH_THREADS = re.compile(r"(?:--jackhmmer_n_cpu|--nhmmer_n_cpu)[= ](\S+)")
AF3_RUNNER = re.compile(r"run_alphafold\.py")
AF3_INFERENCE_ONLY = re.compile(r"--norun_data_pipeline")
#: max_workers in that executor. Four searches: uniref90, mgnify, small_bfd, uniprot.
AF3_CONCURRENT_SEARCHES = 4

#: Seven stages already ran oversubscribed, and five of them belong to arms that are
#: finished and cited in decision records. Rewriting their generators would make the
#: repository stop reproducing what was actually submitted, which is worse than the
#: defect. So a stage may carry a written acknowledgement **in the Python module, not in
#: the script literal** - keeping the rendered job byte-identical to the one that ran:
#:
#:     # CLUSTER-CLAIMS-ACK <stage-name>: ran this way as 4231234; kept for provenance
#:
#: The reason must name a job id, so this cannot be used to wave through a stage that has
#: not run yet. New stages get the arithmetic right instead.
ACK = re.compile(r"^#\s*CLUSTER-CLAIMS-ACK\s+(\S+?):\s*(.+)$", re.MULTILINE)
ACK_JOB_ID = re.compile(r"\b\d{7}\b")

#: A shell comment is prose, not a directive: a stage that *explains* "--cpu 2" in a
#: comment is not running two threads, and scanning the comment as if it were code turned
#: the track-a fix into two false failures the first time it was tested. #BSUB and the
#: shebang are directives despite the leading #, so they survive. The no-GPU claim is
#: deliberately matched against the full text - there, prose is exactly what is checked.
COMMENT_LINE = re.compile(r"^[ \t]*#(?!BSUB\b|!).*$", re.MULTILINE)
#: Plain shell assignments, so `--jackhmmer_n_cpu=$JACKHMMER_N_CPU` resolves the way an
#: f-string placeholder already did. Without this every parameterised script reports "?".
SHELL_ASSIGN = re.compile(r"^[ \t]*(\w+)=([\w.]+)[ \t]*$", re.MULTILINE)

INPUT_LOOP = re.compile(r"for\s+\w+\s+in\s+[^\n]*?/\*\.json")
#: A comparison of a computed count against a literal, in any of the shapes these
#: scripts use: [ "$n" = 6 ], [ "$input_count" = 64 ], test "$n" -eq 3.
#: `test` and `[` are the same builtin, and a generator that writes the `test` form was
#: reported as having no guard at all - so both spellings have to be here or the check
#: fails scripts for their choice of syntax.
COUNT_GUARD = re.compile(
    r"(?:\[|\btest\b)\s*\"?\$\{?\w+\}?\"?\s*(?:=|==|-eq)\s*\S+?\s*\]?"
    r"|\bwc -l\b[^\n]*\n[^\n]*\bexit\b"
)


def literals_with_bsub(path: Path) -> list[tuple[str, str]]:
    """Every string literal in the module that renders an LSF script.

    f-string placeholders are resolved against module-level constants where those are
    plain literals, so ``#BSUB -n {JACKHMMER_N_CPU}`` is compared as ``-n 8``. A
    placeholder that cannot be resolved becomes ``?``, which never equals another value
    and therefore reports rather than passing silently.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = str(node.value.value)

    def render(node: ast.AST) -> str:
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.JoinedStr):
            out = []
            for part in node.values:
                if isinstance(part, ast.Constant):
                    out.append(str(part.value))
                elif isinstance(part, ast.FormattedValue) and isinstance(part.value, ast.Name):
                    out.append(constants.get(part.value.id, "?"))
                else:
                    out.append("?")
            return "".join(out)
        return ""

    texts: list[str] = []
    for literal in ast.walk(tree):
        if isinstance(literal, (ast.Constant, ast.JoinedStr)):
            text = render(literal)
            if "#BSUB" in text:
                texts.append(text)
    # An f-string's own Constant pieces are walked too, so a stage is found several times
    # nested inside itself. Keep only the outermost: drop any text contained in another.
    outermost = [t for t in texts if not any(t != other and t in other for other in texts)]
    found, seen = [], set()
    for text in outermost:
        if text in seen:
            continue
        seen.add(text)
        name = BSUB_NAME.search(text)
        found.append((name.group(1) if name else "<unnamed>", text))
    return found


def acknowledgements(module_text: str) -> dict[str, str]:
    """Stage name -> reason, for mismatches deliberately kept as they ran."""
    # A job name carrying a job-array suffix is quoted in the #BSUB line, so normalise
    # both sides rather than making the author guess which form to write.
    return {name.strip('"'): reason.strip() for name, reason in ACK.findall(module_text)}


def check_stage(path: Path, name: str, body: str, acked: dict[str, str] | None = None) -> list[str]:
    where = f"{path.relative_to(REPOSITORY_ROOT)}::{name}"
    problems: list[str] = []
    ack = (acked or {}).get(name.strip('"'))
    if ack is not None and not ACK_JOB_ID.search(ack):
        problems.append(f"{where}: CLUSTER-CLAIMS-ACK names no job id, so it cannot be an "
                        "acknowledgement of something that ran; fix the stage instead")
        ack = None

    requests_gpu = bool(BSUB_GPU.search(body))
    claims_no_gpu = bool(NO_GPU_CLAIM.search(body))
    if claims_no_gpu and not requests_gpu and not GPU_GUARD.search(body):
        problems.append(
            f"{where}: claims it needs no GPU and requests none, but never asserts it got none. "
            "The queue is chosen at submit time and can merge its own GPU_REQ into the job - that is "
            "how 4235698 and 4236768 held a V100 through a jackhmmer search. Add a guard that exits "
            'when CUDA_VISIBLE_DEVICES is set, e.g. [ -z "${CUDA_VISIBLE_DEVICES:-}" ] || exit 9'
        )

    cores = BSUB_CORES.search(body)
    span = BSUB_SPAN.search(body)
    if cores and span and cores.group(1) != span.group(1):
        problems.append(f"{where}: -n {cores.group(1)} but span[ptile={span.group(1)}]; "
                        "ptile is slots per host, so these must be equal or the job scatters")
    code = COMMENT_LINE.sub("", body)
    shell_vars = dict(SHELL_ASSIGN.findall(code))

    def thread_value(raw: str) -> str | None:
        thread = raw.strip('"\'').rstrip(":;,)").lstrip("$").strip("{}")
        if thread.startswith("LSB_DJOB_NUMPROC"):
            return None
        return shell_vars.get(thread, thread)

    if cores:
        for raw in set(THREADS.findall(code)):
            thread = thread_value(raw)
            if thread is not None and thread != cores.group(1):
                problems.append(f"{where}: -n {cores.group(1)} but the stage runs {thread} threads; "
                                "a tool told to use a different count than the scheduler reserved is "
                                "what draws the low-utilisation mail")

        runs_af3_search = bool(AF3_RUNNER.search(code)) and not AF3_INFERENCE_ONLY.search(code)
        for raw in set(AF3_SEARCH_THREADS.findall(code)):
            thread = thread_value(raw)
            if thread is None:
                continue
            if not runs_af3_search:
                expected = thread
            else:
                try:
                    expected = str(int(thread) * AF3_CONCURRENT_SEARCHES)
                except ValueError:
                    expected = "?"
            if expected != cores.group(1):
                if ack is not None:
                    print(f"note {where}: -n {cores.group(1)} vs {expected} AF3 worker "
                          f"threads, acknowledged - {ack}")
                    continue
                problems.append(
                    f"{where}: -n {cores.group(1)} but AF3's data pipeline starts "
                    f"{AF3_CONCURRENT_SEARCHES} concurrent searches at --cpu {thread}, so this "
                    f"stage runs {expected} worker threads. AF3 does not use the flag as a total: "
                    "_get_protein_msa_and_templates submits uniref90, mgnify, small_bfd and "
                    "uniprot into one ThreadPoolExecutor(max_workers=4). Set -n to "
                    f"4 x --jackhmmer_n_cpu (here -n {expected}), or lower the flag"
                )

    if INPUT_LOOP.search(code) and not COUNT_GUARD.search(code):
        problems.append(
            f"{where}: loops over staged inputs without comparing a count against an expected number. "
            "sha256sum -c cannot see files the manifest does not list, which is how 64 panel inputs "
            "became 128"
        )
    return problems


def live(job_id: str) -> int:
    """Ask the scheduler whether a running job was given a GPU its script never asked for."""
    try:
        record = subprocess.run(["bjobs", "-l", job_id], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"cannot reach the scheduler: {exc}", file=sys.stderr)
        return 2
    if record.returncode != 0:
        print(record.stderr.strip() or f"bjobs -l {job_id} failed", file=sys.stderr)
        return 2
    flat = " ".join(record.stdout.split())
    allocated = "GPU REQUIREMENT DETAILS" in flat or "ngpus_physical" in flat
    requested = "#BSUB -gpu" in flat
    if allocated and not requested:
        print(f"job {job_id}: the queue attached a GPU to a job that never requested one", file=sys.stderr)
        print(f"  {flat[flat.find('GPU REQUIREMENT DETAILS'):][:200]}", file=sys.stderr)
        return 1
    print(f"job {job_id}: gpu_allocated={allocated} gpu_requested={requested}; consistent")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", metavar="JOB_ID", help="ask the scheduler about one running job")
    args = parser.parse_args()
    if args.live:
        return live(args.live)

    roots = [root for root in SEARCH_ROOTS if root.is_dir()]
    if not roots:
        print("no job-script directory present; nothing to check")
        return 0

    problems: list[str] = []
    stages = 0
    for root in roots:
        for path in sorted(root.glob("*.py")):
            if path.name == Path(__file__).name:
                continue
            try:
                literals = literals_with_bsub(path)
            except SyntaxError as exc:
                problems.append(f"{path.relative_to(REPOSITORY_ROOT)}: cannot parse ({exc})")
                continue
            acked = acknowledgements(path.read_text(encoding="utf-8"))
            for name, body in literals:
                stages += 1
                problems.extend(check_stage(path, name, body, acked))

    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    print(f"cluster claims: {stages} LSF stage(s) checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
