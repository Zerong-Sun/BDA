import {
  addWorkflowNodeApiV2WorkflowRunsWorkflowIdNodesPost,
  deleteWorkflowNodeApiV2WorkflowRunsWorkflowIdNodesNodeIdDelete,
  getWorkflowApiV2WorkflowRunsWorkflowIdGet,
  getWorkflowGraphApiV2WorkflowRunsWorkflowIdGraphGet,
  listWorkflowNodesApiV2WorkflowRunsWorkflowIdNodesGet,
  patchWorkflowLayoutApiV2WorkflowRunsWorkflowIdLayoutPatch,
  patchWorkflowNodeApiV2WorkflowRunsWorkflowIdNodesNodeIdPatch,
  postWorkflowApiV2ProjectsProjectIdWorkflowRunsPost,
  previewNodeScriptApiV2WorkflowNodesNodeIdScriptPreviewsPost,
  submitWorkflowApiV2WorkflowRunsWorkflowIdSubmissionsPost,
  validateWorkflowApiV2WorkflowRunsWorkflowIdValidatePost,
  workflowPreflightApiV2WorkflowRunsWorkflowIdPreflightGet,
} from './generated/sdk.gen'
import { ApiError, type ProblemDetails } from './client'
import './generatedTransport'
import {
  WorkflowNodeSchema,
  WorkflowGraphSchema,
  WorkflowRunSchema,
  WorkflowPreflightSchema,
  type WorkflowGraph,
  type WorkflowLayout,
  type WorkflowNode,
  type WorkflowInputBinding,
  type WorkflowPreflight,
  type SubmitStatus,
} from '../schemas/workflow'

async function workflowIfMatch(workflowRunId: string): Promise<Record<string, string>> {
  const { data } = await getWorkflowApiV2WorkflowRunsWorkflowIdGet<true>({ path: { workflow_id: workflowRunId },
    throwOnError: true })
  const workflow = WorkflowRunSchema.parse(data)
  return { 'If-Match': `W/"${workflow.version}"` }
}

export function listWorkflowNodes(workflowRunId: string): Promise<WorkflowNode[]> {
  return listWorkflowNodesApiV2WorkflowRunsWorkflowIdNodesGet<true>({ path: { workflow_id: workflowRunId },
    throwOnError: true }).then(({ data }) => data.items.map((item) => WorkflowNodeSchema.parse(item)))
}

export function getWorkflowGraph(workflowRunId: string): Promise<WorkflowGraph> {
  return getWorkflowGraphApiV2WorkflowRunsWorkflowIdGraphGet<true>({ path: { workflow_id: workflowRunId },
    throwOnError: true }).then(({ data }) => WorkflowGraphSchema.parse(data))
}

export function getWorkflowPreflight(
  workflowRunId: string,
  workflowNodeId?: string,
): Promise<WorkflowPreflight> {
  void workflowNodeId
  return workflowPreflightApiV2WorkflowRunsWorkflowIdPreflightGet<true>({ path: { workflow_id: workflowRunId },
    throwOnError: true }).then(({ data }) => WorkflowPreflightSchema.parse(data))
}

export interface SubmitWorkflowResponse {
  id: string
  workflow_run_id: string
  status: SubmitStatus
}

export function submitWorkflowRun(workflowRunId: string): Promise<SubmitWorkflowResponse> {
  return submitWorkflowApiV2WorkflowRunsWorkflowIdSubmissionsPost<true>({ path: { workflow_id: workflowRunId },
    headers: { 'Idempotency-Key': crypto.randomUUID() }, body: {}, throwOnError: true,
  }).then(({ data: submission }) => ({ ...submission, workflow_run_id: workflowRunId }))
}

/**
 * Preflight blockers carried by a refused submission.
 *
 * A submission has no 'blocked' status - the server refuses with a 409 Problem Details
 * instead - so the blockers the preflight computed are only reachable from the error.
 * The UI used to test the response for a status the API cannot return, so every refusal
 * surfaced as a generic failure and the reasons were discarded.
 */
export function preflightBlockersFrom(error: unknown): string[] {
  if (!(error instanceof ApiError) || error.status !== 409) return []
  const problem = error.payload as Partial<ProblemDetails> | undefined
  if (problem?.error_code !== 'workflow_preflight_failed') return []
  return (problem.errors ?? [])
    .map((item) => (typeof item.message === 'string' ? item.message : String(item.code ?? '')))
    .filter(Boolean)
}

