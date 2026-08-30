"""Ask for the cores a tool actually uses, and say why the number is what it is.

Registered plugins declared ``cpus`` of 4, 8 and 16. Nothing in this repository
supported those numbers: the commands pass no thread or worker flag, so each tool ran on
its own default while LSF reserved the declared count.

This project treats the resulting low-utilisation inspection mail as a violation, not a
notice, and has already paid for it once. Jobs ``4167123``/``4167124`` inherited ``-n 4``
from ``4140800`` and were killed in PEND under D061; the replacement ``4167148`` then
measured **CPU PEAK 1.00 / average efficiency 68.68 %**, which is the direct evidence
that ``boltz predict`` drives one GPU and one core. Every hand-written job in the project
has written ``-n 1``/``ptile=1`` since.

So the rule the migration applies is D061's: **one slot unless something in the
repository says otherwise**, and the something has to be nameable. Each entry below
carries ``cpus_evidence`` for exactly that reason - a bare number cannot be reviewed, and
the next person to raise one should have to write down what they measured or which flag
they read. ``check_plugin_cpu_declarations.py`` fails the build when a plugin asks for
more than one slot without it.

Not changed here:

* **AlphaFold2** keeps 8. ``qm-scripts/library/catalog.json`` - generated from the
  upstream entrypoint - lists ``jackhmmer_n_cpu``, ``hhsearch_n_cpu`` and
  ``hmmsearch_n_cpu``, whose upstream default is 8. The reservation matches what the
  MSA stage will start.
* **Foldseek** keeps 8, and it is the one entry that stays uncomfortable. ``foldseek
  easy-search`` in this command passes no thread argument, and Foldseek's own default is
  the host's core count rather than the reserved slot count - so 8 is not *matched*, it
  is merely closer than 1 would be. Lowering it to 1 makes the mismatch worse, not
  better. The fix is ``--threads "$BDA_CPUS"``, and it needs one verified ``--help`` on
  the cluster first; guessing a flag into a command that only ever runs where nobody can
  test it is how the ``seq`` parameter of 0039 happened.

The renderer half of this landed with it: ``compute/scripts.py`` now emits
``span[ptile=N]`` beside ``-n N`` and exports ``$BDA_CPUS``, so the three numbers cannot
drift apart again.

Revision ID: 0044_slot_counts_match_cores
Revises: 0043_durable_agent_runs
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0044_slot_counts_match_cores"
down_revision: str | None = "0043_durable_agent_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: plugin_key -> (slots it should hold, why that number).
#: A key absent from the database is skipped: AlphaFold 3, Boltz and Chai-1 entered the
#: registry through the v1 import rather than through a migration, so a database built
#: only from migrations legitimately has no row for them.
SLOTS: dict[str, tuple[int, str]] = {
    "Boltz": (
        1,
        "Measured: job 4167148 reported CPU PEAK 1.00 and 68.68% average efficiency on "
        "one slot. `boltz predict` drives the GPU; the command passes neither "
        "--num_workers nor --preprocessing_threads (D061).",
    ),
    "Chai-1": (
        1,
        "`chai-lab fold` exposes no thread or worker option in the upstream parameter "
        "list (qm-scripts/library/catalog.json), and the command passes none.",
    ),
    "BindCraft": (
        1,
        "bindcraft.py takes --settings/--filters/--advanced only; no worker count is "
        "exposed upstream and none has been measured. Raise it from a measurement, not "
        "from the length of the pipeline.",
    ),
    "RFdiffusion3": (
        1,
        "Diffusion inference on one GPU; the engine config exposes no thread count.",
    ),
    "superfold": (
        1,
        "The superfold wrapper takes no thread or worker argument (see the command "
        "registered by 0028); it runs AlphaFold2 weights on one GPU. The 2 it carried "
        "was never traced to anything.",
    ),
    "AlphaFold 3": (
        8,
        "Upstream exposes --jackhmmer_n_cpu and --nhmmer_n_cpu with a default of 8, and "
        "the hand-written control job 4186532 reserved -n 8 to match "
        "--jackhmmer_n_cpu. 16 matched nothing.",
    ),
    "AlphaFold2": (
        8,
        "Upstream exposes jackhmmer_n_cpu / hhsearch_n_cpu / hmmsearch_n_cpu, default 8; "
        "the MSA stage starts that many.",
    ),
    "Foldseek": (
        8,
        "Structure search is genuinely parallel, but this command passes no --threads, "
        "so Foldseek reads the host core count rather than the reservation. 8 is the "
        "closer of the two available wrong answers; pass --threads \"$BDA_CPUS\" once "
        "the flag has been confirmed on the cluster.",
    ),
    "APBS+PDB2PQR": (
        1,
        "pdb2pqr30 and apbs are invoked without any thread option in this command.",
    ),
    "US-align": (1, "Single-threaded pairwise alignment."),
    "RFdiffusion": (1, "Diffusion inference on one GPU; no thread count is exposed."),
    "ProteinMPNN": (1, "Sequence design on one GPU; no thread count is exposed."),
    "Rosetta": (
        1,
        "The reviewed binary is the non-MPI `.default.linuxgccrelease` build, which is "
        "serial by construction.",
    ),
    "proteinhunter_boltz": (
        1,
        "Wraps `boltz predict`; the same measurement that fixed Boltz applies.",
    ),
}


def _apply(mapping: dict[str, dict]) -> int:
    """Merge the given resource keys into each plugin row, leaving the rest alone."""
    bind = op.get_bind()
    touched = 0
    for plugin_key, changes in mapping.items():
        rows = bind.execute(
            sa.text("SELECT id, resources FROM model_plugins WHERE plugin_key = :key"),
            {"key": plugin_key},
        ).fetchall()
        for row in rows:
            resources = dict(row.resources or {})
            resources.update(changes)
            if changes.get("cpus_evidence") is None:
                resources.pop("cpus_evidence", None)
            bind.execute(
                sa.text(
                    """
                    UPDATE model_plugins
                    SET resources = CAST(:resources AS json),
                        version = version + 1,
                        updated_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": row.id, "resources": json.dumps(resources)},
            )
            touched += 1
    return touched


def upgrade() -> None:
    touched = _apply(
        {key: {"cpus": slots, "cpus_evidence": why} for key, (slots, why) in SLOTS.items()}
    )
    print(f"0044: slot counts and their evidence written for {touched} plugin rows")


def downgrade() -> None:
    """Restore the counts as they stood at 0043 and drop the evidence field.

    Only the keys this migration wrote are restored; a row whose resources were changed
    for another reason in between keeps that change.
    """
    previous = {
        "Boltz": 8,
        "Chai-1": 8,
        "BindCraft": 16,
        "RFdiffusion3": 4,
        "superfold": 2,
        "AlphaFold 3": 16,
        "AlphaFold2": 8,
        "Foldseek": 8,
        "APBS+PDB2PQR": 4,
        "US-align": 1,
        "RFdiffusion": 1,
        "ProteinMPNN": 1,
        "Rosetta": 1,
        "proteinhunter_boltz": 1,
    }
    touched = _apply({key: {"cpus": cpus, "cpus_evidence": None} for key, cpus in previous.items()})
    print(f"0044: slot counts restored for {touched} plugin rows")
