# BDA Implementation Notes

Deviation log for the End-to-End Loop Hardening plan. Review before each commit.

## 2026-07-07 — Execution start

| Field | Content |
|-------|---------|
| Original plan | Stage 0 framing decisions locked; begin Stage 1+ |
| What happened | Started implementation per attached plan |
| Decision | Follow plan stage order with Batch A then B then C |
| Reason | User requested full plan execution |
| Risk | Stage 4 RFdiffusion E2E requires campus network at verification time |
| Needs human confirmation | Stage 4 live cluster run when off-campus |

## 2026-07-07 — Stage 4 cluster E2E

| Field | Content |
|-------|---------|
| Original plan | Run RFdiffusion on `qm` and collect outputs in UI |
| What happened | Added [`docs/CLUSTER_E2E_RFDIFFUSION.md`](docs/CLUSTER_E2E_RFDIFFUSION.md) runbook; code paths unified but live job not executed in this session |
| Decision | Defer manual cluster verification to campus-network window |
| Reason | Agent environment cannot reach `qm` from off-campus |
| Risk | Unverified plugin wrapper / queue config until human runs runbook |
| Needs human confirmation | Yes — execute runbook on campus network and record job IDs |

## 2026-07-13 — Stage 4 retry

| Field | Content |
|-------|---------|
| Original plan | Run RFdiffusion on `qm` and collect outputs in UI |
| What happened | Rechecked remote_lsf config and retried read-only cluster access; `ssh qm bjobs -V` timed out against `172.18.6.10:18188` from the current environment. Local RFdiffusion/LSF render, preflight, collection, and jobs-router regression tests passed. |
| Decision | Keep live RFdiffusion completion pending; do not substitute local fixtures for the real cluster acceptance item |
| Reason | Stage 4 acceptance requires a real LSF job and output collection from `qm`, which is network-blocked here |
| Risk | Queue availability, RFdiffusion environment path, and remote output transfer remain unverified until the campus-network run |
| Needs human confirmation | Yes — run `docs/CLUSTER_E2E_RFDIFFUSION.md` from campus/VPN and record `job_id` plus LSF `external_id` |

## 2026-07-07 — Streaming implementation

| Field | Content |
|-------|---------|
| Original plan | Real token streaming via `provider.stream()` after tool rounds |
| What happened | `streaming.py` uses `prepare_llm_conversation()` then `provider.stream()`; rule-based mode streams char-by-char |
| Decision | Tool-round status events emitted from completed `tool_results` list |
| Reason | Minimal refactor of `service.py` while preserving tool loop correctness |
| Risk | Status events appear after tools finish, not live per tool |
| Needs human confirmation | No |

## 2026-07-13 — Stage 5 streaming status pass

| Field | Content |
|-------|---------|
| Original plan | Make Copilot streaming truthful and visible after tool rounds |
| What happened | Preserved `tool:*` SSE status events through the frontend API client, surfaced the active tool in the Copilot loading state, and added focused frontend coverage for tool-status streaming |
| Decision | Keep the current backend tool-round sequencing, but stop hiding tool status behind generic thinking UI |
| Reason | The existing service emits tool status events after completed tool rounds; showing them clearly improves traceability without broad Copilot refactoring |
| Risk | Tool statuses still represent completed tool rounds, not live per-tool progress inside `prepare_llm_conversation()` |
| Needs human confirmation | No |

## 2026-07-08 — Verification and optimization pass

| Field | Content |
|-------|---------|
| Original plan | Validate hardened features and optimize UX |
| What happened | Fixed 3 backend test regressions; added `test_copilot_stream.py`; improved Copilot degraded-mode banner (config + session); SSE status parsing for `tool:*` events; MSW mock for `/copilot/config` |
| Decision | Stream tests use in-memory SQLite to avoid module DB lock |
| Reason | `db_connection` fixture conflicted with module-scoped `ensure_db` |
| Risk | Full backend pytest suite takes ~7–8 minutes locally |
| Needs human confirmation | Stage 4 campus cluster E2E still manual |

## 2026-07-08 — SQLite pool lock fix

| Field | Content |
|-------|---------|
| Original plan | Full backend pytest suite should pass reliably |
| What happened | `test_confirm_cluster_draft_submits_exact_saved_script` left an uncommitted write txn on a pooled connection, causing `database is locked` in later API tests |
| Decision | `pool.release()` rolls back before returning connections; cluster draft test explicitly commits |
| Reason | Pooled connections must not retain write locks across tests |
| Risk | Low — API paths already commit via `get_connection()` dependency |
| Needs human confirmation | No |

## 2026-07-13 — Stage 6 focused UX and visualization

| Field | Content |
|-------|---------|
| Original plan | Replace page-derived progress with readiness state; repair mobile navigation/action semantics; add target/candidate visualization overlays; make Mol* genuinely lazy-loaded; add vertical-slice and failure-path browser-facing tests |
| What happened | Workflow progress now gates the supported path on `target_readiness.ready_for_workflow`; mobile primary navigation is reachable; target and candidate structure panels expose chain-role legends, missing hotspot/contact evidence, and provenance instead of implying uncomputed evidence exists; runtime imports no longer pull the pdb-viewer barrel into the main bundle; frontend vertical-slice and retry-path tests were added |
| Decision | Treat confirmed hotspots and interface-contact tables as unavailable until backend data actually links them; show explicit recovery links to Target intelligence instead of fake-complete overlays |
| Reason | A non-expert should understand what is confirmed, what is inferred, and what action restores the path without mistaking model/UI hints for experimental or computed evidence |
| Risk | True end-to-end browser automation is still not configured; the current coverage is Vitest/jsdom browser-facing UI coverage plus production build chunk verification |
| Needs human confirmation | Manual smoke on a phone-sized viewport and later Stage 7 approval only after the vertical slice is accepted |

## 2026-07-13 — “What to fix first” finish pass

| Field | Content |
|-------|---------|
| Original plan | Finish the P0/P1/P2 “what to fix first” list without broad rewrites or fake completion |
| What happened | Removed the unrelated cannabinoid project from default seeded projects while leaving optional ligand/research seed code isolated for explicit use; changed route-plan application to derive workflow edges from registered plugin input/output port schemas instead of generic `output`/`input`; updated DiffAb output schema so the antibody route can pass sequence-bearing CDR designs into AlphaFold 3 through a named compatible port |
| Decision | Keep Stage 7 capabilities paused unless the proven vertical slice is explicitly accepted; do not claim the live RFdiffusion cluster path is complete while `qm` remains unreachable from this environment |
| Reason | The platform’s supported path must be truthful by default: no unrelated product examples in the default UI, no schema-invalid route graphs, and no synthetic or unavailable execution presented as real design output |
| Risk | Optional ligand-aware routing still exists as hidden/non-default capability; true browser-runner E2E and live cluster RFdiffusion remain separate acceptance gates |
| Needs human confirmation | Yes — manual vertical-slice smoke on a real browser/phone viewport and campus/VPN execution of the RFdiffusion runbook |

