# Local project storage contract

BDA Workbench treats a project as both a database record and a local workspace.
At the current stage, every created project must be persisted locally. The API
also keeps a cloud-sync boundary so a later backend server can mirror the same
project manifest without changing the front-end workflow.

## Local layout

Project workspaces live under:

```text
backend/artifacts/projects/<project_id>/
  metadata/project.json
  inputs/
  workflows/
  jobs/
  results/
  research/
  exports/
```

`metadata/project.json` is the stable local manifest. It records the project id,
name, type, status, owner, summary, local storage root, and cloud sync status.

## Creation flow

1. `POST /api/v1/projects` creates the SQLite project record.
2. The backend creates the local workspace and `metadata/project.json`.
3. The backend creates the initial design task, draft workflow run, and research brief.
4. `GET /api/v1/projects` returns each project with:
   - `local_workspace.status`
   - `local_workspace.root`
   - `local_workspace.manifest`
   - `cloud_sync.status`

The front end displays the local workspace status in the project selector.

## Deletion flow

`DELETE /api/v1/projects/{project_id}` removes the project database record and
lets SQLite cascade linked project data such as targets, workflow runs,
candidates, artifacts, campaigns, and research briefs.

The local workspace is not physically erased by default. The backend moves:

```text
backend/artifacts/projects/<project_id>/
```

to:

```text
backend/artifacts/project_trash/<deleted_at>_<project_id>/
```

The trash folder includes `metadata/deletion.json` with the original root,
trash root, deletion timestamp, and actor id. Moving the workspace out of
`backend/artifacts/projects/` prevents the local recovery scanner from
recreating a database row for a project the user intentionally deleted.

## Recovery flow

`GET /api/v1/projects/local-index` scans local manifests and restores minimal
database rows for any project whose local workspace exists but whose SQLite row
is missing. `init_db.py` does not restore orphaned local manifests by default;
set `BDA_RECONCILE_LOCAL_PROJECTS=true` when running initialization if an
explicit local recovery pass is needed.

This allows local projects such as the sweet-protein RFdiffusion project to be
restored after a seed/reset cycle when an explicit recovery pass is requested,
as long as the local project manifest is still present.

## Cloud sync boundary

`POST /api/v1/projects/{project_id}/sync`

Payload:

```json
{ "target": "local" }
```

or:

```json
{ "target": "cloud" }
```

`target=local` refreshes the local manifest. `target=cloud` currently returns
`not_configured`; this is the reserved interface for a future backend cloud
server sync service.
