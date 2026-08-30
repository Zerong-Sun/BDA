import './generatedTransport'
import {
  getCandidateApiV2CandidatesCandidateIdGet,
  listCandidateMetricsApiV2CandidatesCandidateIdMetricsGet,
  listCandidatesApiV2ProjectsProjectIdCandidatesGet,
  postDeliveryApiV2ProjectsProjectIdDeliveryPackagesPost,
} from './generated/sdk.gen'
import {
  CandidateListSchema,
  CandidateMetricListSchema,
  CandidateSchema,
  type CandidateListResponse,
} from '../schemas/candidate'

export interface CandidateQuery {
  candidate_kind?: 'design_candidate' | 'research_target'
  limit?: number
  cursor?: string
}

export async function listCandidates(projectId: string, query: CandidateQuery = {}) {
  const page = await listCandidatesApiV2ProjectsProjectIdCandidatesGet<true>({
    path: { project_id: projectId },
    query: { cursor: query.cursor, limit: query.limit ?? 50, candidate_kind: query.candidate_kind },
    throwOnError: true,
  })
  return CandidateListSchema.parse(page.data)
}

const MAX_CANDIDATE_CURSOR_PAGES = 1_000

export async function listAllCandidates(
  projectId: string,
  query: Omit<CandidateQuery, 'cursor'> = {},
) {
  const candidatesById = new Map<string, CandidateListResponse['items'][number]>()
  const seenCursors = new Set<string>()
  let cursor: string | undefined

  for (let pageIndex = 0; pageIndex < MAX_CANDIDATE_CURSOR_PAGES; pageIndex += 1) {
    if (cursor) {
      if (seenCursors.has(cursor)) {
        throw new Error(`Candidate pagination repeated cursor "${cursor}".`)
      }
      seenCursors.add(cursor)
    }

    const page = await listCandidates(projectId, { ...query, cursor })
    for (const candidate of page.items) {
      candidatesById.set(candidate.id, candidate)
    }

    if (!page.next_cursor) {
      return {
        items: [...candidatesById.values()],
        next_cursor: null,
      } satisfies CandidateListResponse
    }
    cursor = page.next_cursor
  }

  throw new Error(
    `Candidate pagination exceeded ${MAX_CANDIDATE_CURSOR_PAGES.toLocaleString()} pages.`,
  )
}

export async function getCandidate(candidateId: string) {
  const candidate = await getCandidateApiV2CandidatesCandidateIdGet<true>({
    path: { candidate_id: candidateId }, throwOnError: true,
  })
  return CandidateSchema.parse(candidate.data)
}

export async function listCandidateMetrics(candidateId: string) {
  const page = await listCandidateMetricsApiV2CandidatesCandidateIdMetricsGet<true>({
    path: { candidate_id: candidateId }, throwOnError: true,
  })
  return CandidateMetricListSchema.parse(page.data)
}

export async function downloadCandidateStructures(
  projectId: string,
  candidateIds: string[],
  filename = 'candidate_structures.zip',
) {
  return postDeliveryApiV2ProjectsProjectIdDeliveryPackagesPost<true>({
    path: { project_id: projectId },
    body: { candidate_ids: candidateIds, name: filename, include_experiment_results: true },
    throwOnError: true,
  }).then((response) => response.data)
}

export type { CandidateListResponse }
