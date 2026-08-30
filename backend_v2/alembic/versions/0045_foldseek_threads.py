"""Foldseek passes --threads, now that the flag has been checked on the cluster.

0044 left this as the one uncomfortable declaration: Foldseek held 8 slots while its
command passed no thread argument, so the binary read the *host's* core count instead of
the reservation. 8 was not a match, only the closer of two wrong answers. The fix was
known - ``--threads "$BDA_CPUS"`` - and deliberately not written, because a flag that has
never been run cannot be verified from a laptop; that is exactly how 0039's dead ``seq``
parameter happened.

Checked on qm (2026-08-28, foldseek 10.941cd33 in ``/work/bme-sunzr/.conda/envs/bda-tools``)::

    $ foldseek easy-search --help
    common:
     --threads INT                   Number of CPU-cores used (all by default) [64]

Two things that reading could not have settled:

* ``--threads`` is under ``common:``, so it is accepted by ``easy-search`` and not only
  by the low-level modules that the wrapper calls.
* the bracketed default printed **64**, which is the login node's ``nproc`` - confirming
  the "all by default" wording means *the machine's* cores, with nothing in Foldseek
  consulting ``LSB_DJOB_NUMPROC``. On an 8-slot reservation the unpatched command would
  have started 64 threads.

So the command now passes ``--threads "$BDA_CPUS"``. The renderer takes ``-n``,
``span[ptile=...]`` and ``$BDA_CPUS`` from one number (``compute/scripts.py:declared_cpus``),
and exports it on all three backends, so the threads Foldseek starts are the slots LSF
reserved. The count stays 8; what changes is that 8 is now true.

Revision ID: 0045_foldseek_threads
Revises: 0044_slot_counts_match_cores
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0045_foldseek_threads"
down_revision: str | None = "0044_slot_counts_match_cores"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PLUGIN_KEY = "Foldseek"

#: Appended as a further continuation line, rather than substituted into a known flag, so
#: that a command whose other arguments have since been edited still gets it.
THREADS_ARG = ' \\\n  --threads "$BDA_CPUS"'

EVIDENCE_AFTER = (
    "Verified on qm 2026-08-28 (foldseek 10.941cd33): `foldseek easy-search --help` "
    "lists `--threads INT  Number of CPU-cores used (all by default)` under `common:`, "
    "and its printed default was 64 - the login node's nproc, not the reservation. The "
    "command now passes --threads \"$BDA_CPUS\", which the renderer sets from the same "
    "number as -n and span[ptile], so 8 threads run on the 8 reserved slots."
)

EVIDENCE_BEFORE = (
    "Structure search is genuinely parallel, but this command passes no --threads, "
    "so Foldseek reads the host core count rather than the reservation. 8 is the "
    'closer of the two available wrong answers; pass --threads "$BDA_CPUS" once '
    "the flag has been confirmed on the cluster."
)


def _rows(bind: sa.engine.Connection) -> list[sa.Row]:
    return list(
        bind.execute(
            sa.text("SELECT id, command, resources FROM model_plugins WHERE plugin_key = :key"),
            {"key": PLUGIN_KEY},
        ).fetchall()
    )


def _write(bind: sa.engine.Connection, row_id, command: str, resources: dict) -> None:
    bind.execute(
        sa.text(
            """
            UPDATE model_plugins
            SET command = :command,
                resources = CAST(:resources AS json),
                version = version + 1,
                updated_at = now()
            WHERE id = :id
            """
        ),
        {"id": row_id, "command": command, "resources": json.dumps(resources)},
    )


def upgrade() -> None:
    bind = op.get_bind()
    touched = 0
    for row in _rows(bind):
        command = row.command or ""
        if "foldseek easy-search" not in command or "--threads" in command:
            # Absent, replaced, or already carrying a thread count: leave it alone.
            continue
        resources = dict(row.resources or {})
        resources["cpus_evidence"] = EVIDENCE_AFTER
        _write(bind, row.id, command.rstrip() + THREADS_ARG, resources)
        touched += 1
    print(f"0045: Foldseek --threads written for {touched} plugin rows")


def downgrade() -> None:
    bind = op.get_bind()
    touched = 0
    for row in _rows(bind):
        command = row.command or ""
        if not command.endswith(THREADS_ARG):
            # Edited since; removing a --threads this migration did not add would be
            # worse than leaving it.
            continue
        resources = dict(row.resources or {})
        resources["cpus_evidence"] = EVIDENCE_BEFORE
        _write(bind, row.id, command[: -len(THREADS_ARG)], resources)
        touched += 1
    print(f"0045: Foldseek --threads removed from {touched} plugin rows")
