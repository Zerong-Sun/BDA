import { generatedClient } from './generatedTransport'
import { WorkflowGraphSchema, type WorkflowEdge } from '../schemas/workflow'
import type { GatePolicy, GateResult, GateSummary } from '../../features/workflow/gates'

async function call<T>(
  url: string,
  method: 'GET' | 'POST' | 'PUT',
  body?: unknown,
  version?: number,
): Promise<T> {
  const result = await generatedClient.request({
    url: `/api/v2${url}`,
    method,
    body,
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...(version === undefined ? {} : { 'If-Match': `W/"${version}"` }),
    },
    throwOnError: true,
  })
  return result.data as T
}
export async function saveConnections(id: string, edges: WorkflowEdge[], version: number) {
  return WorkflowGraphSchema.parse(
    await call(`/workflow-runs/${id}/connections`, 'PUT', { edges }, version),
  )
}
export const listGates = (id: string) =>
  call<{ items: GateSummary[] }>(`/workflow-runs/${id}/gates`, 'GET')
export const gateResults = (
  id: string,
  gate: string,
  q: string,
  offset: number,
  sort: string,
  descending: boolean,
) =>
  call<{ gate: GateSummary; items: GateResult[]; total: number }>(
    `/workflow-runs/${id}/gates/${gate}/results?q=${encodeURIComponent(q)}&offset=${offset}&limit=100&descending=${descending}${sort ? `&sort_metric=${encodeURIComponent(sort)}` : ''}`,
    'GET',
  )
export const releaseGate = (id: string, gate: GateSummary, selected: string[]) =>
  call<GateSummary>(`/workflow-runs/${id}/gates/${gate.id}/release`, 'POST', {
    version: gate.version,
    selected_ids: selected,
  })
export const retryGate = (id: string, gate: string) =>
  call<GateSummary>(`/workflow-runs/${id}/gates/${gate}/retry`, 'POST', {})
export const previewGate = (id: string, edge: string, policy: GatePolicy, source_job_id?: string) =>
  call<GateSummary>(`/workflow-runs/${id}/connections/${edge}/previews`, 'POST', {
    policy,
    source_job_id,
  })
export interface Suggestions {
  fingerprint: string
  workflow_version: number
  objective: string
  upstream_results?: Array<{
    node_key: string
    port: string
    job_id: string
    attempt: number
    count: number
    metrics: string[]
  }>
  suggestions: Array<{
    parameter: string
    current: unknown
    value: unknown
    source: string
    reason: string
  }>
}
export const suggestParameters = (id: string, node: string) =>
  call<Suggestions>(`/workflow-runs/${id}/nodes/${node}/parameter-suggestions`, 'GET')
export interface ImportedScript {
  filename: string
  language: 'python' | 'shell'
  source: string
  checksum_sha256: string
  parameters: Record<string, unknown>
  commands?: string[]
  inputs?: string[]
  outputs?: string[]
  warnings: string[]
}
export const importScript = (id: string, filename: string, source: string) =>
  call<ImportedScript>(`/workflow-runs/${id}/script-imports`, 'POST', {
    filename,
    source,
    language: filename.endsWith('.py') ? 'python' : 'shell',
  })

export const previewSources = (id: string, edge: string) =>
  call<{
    items: Array<{
      id: string
      node_key: string
      attempt: number
      created_at: string
      count: number
    }>
  }>(`/workflow-runs/${id}/connections/${edge}/preview-sources`, 'GET')
