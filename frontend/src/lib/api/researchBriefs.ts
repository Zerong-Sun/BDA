import './generatedTransport'
import { listBriefsApiV2ProjectsProjectIdResearchBriefsGet } from './generated/sdk.gen'
import type { BriefResponse } from './generated/types.gen'

/** The endpoint is UUID-paginated, not date-sorted. Finish reading before picking latest. */
export async function listAllResearchBriefs(projectId: string): Promise<BriefResponse[]> {
  const briefs = new Map<string, BriefResponse>()
  const seen = new Set<string>()
  let cursor: string | undefined
  do {
    const { data } = await listBriefsApiV2ProjectsProjectIdResearchBriefsGet<true>({
      path: { project_id: projectId }, query: { limit: 200, ...(cursor ? { cursor } : {}) }, throwOnError: true,
    })
    for (const brief of data.items) briefs.set(brief.id, brief)
    cursor = data.next_cursor || undefined
    if (cursor && seen.has(cursor)) throw new Error('Research brief pagination did not advance')
    if (cursor) seen.add(cursor)
  } while (cursor)
  return [...briefs.values()]
}

/** Legacy maintenance imports use this exact title for navigation, not research output. */
export function isProjectIndex(title: string) {
  return ['项目条目索引', 'project entry index'].includes(title.trim().toLowerCase())
}

export function latestProgressBrief(briefs: readonly BriefResponse[]) {
  return briefs.filter(brief => brief.status === 'progress_note' && brief.content?.trim() && !isProjectIndex(brief.title))
    .sort((a, b) => (Date.parse(b.updated_at) || Date.parse(b.created_at) || 0) - (Date.parse(a.updated_at) || Date.parse(a.created_at) || 0) || b.id.localeCompare(a.id))[0]
}
