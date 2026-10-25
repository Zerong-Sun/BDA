# Compute targets

状态：活跃

最后核验：2026-10-24（Asia/Shanghai；账号授权与作业目标快照）

权威范围：本文标题所述主题；平台总览与成熟度以仓库根目录 `README.md` 为准。

数据来源：仓库内版本化代码、配置、测试与本文列明的来源。

替代关系：如正文未另行声明，则不取代其他权威文档。

How work reaches a machine, and how to add more machines later.

## The split

| Queue | Runs where | Why |
|---|---|---|
| `dispatch`, `poll`, `collect` | **Host process** | Needs a route to the compute cluster |
| `maintenance` | Container | Only needs database, Redis, object storage |
| `research`, `copilot` | Container | Only needs database, object storage, LLM endpoints |

The compute queues run on the host because the route to the cluster here is a host VPN,
and a container's network namespace does not inherit it. `bda-worker-v2-1` gets
`No route to host` for the cluster while the host reaches it over `utun*`.

This is a property of *this* network, not of the design. Where a worker container can
reach the cluster, run everything in compose and skip this document.

## Running the host worker

```bash
cp backend_v2/scripts/host-worker.env.example backend_v2/scripts/host-worker.env
# Configure a site-approved non-interactive credential reference, or an existing
# SSH session established manually by the account holder. Never put a password
# in a command, environment variable or repository.
```

Stop the containerised worker from consuming the compute queues, or jobs will land on
whichever worker grabs them first and the containerised one will fail:

```bash
docker-compose -f docker-compose.yml -f docker-compose.host-worker.yml up -d
```

Then verify and run:

```bash
backend_v2/scripts/run-host-worker.sh --check
backend_v2/scripts/run-host-worker.sh
```

`--check` includes cluster reachability and scheduler checks. Run it only after the
account holder has established and explicitly confirmed the session. It is not a
background connectivity monitor. Expired authentication must be restored manually;
an agent must not handle password or MFA prompts.

The worker uses Celery's solo pool: the SSH transport holds a live connection that does
not survive being forked into prefork children.

### Requires the VPN

There is no daemon supervision here on purpose — the cluster route is manual, so the
worker is manual too. If the VPN drops, `--check` reports `Cluster reachable  FAIL` and
in-flight jobs stall rather than fail; they resume when connectivity returns, and
`reap_stale_jobs` fails anything past its deadline.

## Adding another cluster or a cloud queue

Two seams, neither of which requires touching the compute module.

### 1. A different scheduler

Register an adapter at startup:

```python
from backend_v2.app.compute.adapters import register_adapter

class SlurmAdapter:
    def __init__(self, target: dict | None = None) -> None: ...
    def ensure_submitted(self, job) -> str: ...
    def status(self, job, external_id): ...
    def cancel(self, external_id) -> bool: ...
    def collect(self, job, external_id) -> list[dict]: ...

register_adapter("slurm", SlurmAdapter)
```

`SubmissionCreate.compute_backend` validates against the registry at request time, so
the new name is accepted immediately — the API schema does not enumerate backends.

The same shape covers cloud batch services: `ensure_submitted` creates the remote job,
`status` maps the provider's states onto `queued/running/succeeded/failed`, and
`collect` returns entries pointing at object storage.

`status` receives the job, not just the provider's id, because a scheduler that has
already discarded a finished job can only be judged by what the job left behind — LSF
expires jobs from `bjobs` within the hour on some sites. When a backend genuinely cannot
answer, return `unknown`: it is non-terminal, so the job keeps polling under its own
`timeout_at` instead of being recorded as a failure it did not suffer.

### 2. A second target for a scheduler you already support

Adapters accept an optional `target` dict that overrides global settings key by key:

```python
adapter_for("lsf", {
    "lsf_ssh_host": "cluster-b.example.edu",
    "lsf_queue": "gpu-a100",
    "lsf_remote_root": "/scratch/bda",
    "lsf_ssh_password_ref": "file:/run/secrets/cluster-b",
})
```

So a second cluster is configuration, not code. The `compute_nodes` registry table is
the intended home for these dicts — it already carries `backend`, `queue` and `labels`.
Routing a job to a specific node is not wired up yet; when it is, it reads that row and
passes it here.

### What an adapter must guarantee

- `ensure_submitted` is idempotent for a given job and attempt. The LSF adapter looks up
  its deterministic job name before submitting, so a retried dispatch does not double-run
  the work.
- `collect` returns checksummed entries whose `object_key` sits under
  `jobs/<job_id>/attempt-<n>/outputs/`. Checksums are re-verified before artifacts are
  registered.
- Status maps onto the job state machine in `compute/service.py`; anything unrecognised
  should map to `failed` with the raw state as the error, never silently to `succeeded`.

## Data movement

See [PLUGIN_INTERFACE.md](PLUGIN_INTERFACE.md#3b-cluster-staging-modes). In short: with
`BDA_V2_LSF_STAGING_MODE=ssh` (the default) the worker stages inputs and retrieves
outputs itself, and the compute node needs no network access and no installed software.
Only one direction of connectivity is required — worker to cluster.

## Account assignment and multiple users

A BDA project role does not authorize use of the deployment's LSF account.
`BDA_V2_LSF_SUBMITTER_USER_IDS` is an explicit JSON list of BDA user UUIDs allowed to
submit through that account. Public defaults to no users, including administrators;
Private defaults to administrators only when the list is empty. A nonempty list is
authoritative for both deployments. Apply the same configuration to API and workers.
Preflight, script preview, workflow submission, compute-draft confirmation and retry
enforce this boundary. Registration and organization membership cannot enlarge it.

The allowlist grants use of one deployment account. It does not connect a student's
personal cluster identity. Until personal connector routing is implemented, use a
separate deployment and compute worker for each personal account, or an explicitly
approved laboratory service account whose site terms permit sharing. Do not add
students to the list while telling them jobs will run under their personal identities.

New LSF jobs freeze their SSH host/user/port, remote root, queue, staging mode and
credential references in an internal target snapshot. Dispatch, polling, collection and
cancellation use that snapshot after deployment configuration changes. Credential values
are never copied. The script-review fingerprint covers the same identity. Retries after
a target change, and retries of legacy jobs without a target snapshot, require a new
reviewed workflow. Legacy tracking retains its existing adapter behavior.

The personal-connector design and release acceptance boundary are recorded in
[Public release readiness](PUBLIC_RELEASE_READINESS.md). Cluster qualification requires
the account holder's session and site-specific execution evidence.
