import { awaitOperation } from './operations'
import { generatedClient } from './generatedTransport'

export interface ResearchGapResolutionAccepted {
  operation_id: string
  research_target_id: string
  status: string
}

export async function createResearchGapResolution(
  projectId: string,
  researchTargetId: string,
): Promise<ResearchGapResolutionAccepted> {
  const response = await generatedClient.request<ResearchGapResolutionAccepted, unknown, true>({
    method: 'POST',
    url: '/api/v2/projects/{project_id}/research-targets/{research_target_id}/gap-resolutions',
    path: { project_id: projectId, research_target_id: researchTargetId },
    body: { resolve_references: true, resolve_structure: true },
    headers: { 'Content-Type': 'application/json' },
    throwOnError: true,
  })
  return response.data as ResearchGapResolutionAccepted
}

/** Gap resolution fetches references and structures, so it is the slowest of the three. */
export function waitForResearchGapResolution(operationId: string) {
  return awaitOperation(operationId, { timeoutMs: 180_000 })
}
