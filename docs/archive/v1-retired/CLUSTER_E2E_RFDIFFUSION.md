# RFdiffusion remote_lsf end-to-end runbook

This runbook verifies the workflow-integrated cluster path for BDA on the `qm` LSF cluster.

The first acceptance-tested route is the sweet-protein vertical slice: Monellin/Brazzein scaffold preparation, RFdiffusion backbone generation, ProteinMPNN sequence design, fold prediction, and Rosetta/interface scoring. Site owners may adapt queues, modules, wrapper paths, and license checks for their installation.

## Prerequisites

- Connected to campus network (cluster SSH reachable from the app host).
- `.env` configured:

```dotenv
BDA_COMPUTE_MODE=remote_lsf
BDA_LSF_SSH_HOST=qm
BDA_LSF_REMOTE_ROOT=/work/bme-sunzr/bda
BDA_LSF_DEFAULT_GPU_QUEUE=4v100-16-e5
BDA_LSF_DEFAULT_CPU_QUEUE=v3-64
BDA_LSF_PLUGIN_COMMANDS_JSON={}
CELERY_BROKER_URL=redis://localhost:6379/1
REDIS_URL=redis://localhost:6379/0
```

- SSH key auth to `qm` works: `ssh qm "bjobs -V"`
- RFdiffusion uses the built-in `plugin_rfdiffusion` LSF renderer. No generic
  `BDA_LSF_PLUGIN_COMMANDS_JSON` entry is required for this model.
- Target structure stored for the sweet-protein project (`proj_sweetprotein_rfdiffusion_100x2_160d28`) or a newly created sweet-protein project.
- Site-owner verification that model executables and licenses are available on the selected cluster environment.

## Steps

1. **Health check**
   - `GET /api/v1/compute/cluster-health`
   - Expect healthy SSH / queue visibility.

2. **Create workflow**
   - Open `/workflow?project=proj_sweetprotein_rfdiffusion_100x2_160d28`
   - Apply or inspect the sweet-protein route (`sweet_protein_design_route`) with RFdiffusion → ProteinMPNN → fold prediction → Rosetta/interface scoring.

3. **Script preview**
   - `POST /api/v1/workflow-node-runs/{node_run_id}/script-preview`
   - Human-review `submit.lsf` contents and input manifest paths.

4. **Submit**
   - `POST /api/v1/workflow-node-runs/{node_run_id}/submit-to-compute`
   - Record returned `job_id` and LSF `external_id`.

5. **Poll**
   - `GET /api/v1/jobs/{job_id}` or `POST /api/v1/jobs/{job_id}/sync`
   - Celery `bda.poll_job_status` should advance status while queued/running.

6. **Collect**
   - On `completed`, outputs appear under project artifacts/candidates.
   - `GET /api/v1/projects/{project_id}/candidates`

7. **Visualize**
   - Candidates page → MolStar structure viewer.

## Acceptance

- Sweet-protein RFdiffusion job completes on the real cluster.
- Downstream ready nodes can be scheduled by DAG orchestration or explicitly verified if an installation has not enabled automatic orchestration yet.
- Outputs are collected into the platform database/artifacts with lineage.
- Structures are viewable in the UI with provenance and fixture warnings absent.

## Notes

- Manual campus-network verification is required; automated CI cannot reach `qm`.
- Record job IDs and deviations in [`implementation-notes.md`](../implementation-notes.md).
- 2026-07-13 local verification from this Codex environment could not reach
  `qm` (`172.18.6.10:18188` timed out), so the real cluster completion
  acceptance item remains pending until run from the campus network.
