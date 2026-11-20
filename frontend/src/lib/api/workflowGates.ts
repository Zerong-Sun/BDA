import { generatedClient } from './generatedTransport'
import { WorkflowGraphSchema, type WorkflowEdge } from '../schemas/workflow'

export interface GateRules {
  operator: 'and' | 'or'
  conditions: Array<{
    metric: string
    op: 'gt' | 'gte' | 'lt' | 'lte' | 'eq' | 'ne'
    value: number
  }>
  sort_metric?: string | null
  descending: boolean
  top_n?: number | null
}
export interface GatePolicy extends Record<string, unknown> {
  mode: 'automatic' | 'manual' | 'review' | 'integrity' | 'dependency'
  configured: boolean
  rules: GateRules
  structure?: {
    preset?: 'multi_helix' | 'structured' | 'beta_sheet'
    min_strands?: number
    chains: string[]
    min_helices: number
    min_helix_length: number
    start?: number | null
    end?: number | null
  } | null
  script_preview_id?: string | null
  script?: string | null
}
export interface GateSummary {
  id: string
  edge_id: string
  status: string
  version: number
  revision: number
  preview: boolean
  total: number
  passed: number
  selected: number
  selected_ids: string[]
  error?: string
  created_at: string
  source_job_id?: string
  released_by?: string
  policy?: GatePolicy
}
export interface GateResult {
  id: string
  key: string
  sequence?: string
  passed: boolean
  needs_attention?: boolean
  selected: boolean
  reasons: string[]
  metrics: Record<string, number>
  files: Array<{ artifact_id: string; port: string; selector: Record<string, unknown> }>
}


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