## 2026-07-13 — “Staged implementation plan” finish pass

| Field | Content |
|-------|---------|
| Original plan | Turn the Stage 0–7 implementation plan into a durable repository artifact and close the canonical verification gap |
| What happened | Added `docs/END_TO_END_LOOP_HARDENING_PLAN.md`, linked it from `docs/README.md`, and fixed frontend lint blockers so the canonical frontend lint command exits cleanly with zero warnings |
| Decision | Mark Stage 7 as paused, not implemented; keep live RFdiffusion and manual browser smoke as explicit gates rather than treating documentation as scientific execution evidence |
| Reason | The project needs one source of truth that a reviewer can use without reading the chat history, and the staged plan must remain adversarial about what is truly proven |
| Risk | The plan will drift unless future Stage 7 expansion updates the same document and implementation notes |
| Needs human confirmation | Yes — accept the Stage 6 vertical slice and choose the first Stage 7 expansion deliberately |

## 2026-07-13 — MVP authority and sweet-protein route decision

| Field | Content |
|-------|---------|
| Original plan | Resolve MVP scope, compute truth, execution model, research authority, fixture policy, deployment ownership, examples storage, and first supported route |
| What happened | Updated the hardening plan with broader protein/biomaterial MVP scope, Project Review as canonical dossier, Target Intelligence/Literature Claims as evidence producers, server-verifiable Copilot mutation authority, production fixture exclusion, scientific threshold database requirement, site-owned LSF adapter responsibility, object/release-storage delivery package direction, and sweet protein as the first acceptance-tested route. Added `sweet_protein_design_route` to the route planner and verified repo-local synthetic runners pass smoke while real model/LSF/Docker executables are not installed in this environment. |
| Decision | The first supported vertical slice is sweet protein redesign: Monellin/Brazzein evidence and structure readiness → RFdiffusion → ProteinMPNN → fold prediction → Rosetta/interface scoring. Synthetic local runners are not scientific execution evidence. |
| Reason | Sweet protein has concrete project artifacts, archived scripts, scaffolds, and a narrow enough route to test the full platform loop without reopening every Stage 7 expansion. |
| Risk | Automatic DAG orchestration and real cluster execution remain acceptance gates; current local runner smoke proves only fixture mechanics. |
| Needs human confirmation | Yes — run the sweet-protein route on the installation-owned compute environment with verified licenses/executables, then accept or reject the vertical slice. |

## 2026-07-13 — Layer 8 tests, reliability, and maintainability

| Field | Content |
|-------|---------|
| Original plan | Make CI an honest executable product contract before adding more features |
| What happened | Fixed cwd-dependent backend test collection by normalizing test imports; moved backend tests to per-process temporary SQLite/artifact roots; made `reset_pool()` close pooled SQLite connections instead of dropping the global reference; added frontend retry-policy tests proving non-idempotent mutations are not replayed; added page-level product-contract tests for Experiments, Research/Target intelligence, Workflow, Candidates, Results, PDB upload persistence semantics, and Mol* lazy loading; split Mol* into lazy production chunks; added frontend lint to CI; made security audits fail CI; removed the successful deploy placeholder job |
| Decision | Treat lint, tests, production build, dependency audit, and vulnerability scan as blocking product contracts. Keep deployment absent until a real staging target, credentials, and rollback path exist. |
| Reason | A CI job that passes while tests depend on cwd, security is advisory, uploads can be ambiguous, or deploy is a placeholder gives false confidence and violates the platform’s scientific-trust goal. |
| Risk | Page coverage now includes Vitest/jsdom plus a real Chromium browser smoke; external compute boundaries are still mocked unless the installation-owned LSF/RFdiffusion acceptance run is performed. |
| Needs human confirmation | Yes — run the sweet-protein route on licensed installed compute. |

## 2026-07-13 — Plan completion browser gate

| Field | Content |
|-------|---------|
| Original plan | Fully complete remaining in-repository plan gates without faking external compute |
| What happened | Added `playwright` as an explicit frontend dev dependency, added `npm run test:browser`, created `frontend/scripts/browser-vertical-slice.mjs`, and wired CI to install Chromium and run the built app through a real browser smoke covering readiness recovery, blocked workflow submission, mobile navigation, candidate empty-structure state, and results/delivery gating |
| Decision | Use a minimal Playwright script instead of introducing a larger test framework; mock APIs inside Chromium so the browser test verifies frontend route semantics without depending on a local backend or synthetic compute |
| Reason | The remaining browser-runner gap was an in-repo testability gap and could be closed honestly. The live RFdiffusion/LSF acceptance gate still requires installation-owned compute and must not be simulated as scientific execution. |
| Risk | Browser smoke is still a deterministic vertical-slice smoke, not an exhaustive cross-browser suite. CI now downloads Chromium, increasing frontend job time. |
| Needs human confirmation | Yes — run the sweet-protein route on licensed/site compute and decide whether to resume Stage 7 expansion. |

## 2026-07-28 — Compute dataflow repair and plugin interface rebuild

| Field | Content |
|-------|---------|
| Original plan | `/Users/zero/.claude/plans/harmonic-brewing-diffie.md` — scope B: P0/P1 correctness plus declarative plugin extension interface |
| What happened | Added `model_plugins.input_ports/output_ports/resources/runtime_mode/output_parser` and `workflow_nodes.input_bindings` (migration `0016_compute_dataflow_ports`); new `compute/binding.py`, `compute/scripts.py`, `compute/parsers/`, `workflows/preflight.py`, `registry/ports.py`. Jobs now receive bound artifacts, downstream nodes consume upstream outputs, preflight is enforced at submit, preview renders through the same code the LSF adapter submits, plugin validation writes to its own columns, experiment import resolves `candidate_ref` and tolerates bad rows. 23 new backend tests; suite 186 passed, ruff and mypy clean (mypy now cleaner than the pre-change baseline, which had 2 errors). |
| Decision | Port compatibility keys on `artifact_type` + semantic `kind`; `content_type` is advisory only |
| Reason | Live data has 200 backbone PDBs stored as `application/vnd.palm` (browser mis-sniff). Gating on content type would reject valid scientific data. |
| Risk | Frontend binding UI not implemented — bindings are currently API-only, so the workflow canvas cannot yet author them. Disabled plugins (6 of 10) have empty port declarations and must be filled in before they can be wired. |
| Needs human confirmation | Yes — see LSF note below; and someone must author ports for the 6 disabled plugins |

### LSF status as of this change

`qm` became reachable during this session. The earlier conclusion in this session that
key auth was the only path was **wrong**: the site's policy is password auth. The server
offers only `gssapi-keyex,gssapi-with-mic,password`, and it also refuses plain SSH exec
channels, so commands must run on a PTY.

`LSFAdapter` was therefore reworked onto a transport abstraction
(`backend_v2/app/compute/ssh_transport.py`):

- `KeySSHTransport` — the previous `ssh -o BatchMode=yes` behaviour, still the default
  and still preferred.
