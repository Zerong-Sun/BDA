import { z } from 'zod'
import { generatedClient } from './generatedTransport'

const CopilotResearchIssueSchema = z.object({
  kind: z.string(),
  path: z.string(),
  message: z.string(),
  reference: z.string().optional(),
  line: z.string().optional(),
  column: z.string().optional(),
})

const CopilotResearchImportResponseSchema = z.object({
  project_id: z.string(),
  project_name: z.string(),
  status: z.enum(['created', 'unchanged']),
  checksum: z.string(),
  counts: z.record(z.string(), z.number()),
})

export type CopilotResearchIssue = z.infer<typeof CopilotResearchIssueSchema>
export type CopilotResearchImportResponse = z.infer<typeof CopilotResearchImportResponseSchema>

export interface ResearchGenerationRequest {
  topic: string
  strata: string
  candidate_count: number
  use_external_evidence?: boolean
  evidence_cutoff?: string
  language: 'en' | 'zh'
  conversation_id?: string
}

export interface ResearchGeneration {
  id: string
  source_project_id: string
  status: 'pending' | 'ready' | 'failed' | 'imported'
  request: ResearchGenerationRequest
  draft: Record<string, unknown>
  validation: {
    valid?: boolean
    issues?: Array<Record<string, unknown>>
    citation_coverage?: number
    missing_categories?: string[]
    records_to_create?: Record<string, number>
    source_counts?: Record<string, number>
  }
  checksum: string | null
  imported_project_id: string | null
  error: string | null
  version: number
}

export function looksLikeCopilotResearchResult(content: string): boolean {
  return /["']schema_version["']\s*:\s*["']1\.0["']/.test(content)
    && /["'](?:nodes|references)["']\s*:/.test(content)
}

export function copilotResearchIssues(error: unknown): CopilotResearchIssue[] {
  const payload = error && typeof error === 'object' && 'payload' in error
    ? (error as { payload?: unknown }).payload
    : undefined
  if (!payload || typeof payload !== 'object' || !('errors' in payload)) return []
  const parsed = z.array(CopilotResearchIssueSchema).safeParse((payload as { errors?: unknown }).errors)
  return parsed.success ? parsed.data : []
}

export async function importCopilotResearchResult(
  organizationId: string,
  result: string,
): Promise<CopilotResearchImportResponse> {
  const response = await generatedClient.request<CopilotResearchImportResponse, unknown, true>({
    method: 'POST',
    url: '/api/v2/copilot-research-imports',
    body: { organization_id: organizationId, result },
    headers: { 'Content-Type': 'application/json' },
    throwOnError: true,
  })
  return CopilotResearchImportResponseSchema.parse(response.data)
}

export async function createResearchGeneration(projectId: string, payload: ResearchGenerationRequest) {
  const response = await generatedClient.request<{ generation_id: string; operation_id: string; status: string }, unknown, true>({
    method: 'POST',
    url: '/api/v2/projects/{project_id}/research-generations',
    path: { project_id: projectId },
    body: payload,
    headers: { 'Content-Type': 'application/json' },
    throwOnError: true,
  })
  return response.data as unknown as { generation_id: string; operation_id: string; status: string }
}

export async function getResearchGeneration(generationId: string): Promise<ResearchGeneration> {
  const response = await generatedClient.request<ResearchGeneration, unknown, true>({
    method: 'GET',
    url: '/api/v2/research-generations/{generation_id}',
    path: { generation_id: generationId },
    throwOnError: true,
  })
  return response.data as unknown as ResearchGeneration
}

export async function waitForResearchGeneration(generationId: string): Promise<ResearchGeneration> {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const generation = await getResearchGeneration(generationId)
    if (generation.status !== 'pending') return generation
    await new Promise((resolve) => window.setTimeout(resolve, 1000))
  }
  throw new Error('Research generation did not finish within two minutes.')
}

export async function importResearchGeneration(generationId: string, checksum: string) {
  const response = await generatedClient.request<CopilotResearchImportResponse & { generation_id: string }, unknown, true>({
    method: 'POST',
    url: '/api/v2/research-generations/{generation_id}/import',
    path: { generation_id: generationId },
    body: { checksum },
    headers: { 'Content-Type': 'application/json' },
    throwOnError: true,
  })
  return response.data as unknown as CopilotResearchImportResponse & { generation_id: string }
}
