import './generatedTransport'
import {
  deleteTimelineEntryApiV2TimelineEntryIdDelete,
  listTimelineApiV2ProjectsProjectIdTimelineGet,
  patchTimelineEntryApiV2TimelineEntryIdPatch,
  postTimelineEntryApiV2ProjectsProjectIdTimelinePost,
} from './generated/sdk.gen'
import { TimelineEntrySchema, TimelineEntryPageSchema, type TimelineEntry } from '../schemas/timeline'

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

/** The body both writes take. Built by `features/timeline/timelineEntryForm`, which owns
 *  the field rules; this module owns only the transport. */
export interface TimelineEntryBody {
  occurred_at: string
  entry_type: string
  decision_ref: string | null
  lane: string
  phase: string
  title: string
  summary: string
  body: string
  outcome: string
  provenance: Record<string, string[]>
  alternatives: Array<{ option: string; rejected_because: string }>
  code_refs: Array<{ path: string; role: string }>
  tags: string[]
}

export async function createTimelineEntry(
  projectId: string,
  body: TimelineEntryBody,
): Promise<TimelineEntry> {
  const created = await postTimelineEntryApiV2ProjectsProjectIdTimelinePost<true>({
    path: { project_id: projectId },
    body: body as never,
    throwOnError: true,
  })
  return TimelineEntrySchema.parse(created.data)
}

/** 412 here means someone else edited the entry between the load and the save; the
 *  caller reloads and never overwrites. */
export async function updateTimelineEntry(
  entryId: string,
  version: number,
  body: TimelineEntryBody,
): Promise<TimelineEntry> {
  const updated = await patchTimelineEntryApiV2TimelineEntryIdPatch<true>({
    path: { entry_id: entryId },
    headers: { 'If-Match': `W/"${version}"` },
    body: body as never,
    throwOnError: true,
  })
  return TimelineEntrySchema.parse(updated.data)
}

/** Deleting a decision removes a number from the record, so the version has to match:
 *  a stale tab must not be able to drop an entry someone else has since edited. */
export async function deleteTimelineEntry(entryId: string, version: number): Promise<void> {
  await deleteTimelineEntryApiV2TimelineEntryIdDelete<true>({
    path: { entry_id: entryId },
    headers: { 'If-Match': `W/"${version}"` },
    throwOnError: true,
  })
}