- `PasswordSSHTransport` — paramiko with a password, for servers without `publickey`.
  Commands are wrapped in per-invocation sentinels so PTY echo, CRLF and login-shell
  noise (conda banner, MOTD) cannot corrupt `bjobs` parsing, and the command runs in a
  subshell so a remote `exit` cannot kill the session and lose the exit code. Script
  bodies are shipped base64-encoded rather than over stdin, which a PTY would mangle.

Config: `BDA_V2_LSF_SSH_PASSWORD_REF` (a `file:` reference only — never an inline value
or an env var, both of which are visible via `docker inspect`), plus
`BDA_V2_LSF_SSH_USER` and `BDA_V2_LSF_SSH_PORT`. The production validator now accepts
either a key path or a password reference, and rejects a non-`file:` reference.

Verified against the real cluster (`b04u17l`, IBM Spectrum LSF 10.1.0.0):
command execution, queue queries (`v3-64`, `4v100-16-e5` are Open:Active), exit-code
propagation for 0/7/42, session survival after a non-zero exit, and base64 script
round-trip into `/work/bme-sunzr`.

**Still blocking a real job:** `/usr/local/bin/bda-minio-upload` does not exist on the
cluster. Without that wrapper a job cannot return its outputs, so no end-to-end LSF run
has been performed. The worker containers also still need the password secret mounted
and `BDA_V2_LSF_*` set; `BDA_V2_COMPUTE_BACKEND` is currently `docker`.

Host keys: `PasswordSSHTransport` uses paramiko's `RejectPolicy`, so the cluster host key
must be present in the worker image's `known_hosts` before this can connect. The probe
above bypassed that deliberately and is not how the adapter runs.

### Verification performed

- `ruff` clean, `mypy` clean (165 files), `pytest` 186 passed / 2 skipped
- Migration applied to the live database inside its own transaction; an earlier attempt
  failed because the revision id exceeded `alembic_version.version_num` varchar(32) and
  rolled back cleanly with no partial DDL
- `backend_v2/scripts/verify_dataflow_e2e.py` — 10/10 checks against the live database
  using real seeded plugin ports and a real `backbone_set` artifact, inside a
  rolled-back transaction
- Backup taken first: `/Users/zero/bda-backups/` (pg_dump 16M verified complete, MinIO
  volume 9.4M, row-count baseline)
- Row counts for every table the migration touches are unchanged. `artifacts` and
  `artifact_lineage_edges` grew during the session from a concurrent
  `historical_alphafold_import` that finished ~37 minutes before the restart; unrelated
  to this change.
- The `candidate_ref` backfill linked 0 rows: the 5 unlinked results reference candidate
  keys that exist nowhere in the database (lifecycle-test leftovers), so there was no
  unambiguous match to make. The earlier estimate of 5 repairable rows was wrong.

## 2026-07-28 — Real LSF execution closed

| Field | Content |
|-------|---------|
| Original plan | Install the `bda-minio-upload` wrapper on the cluster to unlock end-to-end LSF |
| What happened | The wrapper turned out to be unbuildable **and unnecessary**. Probing the cluster showed compute nodes have no route to the object store, so no wrapper could have uploaded anything. Inverted the transfer instead: the API stages inputs over SFTP and pulls outputs back, and the output manifest is generated by a snippet inlined into the submit script. A real job then ran end to end on `qm` (LSF id 4026880). |
| Decision | `BDA_V2_LSF_STAGING_MODE=ssh` is the default; `presigned` remains for sites whose nodes can reach the object store |
| Reason | Only one direction of connectivity exists and it is the one we already use. Requiring cluster-side installation would also have made onboarding any new cluster a sysadmin ticket. |
| Risk | The worker process needs its own route to the cluster; a containerised worker does not inherit a host VPN (verified: `bda-worker-v2-1` gets `No route to host` for the cluster while the host reaches it over `utun*`). Until that is solved, LSF submission works only from a process that has the route. |
| Needs human confirmation | Yes — decide how the worker gets cluster connectivity in the real deployment |

### Why the wrapper approach was abandoned

Measured, not assumed:

- cluster → host MinIO (`192.168.31.243:9002`): **No route to host**. The cluster sits on
  `10.10.4.x / 172.18.6.x / 192.168.6.x / 11.11.5.x`; MinIO is bound to `127.0.0.1` on a
  host in a `192.168.31.x` NAT.
- cluster has general internet access, but the object store is not on the internet.
- cluster has `curl` and a conda `python3`; it has neither `mc` nor `aws`.
- `/work/bme-sunzr` is writable and the SFTP subsystem is available.

A `bda-minio-upload` wrapper would therefore have had nothing to upload to, and would
additionally have required object-store credentials to live on a shared cluster account.

### Verified against the live cluster

`backend_v2/scripts/verify_lsf_e2e.py` — 9/9 against `qm`, LSF job **4026880**:
input staged over SFTP, `bsub` accepted, job reached `succeeded`, manifest generated on
the node, output retrieved, checksum verified end to end, output port inferred from the
directory layout, bytes round-tripped intact. Remote working directory and test objects
cleaned up afterwards.

The cluster host key was added to `known_hosts` as part of this; `PasswordSSHTransport`
uses paramiko's `RejectPolicy` and will refuse an unknown host, which is intended.

## 2026-07-28 — Workflow canvas can author input bindings

| Field | Content |
|-------|---------|
| Original plan | Finish the frontend so bindings are usable outside the API |
| What happened | Added `InputBindingPanel`, wired it into `WorkflowInspector`, regenerated the typed API client against the new OpenAPI, and removed three UI controls that had never done anything |
| Decision | Per-node `queue` became a real field (the backend already accepted it); `resource_requirement` and `gpu_requirement` were deleted rather than kept as decoration |
| Reason | Those inputs were discarded by `submitWorkflowNode`'s `void options`, so the UI implied control the platform did not have. Resources are now declared by the plugin and rendered into scheduler directives server-side, which is where they belong. |
| Risk | Bindings can only reference upstream nodes that already carry a registry plugin; nodes without one show an explanatory empty state rather than an unusable picker |
| Needs human confirmation | No |

Frontend gate: `tsc -b` clean, `eslint --max-warnings=0` clean, 201 tests over 58 files,
production build succeeds.

The binding picker filters candidates on `artifact_type` and port `kind`, never on
content type — a regression test pins this, because real `.pdb` uploads in this
deployment carry `application/vnd.palm` and content-type filtering would hide them.

Experiment import now waits for its operation and renders the row-level report
(imported / skipped / unlinked counts, ignored columns, per-row errors) instead of
reporting a fixed `imported: 0` that was never true.

## 2026-07-28 — Compute worker moved to the host

