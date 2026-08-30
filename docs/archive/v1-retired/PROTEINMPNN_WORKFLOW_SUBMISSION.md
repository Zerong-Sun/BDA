# ProteinMPNN workflow submission contract

ProteinMPNN must be submitted through a workflow node so BDA can show queue
state, log tails, and collected outputs in the Jobs and Artifacts panels.

## Standard UI path

1. Open a project workflow route.
2. Select the `ProteinMPNN` node downstream of RFdiffusion.
3. Set node parameters in Node details:
   - `num_seq_per_target`: use `5` for the current sweet-protein round.
   - `pdb_path_chains`: designed chain, usually `A` for generated single-chain backbones.
   - `sampling_temp`: current sweet-protein setting is `0.2`.
   - `batch_size`: keep at `1` unless GPU memory has been checked.
4. Generate the script preview.
5. Submit from the node Jobs panel.
6. When the job finishes, sync results.

The remote LSF renderer now has a built-in ProteinMPNN script. It stages
upstream RFdiffusion backbone artifacts, runs `parse_multiple_chains.py`,
`assign_fixed_chains.py`, and `protein_mpnn_run.py`, then writes:

```text
output/manifest.json
output/sweetprotein_mpnn5_designs.fasta
output/proteinmpnn_scores.csv
output/proteinmpnn_run.json
```

`output/manifest.json` is the required BDA output contract. Without it the UI
cannot register sequence sets, score tables, or run records.

## Imported manual job

The earlier sweet-protein ProteinMPNN job was submitted outside the BDA node
job path, so it did not appear in the local Jobs table while it was queued or
running. The completed LSF job was:

```text
3860487
```

Remote output directory:

```text
/work/bme-sunzr/bda/proteinmpnn_sweetprotein_20260627/outputs_temp0.2_5seq
```

It generated 1000 sequences: 100 Monellin backbones x 5 sequences and 100
Brazzein backbones x 5 sequences.

After downloading the combined FASTA and manifest, run:

```bash
BDA_DB_PATH=backend/db/bda.sqlite3 BDA_COMPUTE_MODE=demo \
  backend/.venv/bin/python backend/scripts/register_sweet_protein_mpnn_results.py
```

That script splits the manual result by route and registers BDA jobs, artifacts,
and node metrics for both sweet-protein workflow routes.
