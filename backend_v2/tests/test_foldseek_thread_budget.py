"""0045 makes Foldseek's thread count and its slot reservation the same number.

The migration itself is careful about *whether* to patch a row (it skips a command that
already carries ``--threads``, and one that is no longer the registered Foldseek command
at all). What nothing checks is the property the patch exists for: that the number
Foldseek is told to start equals the number LSF was asked to reserve.

That property lives in two files at once - the migration appends ``--threads
"$BDA_CPUS"``, and ``compute/scripts.py`` decides what ``$BDA_CPUS`` is - so neither file
can be read alone to confirm it. Hence a test that renders the patched command and reads
the script.

Foldseek's own default is the *host's* core count: the installed build prints ``[64]``,
which is the login node's nproc. An unflagged command on an 8-slot reservation therefore
started 64 threads, which is the low-utilisation violation of D061 arriving from the
over-subscription side.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from backend_v2.app.compute.scripts import ScriptContext, declared_cpus, render_script


def _load_revision(name: str):
    """Load a revision by path: `0027_...` is not an importable module name."""
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"revision_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REGISTERED = _load_revision("0027_ip_and_physics_tools")
SLOTS = _load_revision("0044_slot_counts_match_cores")
THREADS = _load_revision("0045_foldseek_threads")

#: What the migration would store, applied the way `upgrade()` applies it.
PATCHED_COMMAND = REGISTERED.FOLDSEEK_COMMAND.rstrip() + THREADS.THREADS_ARG


def test_the_replaced_evidence_is_the_evidence_that_was_written() -> None:
    """``EVIDENCE_BEFORE`` is only meaningful if 0044 actually wrote that string.

    ``upgrade()`` overwrites ``cpus_evidence`` unconditionally, so a drift here is not
    a silent no-op - but ``downgrade()`` restores ``EVIDENCE_BEFORE``, and a drifted
    copy would quietly replace 0044's reasoning with a near-miss of it.
    """
    _, written_by_0044 = SLOTS.SLOTS["Foldseek"]
    assert THREADS.EVIDENCE_BEFORE == written_by_0044


def test_the_thread_count_and_the_reservation_are_one_number() -> None:
    """What Foldseek is told to start must equal what LSF reserved, at any declaration.

    Rendering rather than asserting on the string is the point: ``-n``, ``span[ptile]``
    and ``$BDA_CPUS`` are three writes of one number, and this is the only place the
    patched command and the renderer are read together.
    """
    resources = dict(REGISTERED.FOLDSEEK["resources"])

    for declared in (1, resources["cpus"]):
        script = render_script(
            ScriptContext(
                job_name="bda-foldseek",
                remote_dir="/work/bme-sunzr/bda/jobs/test",
                command=PATCHED_COMMAND,
                queue="v3-64",
                backend="lsf",
                staging_mode="ssh",
                runtime_mode="conda",
                container_image=REGISTERED.TOOLS_ENV,
                runtime_setup=list(REGISTERED.CONDA_SETUP),
                resources={**resources, "cpus": declared},
            )
        )
        assert f"#BSUB -n {declared}" in script
        assert f'#BSUB -R "span[ptile={declared}]"' in script
        assert f"export BDA_CPUS={declared}" in script
        # The export has to precede the command that spends it.
        assert script.index(f"export BDA_CPUS={declared}") < script.index('--threads "$BDA_CPUS"')

    assert declared_cpus(resources) == resources["cpus"]


def test_no_silent_fallback_is_written_into_the_thread_argument() -> None:
    """``${BDA_CPUS:-1}`` would run eight reserved slots at one thread and look fine.

    The renderer exports ``BDA_CPUS`` on every backend, so an unset variable means the
    command is running somewhere the renderer did not produce - which should fail loudly
    rather than silently pick a number.
    """
    assert "BDA_CPUS:-" not in THREADS.THREADS_ARG


def test_applying_the_patch_twice_would_be_refused() -> None:
    """``upgrade()`` skips a command that already carries a thread count.

    Re-running it must not append a second ``--threads``, which Foldseek would read as
    a duplicate flag rather than as the reservation.
    """
    assert "--threads" in PATCHED_COMMAND
    assert PATCHED_COMMAND.count("--threads") == 1
    # The guard `upgrade()` uses, evaluated against the already-patched command.
    assert not ("foldseek easy-search" in PATCHED_COMMAND and "--threads" not in PATCHED_COMMAND)