| Field | Content |
|-------|---------|
| Original plan | Run the compute worker on the host so it can reach the cluster, keeping the door open for more servers and cloud compute |
| What happened | Split the compute queues out of the container worker and added `backend_v2/scripts/run-host-worker.sh` with a preflight, an env template and a compose overlay. Decoupled adapter construction from global settings so a second target is a config dict rather than a code change. |
| Decision | `dispatch`/`poll`/`collect` run on the host; `maintenance`, `research` and `copilot` stay containerised. Celery solo pool, because the SSH transport holds a connection that does not survive prefork. |
| Reason | The cluster route is a host VPN that a container network namespace does not inherit. Leaving both workers on the same queues would send jobs to whichever grabbed them first, and the containerised one always fails. |
| Risk | The cluster route is manual, so the worker is manual. If the VPN drops, in-flight jobs stall until it returns; `reap_stale_jobs` fails anything past its deadline. |
| Needs human confirmation | Yes — the full API-to-cluster loop through the host worker has **not** been observed, because the VPN was down for the whole of this change |

### Extension seam kept open

`adapter_for(name, target)` passes an optional config dict to the factory, and
`LSFAdapter(target)` layers it over global settings. A second cluster or a cloud queue is
therefore configuration:

```python
adapter_for("lsf", {"lsf_ssh_host": "cluster-b", "lsf_queue": "gpu-a100"})
```

`compute_nodes` is the intended home for those dicts (it already has `backend`, `queue`,
`labels`); per-job routing to a node is not wired up yet. New schedulers register with
`register_adapter(name, factory)` and are accepted by the API immediately, because
`SubmissionCreate.compute_backend` validates against the registry rather than a fixed
pattern. Documented in `docs/COMPUTE_TARGETS.md`.

### Verified

- `run-host-worker.sh --check`: PostgreSQL, Redis, MinIO, credentials and staging mode
  all PASS; cluster reachability and `bjobs` FAIL because the VPN was down. The check
  correctly distinguishes the two failure classes.
- Worker boots, connects to the broker and registers exactly `dispatch,collect,poll`.
- Backend gate: ruff clean, mypy clean (169 files), 195 passed / 2 skipped.

**Not verified:** a job submitted through the API and executed on the cluster via the
host worker. The direct adapter path was proven earlier (LSF job 4026880), but that ran
in-process, not through the worker. This needs one run with the VPN up.

## 2026-07-28 — Plugin ports derived rather than authored

| Field | Content |
|-------|---------|
| Original plan | Hand-write port declarations for the six disabled plugins |
| What happened | The declarations already existed in the legacy shape and were derived instead. `output_schema.ports` holds output ports for all ten plugins; inputs come from `parameter_schema.fields` entries typed `artifact_ref`. Migrations 0017 and 0018 applied. |
| Decision | Derived input ports default to `required: false`; added `exclusive_group` so alternative inputs can be expressed |
| Reason | A wrongly-required port blocks submission outright, a wrongly-optional one only goes unenforced — so guessing errs toward the recoverable failure. `exclusive_group` exists because ProteinMPNN takes a backbone as either a PDB or a parsed JSONL, which a per-port flag cannot state. |
| Risk | The semantic `kind` of a derived input is inferred from field name and help text. Two were wrong and are corrected in 0018; others may still be wrong for plugins nobody has run. |
| Needs human confirmation | Yes — which derived inputs are genuinely required, for the plugins beyond ProteinMPNN and Boltz |

### 0016 corrected

0016 hand-wrote ports for the four enabled plugins using invented names (`backbones`,
`sequences`, `structures`) that disagreed with each plugin's own declaration
(`backbone_set`, `sequence_set`, `predicted_structure`) — two sources of truth that
contradicted each other. 0017 replaces them with the derived values.

### Corrections in 0018

- `Boltz.input_path`: `params` → `protein_sequence`, required. Boltz takes a FASTA/YAML
  specification, so it can now be fed from an upstream node.
- `ProteinMPNN.pssm_jsonl`: `protein_sequence` → `params`. A position-specific scoring
  matrix is a parameter file; "pssm" merely reads as sequence-like.
- `ProteinMPNN.pdb_path` / `jsonl_path`: both required, sharing `backbone_source`.

### Known modelling gap

`AlphaFold 3` takes its sequences inside the JSON job specification (`json_path`), so it
cannot be wired from an upstream sequence port as declared. Participating in automatic
orchestration needs either a wrapper that accepts sequence files directly or an upstream
node that emits that JSON.

Gate: ruff clean, mypy clean (169 files), backend 199 passed / 2 skipped, frontend 201
passed over 58 files, dataflow E2E 10/10 against the live database.

## 2026-07-28 — Required inputs decided per model; AlphaFold 3 gap closed

| Field | Content |
|-------|---------|
| Original plan | Decide each plugin's required inputs individually, and bridge AF3 with a script |
| What happened | Migration 0019 sets required flags from each plugin's own field help plus what the tool cannot run without. Added an input-adapter interface (mirror of output parsers) and `af3_fold_input`, plus a standalone CLI. |
| Decision | RFdiffusion's input PDB stays **optional**; AF3 gains a `sequences` port sharing an exclusive group with `json_path` |
| Reason | Unconditional RFdiffusion generation legitimately takes no input PDB, so requiring one would block a real mode. AF3 accepts either a hand-authored specification or generated-from-sequences, which is exactly an exclusive group. |
| Risk | The emitted AF3 JSON follows the documented format but has **not** been run against a real AF3 install; the format has changed across releases |
| Needs human confirmation | Yes — validate `fold_input.json` against the AF3 build actually installed |

| Plugin | Required | Basis |
|---|---|---|
| AlphaFold2 | `fasta_paths` | Nothing to fold without sequences |
| AlphaFold 3 | `json_path` *or* `sequences` | Exclusive group; adapter supplies the JSON |
| BindCraft | `settings` | Names the target; `filters`/`advanced` ship defaults |
| Boltz | `input_path` | Unconditional in the command template |
| Chai-1 | `input_fasta` | Unconditional; `restraints_json` help says "Optional" |
| DiffAb | `antigen_pdb` | Antibody design needs something to design against |
| ProteinMPNN | `pdb_path` *or* `jsonl_path` | Exclusive group |
| Rosetta | `s` | Nothing to score without a structure |
| RFdiffusion | *(none)* | Unconditional generation takes no input PDB |
| Mask RGN | *(none)* | Declares no artifact inputs |

### Input adapters

`ModelPlugin.input_adapter` names a function that synthesises inputs a workflow cannot
bind directly. It runs on the worker during dispatch, before the manifest is written, so
it applies to every compute backend and needs nothing installed on the cluster. Generated
files land under `jobs/<id>/attempt-<n>/generated/` and join the manifest as ordinary
inputs.

`af3_fold_input` reads bound FASTA inputs and emits AF3's job specification. An explicitly
bound `json_path` always wins — a hand-tuned specification is never overwritten. Sequences
containing non-protein residues raise rather than being folded as protein, since a
nucleotide needs a different AF3 entity type that this adapter does not emit.

Also available standalone: `backend_v2/scripts/build_af3_input.py designs.fa -o fold_input.json`.

