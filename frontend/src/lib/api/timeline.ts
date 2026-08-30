import './generatedTransport'
import { listTimelineApiV2ProjectsProjectIdTimelineGet } from './generated/sdk.gen'
import { TimelineEntryPageSchema, type TimelineEntry } from '../schemas/timeline'

export interface TimelineQuery {
  entry_type?: string
  phase?: string
  outcome?: string
  limit?: number
  cursor?: string
}

export async function listTimeline(projectId: string, query: TimelineQuery = {}) {
  const page = await listTimelineApiV2ProjectsProjectIdTimelineGet<true>({
    path: { project_id: projectId },
    query: {
      cursor: query.cursor,
      limit: query.limit ?? 100,
      entry_type: query.entry_type,
      phase: query.phase,
      outcome: query.outcome,
    },
    throwOnError: true,
  })
  return TimelineEntryPageSchema.parse(page.data)
}

const MAX_TIMELINE_PAGES = 200

/** The timeline is read whole (it is a project's history, not a feed), so follow the
 *  cursor to the end. Bounded, and repeated cursors abort, so a paging bug surfaces as
 *  an error instead of an infinite loop. */
export async function listAllTimeline(
  projectId: string,
  query: Omit<TimelineQuery, 'cursor'> = {},
): Promise<TimelineEntry[]> {
  const items: TimelineEntry[] = []
  const seen = new Set<string>()
  let cursor: string | undefined

  for (let page = 0; page < MAX_TIMELINE_PAGES; page += 1) {
    if (cursor) {
      if (seen.has(cursor)) throw new Error(`Timeline pagination repeated cursor "${cursor}".`)
      seen.add(cursor)
    }
    const result = await listTimeline(projectId, { ...query, cursor })
    items.push(...result.items)
    if (!result.next_cursor) return items
    cursor = result.next_cursor
  }
  throw new Error(`Timeline pagination exceeded ${MAX_TIMELINE_PAGES} pages.`)
}
