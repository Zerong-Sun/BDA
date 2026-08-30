NEEDS_FIXES

IMPORTANT — Read-only state is not propagated into workflow mutations. `frontend/src/app/Workflow.tsx:731` renders WorkflowInspector without readOnly; `frontend/src/features/workflow/WorkflowInspector.tsx:229` can still update node parameters, while `frontend/src/features/jobs/JobStatusDrawer.tsx:196` can submit a completed/read-only workflow node. Add and enforce the route’s read-only gate for mutating actions.

IMPORTANT — The script uploader violates the native-control exception. `frontend/src/features/workflow/ScriptAssetManager.tsx:165` exposes a visible browser file input. The migration specification permits file inputs only when hidden behind a localized styled trigger.

IMPORTANT — The job timeline does not react when asynchronously fetched logs arrive. `frontend/src/features/jobs/JobStatusDrawer.tsx:247` passes a changing expression through defaultValue; ReUI Timeline consumes that only on initial mount, so the log step remains visually incomplete. Use controlled value, considering both fetched logs and error_message.

IMPORTANT — Workflow page surfaces remain mixed with hand-built dashboard cards. `frontend/src/app/Workflow.tsx:113`, `frontend/src/app/Workflow.tsx:121`, and `frontend/src/app/Workflow.tsx:627` retain bordered section/div card surfaces instead of Frame compositions, contrary to the single-Frame surface contract.

MINOR — The sortable handle has an incorrect accessible name. `frontend/src/features/workflow/ScriptAssetManager.tsx:229` labels script reordering with the workflow-canvas “connect nodes” hint. Add localized reorder/drag copy so assistive technology describes the actual action.