Gate: ruff clean, mypy clean (173 files), backend 208 passed / 2 skipped, frontend 201
passed over 58 files, dataflow E2E 10/10 against the live database.

## 2026-08-03 — Six sweet-protein design routes recorded and registered

| Field | Content |
|-------|---------|
| Original plan | Register the manuka design routes into Research Methods and as workflow routes |
| What happened | Two route definitions (`sweet_protein_design_routes.py` for scaffold routes 1-3, `sweet_protein_protocol_routes.py` for de novo routes A/B/C) feed three writers: the Methods seeder, the observed-results workflow refresh, and a new per-route registration script. Ran all three against the local database: 6 Methods entries and 3 new workflow routes on the manuka project, each route named by its own definition (`Route A · 药效团移植 / Pharmacophore transplant`, and so on). |
| Decision | A/B/C become **one workflow run each**, not three branches of one graph |
| Reason | In this product a route *is* a workflow run — the context bar switcher lists runs and "New route" creates one. A, B and C are alternative campaigns rather than parallel lanes; stacking them on one canvas would hide that, and Route C is explicitly the filter both other routes hand off to. |
| Decision | The Methods prose is **generated** from the same stage tuples the workflow nodes are built from |
| Reason | The two views are read independently. Hand-writing method text next to a hand-written graph is how a Methods tab ends up describing stages the canvas does not have. |
| Risk | Everything except scaffold routes 1 and 2 is plan-only, and 16 distinct tools have no registered plugin |
| Needs human confirmation | Yes — enable BindCraft / AlphaFold 3 / Boltz / Chai-1 (registered but disabled), and decide which of the 16 missing tools to register |

### Routes

| # | Route | Shape | Execution |
|---|---|---|---|
| 1 | `monellin` — natural MNEI | RFdiffusion → ProteinMPNN → Rosetta → AlphaFold2 | Executed; 0 designs passed the functional-site gate |
| 2 | `brazzein` — natural brazzein | same chain, disulfide topology fixed | Executed; every design broke the disulfide topology |
| 3 | `receptor_conditioned` — TAS1R2/TAS1R3 | intake → hotspots → receptor-conditioned RFdiffusion → contact-constrained MPNN → complex prediction → docking → interface physics → review | Never run, `execution_ready=false` |
| A | `route_a_pharmacophore_transplant` | receptor prep → glycan exclusion → motif extraction → RFdiffusion2 → IP fold-space → SolMPNN → AF2 initial-guess → hand-off | Plan only |
| B | `route_b_bivalent_clamp` | geometry go/no-go → per-epitope BindCraft → linker ladder → ternary prediction (both states) → crossover selection | Plan only |
| C | `route_c_differential_scoring` | intake → developability → differential AF2 → Rosetta ddG (both states) → stability/allergenicity → metadynamics → agonism ranking | Plan only |

Routes 1-3 remain branches of the observed-results run (`observed-results-workflow-v2`,
19 nodes) and converge on the shared `candidate_review` node; that run can no longer
report `succeeded` while route 3 has never executed. The suffix is v2 because the live
database already held that run — writing v1 would have added a duplicate to the project's
route list instead of refreshing the row users see.

### Why A/B/C exist at all

The protocol's section 0: a standard pipeline maximises -dG against one static
conformation, which is affinity. Sweetness is agonism of a class C GPCR. A picomolar
binder of the *open* TAS1R2 VFT passes every conventional filter and tastes of nothing —
the stated explanation for designs that expressed and folded but did nothing. The 2025
cryo-EM endpoints (9UT8 apo, 9UTB sucralose-bound) are what make the differential
objective computable, and Route C is that filter.

### Missing model plugins

16 tools across the six routes have no registered plugin: AlphaFold-Multimer, RosettaDock,
HADDOCK, APBS, PDB2PQR, FoldX (route 3); RFdiffusion2, Foldseek, TM-align, SolMPNN,
AlphaFold2 initial-guess (route A); Rosetta InterfaceAnalyzer + FastRelax, ThermoMPNN,
allergenicity screen, GROMACS, PLUMED (route C). Each gap is carried on the node as
`missing_model_plugins` and shown in the canvas footer as `Needs plugin: ...`, so a stage
that cannot be dispatched does not read as merely "not started yet".

Separately, BindCraft, AlphaFold 3, Boltz (2.x) and Chai-1 are **registered but disabled**.
Route B depends entirely on them and needs them enabled, not written.

Gate: ruff clean, mypy clean (201 files), backend 356 passed / 5 skipped, frontend 345
passed over 85 files. Live database verified through the deployed API code path: the
Research workspace returns 6 methods for the manuka project.

## 2026-08-03 — Registered plugins pointed at their real qm installs

| Field | Content |
|-------|---------|
| Original plan | Step 1 of the qm plan: connect the registered model plugins to the cluster |
| What happened | Found two defects that made every non-ProteinHunter plugin unrunnable, not merely misconfigured. Migration 0024 repairs both for 8 plugins and a new test renders each command through the real renderer. |
| Decision | `enabled` flags are left untouched |
| Reason | Pointing a plugin at a real install is a repair; enabling one is a product decision that needs a smoke test, and AlphaFold 3's weights carry non-commercial terms while this is a food-ingredient project. |
| Risk | The command templates have never been executed on qm; they are transcribed from job scripts that did run, but a flag could still be wrong |
| Needs human confirmation | Yes — one smoke run per plugin before enabling BindCraft / Boltz / Chai-1 |

### The two defects

**Placeholder commands.** AlphaFold2, ProteinMPNN, RFdiffusion and Rosetta carried
`command = "python run.py"` against a `bda/<model>:<ver>` image that does not exist.
`compute.scripts.render_script` builds the LSF script straight from `plugin.command`, so
submitting any of them would have run `python run.py`. Nobody hit it because every real
sweet-protein job went through the hand-rendered `qm-scripts/library` path instead.

**Parameters that never reached the script.** `_parameter_exports` only exports names
matching `^[a-z][a-z0-9_]*$`, deliberately, so a parameter cannot collide with PATH or
`LD_*`. RFdiffusion's parameters were *all* authored in Hydra form
(`inference.num_designs`), Rosetta's in flag form (`score:weights`), and ProteinMPNN had
three with capitals. None of them were ever exported: a node setting
`inference.num_designs=100` would have run the model's default, silently. 0024 renames
them to renderer-safe names and records the real CLI spelling in a new `cli` field on
each parameter, which the command templates map back to.

### What is wired now

| Plugin | Runtime | Entry point |
|---|---|---|
| RFdiffusion | conda `/work/bme-liz/.../SE3nv-gpu` | `run_inference.py`, Hydra args |
| ProteinMPNN | conda `envs/mlfold` | three-step helper pipeline over the staged port dir |
| AlphaFold2 | conda `envs/alphafold` | local full databases; `model_preset` covers multimer |
| Rosetta | plain binary | `application` parameter selects the binary |
| BindCraft / Boltz / Chai-1 | conda under `/work/bme-sunzr/.conda/envs/` | our own account |
| AlphaFold 3 | conda `/share/apps/alphafold3-v3.0.1` | shared install |