export interface SubmitNodeOptions {
  /** Parameter overrides applied to the script preview. */
  override_params?: Record<string, unknown>
  /** Compute backend. Omit to let the server use its configured default. */
  compute_backend?: string
  timeout_minutes?: number
}

export function submitWorkflowNode(workflowRunId: string, options: SubmitNodeOptions = {}) {
  return submitWorkflowApiV2WorkflowRunsWorkflowIdSubmissionsPost<true>({ path: { workflow_id: workflowRunId },
    headers: { 'Idempotency-Key': crypto.randomUUID() }, body: {
      compute_backend: options.compute_backend,
      timeout_minutes: options.timeout_minutes ?? 180,
    }, throwOnError: true,
  }).then(({ data: submission }) => ({ job: submission.jobs[0] ?? null, status: submission.status }))
}

export interface ScriptPreviewResponse {
  workflow_node_id: string
  plugin_id: string | null
  script: string
  input_manifest: Record<string, unknown>
}

export function previewWorkflowNodeScript(nodeRunId: string, options: SubmitNodeOptions = {}) {
  return previewNodeScriptApiV2WorkflowNodesNodeIdScriptPreviewsPost<true>({ path: { node_id: nodeRunId },
    body: {
      compute_backend: options.compute_backend,
      overrides: options.override_params ?? {},
    }, throwOnError: true,
  }).then(({ data }) => data)
}

export function createWorkflowRun(projectId: string) {
  return postWorkflowApiV2ProjectsProjectIdWorkflowRunsPost<true>({ path: { project_id: projectId },
    body: { name: 'New workflow', nodes: [], edges: [] }, throwOnError: true,
  }).then(({ data }) => WorkflowRunSchema.parse(data))
}

export function addWorkflowNode(
  workflowRunId: string,
  payload: {
    node_type: string
    key: string
    model_plugin?: string
    model_plugin_id?: string
    parameters?: Record<string, unknown>
    position?: { x: number; y: number }
  },
) {
  return workflowIfMatch(workflowRunId).then((headers) => addWorkflowNodeApiV2WorkflowRunsWorkflowIdNodesPost<true>({
    path: { workflow_id: workflowRunId }, headers, body: {
      key: payload.key, node_type: payload.node_type,
      model_plugin: payload.model_plugin ?? payload.node_type,
      model_plugin_id: payload.model_plugin_id, parameters: payload.parameters ?? {}, position: payload.position,
    }, throwOnError: true,
  }).then(({ data }) => WorkflowNodeSchema.parse(data)))
}

export function saveWorkflowLayout(workflowRunId: string, layout: WorkflowLayout) {
  return workflowIfMatch(workflowRunId).then((headers) => patchWorkflowLayoutApiV2WorkflowRunsWorkflowIdLayoutPatch<true>({
    path: { workflow_id: workflowRunId }, headers, body: layout, throwOnError: true,
  }).then(({ data }) => WorkflowGraphSchema.parse(data))).then((graph) => graph.workflow)
}

export function updateWorkflowNode(
  workflowRunId: string,
  nodeRunId: string,
  payload: {
    parameters?: Record<string, unknown>
    position?: { x: number; y: number }
    status?: string
    input_bindings?: WorkflowInputBinding[]
    queue?: string | null
  },
) {
  return workflowIfMatch(workflowRunId).then((headers) => patchWorkflowNodeApiV2WorkflowRunsWorkflowIdNodesNodeIdPatch<true>({
    path: { workflow_id: workflowRunId, node_id: nodeRunId }, headers, body: {
      parameters: payload.parameters, position: payload.position,
      input_bindings: payload.input_bindings, queue: payload.queue,
    }, throwOnError: true,
  }).then(({ data }) => WorkflowNodeSchema.parse(data)))
}

export function validateWorkflowRun(workflowRunId: string) {
  return validateWorkflowApiV2WorkflowRunsWorkflowIdValidatePost<true>({ path: { workflow_id: workflowRunId },
    throwOnError: true }).then(({ data }) => data)
}

export function deleteWorkflowNode(workflowRunId: string, nodeRunId: string) {
  return workflowIfMatch(workflowRunId).then((headers) =>
    deleteWorkflowNodeApiV2WorkflowRunsWorkflowIdNodesNodeIdDelete<true>({
      path: { workflow_id: workflowRunId, node_id: nodeRunId }, headers, throwOnError: true,
    }).then(({ data }) => data),
  )
}
