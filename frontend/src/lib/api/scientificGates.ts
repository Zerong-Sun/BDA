import { generatedClient } from './generatedTransport'

async function call<T>(path: string, method: 'GET' | 'POST' = 'GET', body?: unknown): Promise<T> {
  const result = await generatedClient.request({ url: `/api/v2${path}`, method, body,
    headers: body ? { 'Content-Type': 'application/json' } : undefined, throwOnError: true })
  return result.data as T
}
export interface ScientificSource {
  document_id: string; chunk_id: string; title: string; quote: string; locator: string;
  url?: string | null; supported_methods?: string[]
}
export interface ScientificParameter {
  path: string; value: unknown; unit: string; meaning: string; method_key: string;
  method_version: string; source_indexes: number[]
}
export interface ScientificCalibration {
  artifact_id: string; raw_data_artifact_ids: string[]; positive_controls: string[];
  negative_controls: string[]; construct: string; protocol: string; acceptance_criteria: string; summary: string
}
export interface ScientificEvidenceInput {
  workflow_version: number;
  sources: Array<Pick<ScientificSource, 'document_id' | 'chunk_id' | 'quote' | 'locator'> & { supported_methods: string[] }>;
  parameters: ScientificParameter[]; calibration: ScientificCalibration | null; applicability: string
}
export interface ScientificEvidence {
  id: string; evidence: ScientificEvidenceInput; issues: string[]; approved: boolean;
  created_at: string; sources: ScientificSource[];
  review?: { decision: string; rationale: string; actor_id: string; created_at: string } | null
}
export interface ScientificGate {
  edge_id: string; mode: string; required: boolean; allowed: boolean; blockers: string[];
  binding: { project_id: string; workflow_version: number; parameter_hash: string;
    required_parameters: Record<string, unknown>;
    required_methods: Record<string, { method_key: string | null; method_version: string | null }> };
  items: ScientificEvidence[]
}
export const scientificGates = (workflow: string) => call<{ workflow_version: number; items: ScientificGate[] }>(`/workflow-runs/${workflow}/scientific-gates`)
export const scientificSources = (workflow: string, edge: string, query: string) =>
  call<{ items: ScientificSource[] }>(`/workflow-runs/${workflow}/connections/${edge}/scientific-evidence/sources?q=${encodeURIComponent(query)}`)
export const saveScientificEvidence = (workflow: string, edge: string, body: ScientificEvidenceInput) =>
  call<ScientificEvidence>(`/workflow-runs/${workflow}/connections/${edge}/scientific-evidence`, 'POST', body)
export const reviewScientificEvidence = (workflow: string, edge: string, evidence: string, body: { workflow_version: number; decision: 'approve' | 'reject'; rationale: string }) =>
  call<ScientificGate>(`/workflow-runs/${workflow}/connections/${edge}/scientific-evidence/${evidence}/review`, 'POST', body)