Every command writes only to `$BDA_OUTPUT_DIR`; other accounts' directories are read-only
by rule, and `test_qm_plugin_commands.py` asserts no command writes into one. Three of the
route-B models turned out to be installed under our own account already, which removes the
install work that plan step 2 assumed.

Gate: ruff clean, mypy clean (201 files), backend 389 passed / 5 skipped. Migration applied
to the local database: 8 plugins repointed.

## 2026-08-03 — Route-B plugins enabled; cluster verification still outstanding

| Field | Content |
|-------|---------|
| Original plan | Run the four read-only cluster commands, then smoke-test and enable the route-B plugins |
| What happened | The cluster half could not be done: `ssh qm` offers only GSSAPI/password, `BDA_V2_LSF_SSH_KEY_PATH` is empty and the agent holds no identities, so no non-interactive login exists. Did the half that does not need a cluster: `bash -n` over every rendered script, and an argv-level expansion test that runs the command with the model entry point replaced by `printf`. Then enabled BindCraft, Boltz and Chai-1. |
| Decision | AlphaFold 3 stays disabled |
| Reason | Its weights carry non-commercial terms and this is a food-ingredient project; that is the user's call, not a repair. |
| Risk | Path existence, flag compatibility and queue naming on qm are unverified — all three fail as a failed job, not as data loss |
| Needs human confirmation | Yes — the RFD3 sample listing, and one real BindCraft submission as the remaining half of the smoke test |

The expansion test is the one worth keeping: asserting on template text cannot catch a
quoting bug, because `[A1-50/2-4]` unquoted is a glob and an empty optional would become
an empty argument Hydra rejects. Running the expansion shows what the model would actually
receive:

```
contigmap.contigs=[A1-50/2-4/B1-19/B21-44]
inference.num_designs=100
diffuser.partial_T=5
inference.output_prefix=/tmp/out/design
```

It also caught a real defect: `-parser:script_vars` had been quoted, which would have
handed Rosetta a single argument `"a=1 b=2"` instead of a list of key=value pairs. That
flag is now deliberately the only unquoted one.

Gate: ruff clean, mypy clean (201 files), backend 398 passed / 5 skipped.

## 2026-08-03 — qm verified on the cluster; three plugin paths were wrong

| Field | Content |
|-------|---------|
| Original plan | Run the four read-only cluster commands, smoke-test, enable route-B plugins |
| What happened | Got cluster access, ran the checks read-only, and found that three of 0024's entry points were wrong and one model is not installed at all. Migration 0025 corrects them, disables what does not exist, and registers `superfold`. |
| Decision | Disable rather than repoint AlphaFold2 and Chai-1 |
| Reason | A plugin naming absent software is worse than a disabled one: preflight passes it and the failure only appears after a queue wait. |
| Risk | Nothing has actually been executed yet - existence and start-up were checked, not a real design run |
| Needs human confirmation | One real submission per enabled plugin |

### What the examples got wrong

`qm-scripts/library/examples/` claimed BindCraft, Boltz, Chai-1 and Mask RGN live under
our own account. `/work/bme-sunzr/software` is empty and our only conda env is `gemmi`.
BindCraft and Boltz are actually under `/work/bme-liz`; **Chai-1 is not installed
anywhere**; and DeepMind AlphaFold2 plus its `db/alphafold` databases do not exist either.
0024 had wired all four from those configs, so half of what it "fixed" pointed at nothing.

### Two findings that unblock routes

**`superfold` implements `--initial_guess`** (`run_superfold.py:171`). That is the Bennett
protocol Route A's binder filter and Route C's differential scoring are calibrated
against, and the qm doc had it down as needing a dl_binder_design install. Registered as
the `superfold` plugin. Two constraints are encoded: its wrapper exits if a conda
environment is active (so `runtime_mode=script`, empty `runtime_setup`), and it refuses
multimer, so AlphaFold-Multimer remains a genuine gap.

**Rosetta ships 658 binaries here**, including `InterfaceAnalyzer`, `docking_protocol` and
`cartesian_ddg`. Route C's ddG, Route 3's RosettaDock and the ThermoMPNN substitute are
all zero-install, reachable by switching the `application` parameter.

Also measured: `soluble_model_weights` present (SolMPNN usable); GROMACS available as a
module, PLUMED not; foldseek/apbs/pdb2pqr absent.

### RFdiffusion3

The sample is a Python API plus a Hydra CLI (`rfd3 design`). Reading
`rfd3/inference/input_parsing.py` settled the question Route A depends on:
`select_fixed_atoms` takes a per-residue, per-atom-name mapping, so the brazzein charge
pharmacophore can be fixed atom-by-atom while `select_unfixed_sequence` frees the rest.
That is what RFdiffusion2 was wanted for, so Route A's generator is no longer blocked.
`partial_t` is Angstroms of noise here, not a step count - copying an RFD1/RFD2 config
across would be wrong.

Gate: ruff clean, mypy clean (201 files), backend 402 passed / 5 skipped. All 16 wired
entry points verified to exist on qm; `score_jd2` starts.

## 2026-08-03 — Owner decisions applied: AF3 on, AFM dropped, RFdiffusion3 installed

| Field | Content |
|-------|---------|
| Original plan | Act on four decisions: use AF3 directly, cover AlphaFold-Multimer with AF3, install RFdiffusion3, and treat another account's installs as fair game |
| What happened | Migration 0026 enables AlphaFold 3 and registers RFdiffusion3. The route definitions were rewritten against what the cluster actually has, which collapsed the gap list from 16 tools to 8. A clone of the working `foundry` env into our own account is running on the cluster. |
| Decision | Checkpoints are referenced read-only, not copied |
| Reason | `/work/bme-rongx/.foundry/checkpoints` is 12 GB and world-readable and holds `rfd3_latest.ckpt`; `FOUNDRY_CHECKPOINT_DIRS` points the engine at it. Copying would duplicate 12 GB for no benefit. |
| Risk | Neither RFdiffusion3 nor AlphaFold 3 has been executed; the RFD3 command is transcribed from `rfd3/cli.py`, not run |
| Needs human confirmation | One smoke run each, after the env clone finishes |

### Gap list after measurement

Still missing: APBS, PDB2PQR, FoldX, Foldseek, TM-align, ThermoMPNN, the allergen
database, PLUMED. Closed: AlphaFold-Multimer (AF3 covers it), RosettaDock /
InterfaceAnalyzer / cartesian_ddg (in the qm Rosetta build), SolMPNN (a ProteinMPNN flag),
AF2 initial-guess (superfold), RFdiffusion2 (RFdiffusion3 supersedes it), GROMACS (a
cluster module), HADDOCK (dropped as redundant with RosettaDock).

### Two corrections the measurement forced

Routes 1 and 2 named `AlphaFold2` as their fold-prediction plugin, but DeepMind AlphaFold2
is not installed on qm - **superfold** is, and it is what produced those observed pLDDT/pTM
results. The stages now name `superfold`; the node keys stay `*_alphafold2` because they
identify results already registered against them.

Renaming Route A's generator stage from `route_a_rfdiffusion2` to `route_a_rfdiffusion3`
exposed a defect in the registration script: it created the new node but left the old one
behind, so the run would show a node with no edges and no spec - which reads as a real
stage that never ran. The script now deletes nodes the spec no longer contains.

Gate: ruff clean, mypy clean (201 files), backend 407 passed / 5 skipped.

## 2026-08-04 — Lightweight tools installed; RFdiffusion3 borrowed rather than cloned

| Field | Content |
|-------|---------|
| Original plan | Continue, and install the lightweight tools and the licence-gated data |
| What happened | Installed Foldseek, US-align, APBS, PDB2PQR, MMseqs2 and PLUMED under our own account and verified each starts; cloned ThermoMPNN and started a dedicated env for it. Abandoned the RFdiffusion3 env clone and pointed the plugin at the existing installation instead. |
| Decision | Do not clone the `foundry` environment |
| Reason | It passed 12 GB and was still copying. An environment carrying torch, JAX and CUDA is not worth duplicating per user on a shared filesystem, and a clone drifts from the copy that is known to work. Referencing another account's install read-only is already how BindCraft, Boltz, RFdiffusion and superfold run here. |
| Risk | The plugin now depends on a directory another account owns |
| Needs human confirmation | FoldX and the allergen databases need registration under a real identity — not something to do on someone's behalf |

### Installed under /work/bme-sunzr

`bda-tools` env: foldseek 10.941cd33, mmseqs2 18.8cc5c, apbs 3.4.1, pdb2pqr 3.6.1,
plumed 2.10. Plus `software/USalign` (20260527, compiled from source) and
`software/ThermoMPNN` (repo with `thermoMPNN_default.pt`; its env is still installing
because liz's `mlfold` has torch but not pytorch_lightning/omegaconf, and writing into
another account's env is not allowed).

PLUMED being installed does not make it usable: the cluster GROMACS modules are not
patched against it. Either build a private patched GROMACS or drive PLUMED from OpenMM,
which needs no patched engine. The route stage says so rather than claiming the gap closed.

### The gap list changed shape

Nothing on it is "software we do not have" any more. What remains is registry work
(Foldseek / US-align / APBS+PDB2PQR / ThermoMPNN plugin rows), one integration
(GROMACS+PLUMED), and two datasets behind registration (AllergenOnline, COMPARE). FoldX
was dropped: it needs an academic licence and the qm Rosetta build already ships
`cartesian_ddg` for the same mutation-energy term.

The dependency guard is new: RFdiffusion3's `runtime_setup` tests that the borrowed
environment still exists and exits with a named dependency error if it does not, rather
than failing inside conda activation.

Gate: ruff clean, backend 407 passed / 5 skipped.

## 2026-08-04 — Lightweight tools installed; RFdiffusion3 borrowed rather than cloned

| Field | Content |
|-------|---------|
| Original plan | Continue, and install the lightweight tools plus the licence-gated data |
| What happened | Installed Foldseek, US-align, APBS, PDB2PQR, MMseqs2 and PLUMED under our own account and verified each starts; cloned ThermoMPNN and started a dedicated env for it. Abandoned the RFdiffusion3 env clone and pointed the plugin at the existing installation instead. |
| Decision | Do not clone the `foundry` environment |
| Reason | It passed 12 GB and was still copying. An environment carrying torch, JAX and CUDA is not worth duplicating per user on a shared filesystem, and a clone drifts from the copy that is known to work. Referencing another account's install read-only is already how BindCraft, Boltz, RFdiffusion and superfold run here. |
| Risk | The plugin now depends on a directory another account owns |
| Needs human confirmation | FoldX and the allergen databases need registration under a real identity |

`bda-tools` env: foldseek 10.941cd33, mmseqs2 18.8cc5c, apbs 3.4.1, pdb2pqr 3.6.1,
plumed 2.10. Plus `software/USalign` (20260527, compiled from source) and
`software/ThermoMPNN` (repo with `thermoMPNN_default.pt`; its env is still installing,
because liz's `mlfold` has torch but not pytorch_lightning/omegaconf and writing into
another account's env is not allowed).

PLUMED being installed does not make it usable: the cluster GROMACS modules are not
patched against it. Either build a private patched GROMACS or drive PLUMED from OpenMM,
which needs no patched engine. The route stage says that rather than claiming the gap shut.

Nothing on the gap list is "software we do not have" any more. What remains is registry
work (Foldseek / US-align / APBS+PDB2PQR / ThermoMPNN plugin rows), one integration
(GROMACS+PLUMED), and two datasets behind registration. FoldX was dropped: it needs an
academic licence and the qm Rosetta build already ships `cartesian_ddg` for the same term.

RFdiffusion3's `runtime_setup` now tests that the borrowed environment still exists and
exits with a named dependency error if it does not, rather than failing inside conda
activation.

Gate: ruff clean, backend 403 passed / 5 skipped.

## 2026-08-03 — Lightweight tools installed and registered; three gaps left

| Field | Content |
|-------|---------|
| Original plan | Install the "lightweight" tools and the data/licence items, then register them |
| What happened | Installed Foldseek, US-align, APBS, PDB2PQR, MMseqs2, PLUMED and ThermoMPNN under our own account (~8 GB). Migration 0027 registers three of them as plugins. The route gap list went from 16 tools to 3 items, none of which is a plugin row anyone can write. |
| Decision | The RFdiffusion3 environment is used in place rather than cloned |
| Reason | The clone reached 12 GB and was still copying. An env carrying torch, JAX and CUDA is not worth duplicating per user on a shared filesystem, and a copy would drift from the one known to work. Same policy as every other plugin here, which runs out of `/work/bme-liz`. |
| Risk | Still nothing executed; the tool command templates are transcribed from `--help`, not run |
| Needs human confirmation | Registering for AllergenOnline/COMPARE, and one smoke submission per plugin |

### Installed under `/work/bme-sunzr`

`bda-tools` conda env (6 GB): foldseek, mmseqs2, apbs, pdb2pqr30, plumed.
`software/USalign`: compiled from source, no conda package exists.
`software/ThermoMPNN` + `thermompnn` env (1.5 GB): torch 2.13, lightning 2.6.5, omegaconf.

### Registered as plugins (0027)

Foldseek, US-align and APBS+PDB2PQR. APBS and PDB2PQR are one plugin on purpose: PDB2PQR
both protonates the structure and writes the APBS input file, so splitting them would
create a node whose only output is the next node's input.

### What is deliberately not registered

**ThermoMPNN** is installed but its stock entry point (`analysis/SSM.py`) reads dataset
paths from the authors' own cluster (`local.yaml` points at `/nas/longleaf/...`), so
running it on arbitrary PDBs needs a wrapper rather than a command template. It is not
blocking: the protocol only uses it to *propose* substitutions, and Rosetta
`cartesian_ddg` is on qm and reachable through the Rosetta plugin's `application`
parameter.

**The allergenicity screen** is blocked on data, not software: MMseqs2 is installed, but
AllergenOnline and COMPARE require accepting their terms and registering - the owner's
action.

**GROMACS+PLUMED** needs PLUMED patched into a GROMACS build; the cluster module is
unpatched. The lighter route is conda OpenMM + openmm-plumed.

Gate: ruff clean, mypy clean (201 files), backend 419 passed / 5 skipped. 15 plugins
registered, 12 enabled.

## 2026-08-03 — First real submissions: three tools through the platform's own scripts

| Field | Content |
|-------|---------|
| Original plan | Stop guessing and submit something |
| What happened | Rendered the Foldseek, US-align and APBS+PDB2PQR job scripts from their registry rows with `compute.scripts.render_script` - the same code the API submits with - staged real route-2 inputs, and ran them on qm. Foldseek passed first time; the other two failed and both failures were real defects. |
| Decision | Fix the command templates rather than the smoke inputs |
| Reason | One was a genuine bug (US-align), the other a contract the plugin had not stated (APBS needs full-atom input). |
| Risk | The GPU-side plugins - RFdiffusion3, superfold, BindCraft, AlphaFold 3, Boltz - still have never run |
| Needs human confirmation | No |

### Two defects only execution could find

**US-align segfaulted.** `-dir1 "" <absolute paths>` made it read zero chains and dump
core - it did not exit non-zero with a message, so the job's only symptom was an empty
output file. US-align concatenates the `-dir1` prefix with each name in the list, so the
prefix must be a real directory (trailing slash included) and the list must hold basenames.

**pdb2pqr rebuilds hydrogens, not missing heavy atoms.** Feeding it an RFdiffusion backbone
died inside the library with a bare `RuntimeError` wrapping "Found gap in biomolecule
structure". The command now checks for side-chain atoms first and fails with a named
message. In the routes this node always sits downstream of sequence design, so the
contract holds - it just was not stated.

Both are pinned by tests that assert on the command shape, not on a mock.

### First scientific result out of the pipeline

US-align on three round-1 brazzein designs against natural brazzein: **TM-score 0.85-0.91,
identity 0.17**. Route A's IP gate is TM < 0.40, so every round-1 design fails it - which
is exactly right, because those designs are partial-diffusion redesigns of the natural
scaffold. The gate discriminates "engineered natural scaffold" from "novel fold", which is
what route A needs it to do.

APBS solved the natural brazzein structure: 16.7 MB potential grid, global net ELEC energy
5.16e4 kJ/mol.

Gate: ruff clean, backend 415 passed / 5 skipped.

## 2026-08-03 — superfold and AF3 corrected from the hand-written jobs that ran them

| Field | Content |
|-------|---------|
| Original plan | Smoke-test the GPU plugins |
| What happened | Those tools have already been run on qm by hand, so their job scripts are ground truth and cost nothing to check against. They contradicted the plugin definitions in three places. Migration 0028 fixes all three; no GPU time spent. |
| Decision | Treat the existing hand-written job scripts as the specification |
| Reason | They are evidence of what works on this cluster, which is strictly better than reading `--help` and guessing. |
| Risk | The plugin path for the GPU models still has not been exercised end to end |
| Needs human confirmation | No |

### Three corrections

**superfold exits inside a conda environment.** Its wrapper tests `CONDA_DEFAULT_ENV` and
quits, because it calls its own interpreter by absolute path. 0025 declared an empty
`runtime_setup` so nothing would *activate* an environment - but that is not the same as
guaranteeing none is *already* active, and the hand-written job opens with
`source deactivate base`, which says this cluster does leave one active. The preamble now
clears it, with an unconditional `unset CONDA_DEFAULT_ENV` as the deterministic fallback:
that single variable is what the wrapper actually tests.

**superfold's input glob swallowed AppleDouble files.** The hand-written loop skips
`._*.pdb`; those are macOS metadata that parse as neither PDB nor FASTA and appear whenever
inputs have been through a Mac. The find now excludes them.

**AlphaFold 3's three output ports all globbed `*`.** Every port matched every file, so
collection could not tell a predicted structure from a confidence JSON. Real runs write
`*_model.cif` (sometimes gzipped) and `*summary_confidences.json`, per the collector in the
AF3 job script, so the globs come from that. `num_diffusion_samples` is now exposed too,
since the real invocation passes it.

### A migration trap worth a guard

`0028_superfold_af3_from_real_runs` is 33 characters and `alembic_version.version_num` is
`VARCHAR(32)`. Alembic does not check: the migration ran, printed its own success lines,
and then died at the version stamp, so the whole upgrade rolled back while looking like it
had worked. Renamed to fit, and `test_migration_core.py` now asserts every revision id fits
the column.

Gate: ruff clean, mypy clean (201 files), backend 420 passed / 5 skipped.

## 2026-08-03 — superfold verified end to end; verification policy set

| Field | Content |
|-------|---------|
| Original plan | Smoke-test the GPU plugins one by one |
| What happened | superfold ran through the plugin path and passed. The owner then set the policy: remaining plugins get validated at first real use rather than by dedicated smoke jobs. |
| Decision | No more standalone smoke submissions |
| Reason | Four plugins are now verified and the two classes of defect they exposed (shell/quoting, and unstated input contracts) are covered by tests. Burning shared GPU queue to pre-verify the rest buys less than validating them against real work. |
| Risk | A plugin's first real use may still fail on a flag mismatch; that surfaces as a failed job, not lost data |
| Needs human confirmation | No |

### What superfold's run proved

Every parameter mapping was echoed back by the model itself, which is what makes this a
verification rather than an absence of errors:

```
Using target structure as initial guess        <- --initial_guess took effect
brazzein_design_0_seq_1_packed_0 model_4_ptm_seed_0 recycles:3 tol:0.20
      mean_plddt:78.00 pTMscore:0.52 rmsd_to_input:1.81
```

`model_4_ptm` confirms `--models 4`, `recycles:3` confirms `--max_recycles`, and the
initial-guess line confirms the Bennett protocol that route A's `pAE_interaction < 10` and
route C's differential thresholds are calibrated against. All three output port globs
matched the real filenames.

The numbers also land directly on route A's gates: `rmsd_to_input` 1.81 A passes the
design-vs-prediction < 2.0 A gate, 2.08 A fails it, and both designs sit far below the
monomer pLDDT > 85 gate.

### Verification policy from here

First use of a plugin runs the smallest possible job and checks three things before
scaling: that parameters are echoed by the model's own output, that filenames match the
port globs, and that failures name themselves. That is what caught the US-align segfault
(empty output, no error) and the pdb2pqr gap failure (bare RuntimeError).

Gate: ruff clean, backend 421 passed / 5 skipped.
