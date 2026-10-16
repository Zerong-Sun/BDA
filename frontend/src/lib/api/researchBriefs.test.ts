import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/mocks/handlers'
import { latestProgressBrief, listAllResearchBriefs } from './researchBriefs'
import type { BriefResponse } from './generated/types.gen'

const brief = (id: string, updated_at: string, status = 'progress_note') => ({ id, title: id, content: 'Saved progress', status, updated_at, created_at: updated_at }) as BriefResponse

describe('complete research brief reading', () => {
  it('selects latest progress after all UUID-ordered pages, ignoring newer drafts', async () => {
    const cursors: (string | null)[] = []
    server.use(http.get('/api/v2/projects/:id/research-briefs', ({ request }) => {
      const cursor = new URL(request.url).searchParams.get('cursor')
      cursors.push(cursor)
      return HttpResponse.json(cursor ? { items: [brief('older-uuid-newer-date', '2026-10-16T00:00:00Z'), brief('draft', '2026-10-17T00:00:00Z', 'draft')], next_cursor: null } : { items: [brief('first-page', '2026-09-01T00:00:00Z')], next_cursor: 'page-two' })
    }))
    const rows = await listAllResearchBriefs('project')
    expect(cursors).toEqual([null, 'page-two'])
    expect(latestProgressBrief(rows)?.id).toBe('older-uuid-newer-date')
  })
  it('rejects a repeated cursor instead of labeling an incomplete page latest', async () => {
    server.use(http.get('/api/v2/projects/:id/research-briefs', () => HttpResponse.json({ items: [], next_cursor: 'stuck' })))
    await expect(listAllResearchBriefs('project')).rejects.toThrow('pagination did not advance')
  })
  it('does not return partial records when a later page fails', async () => {
    server.use(http.get('/api/v2/projects/:id/research-briefs', ({ request }) => new URL(request.url).searchParams.has('cursor')
      ? HttpResponse.json({ detail: 'Unavailable' }, { status: 503 })
      : HttpResponse.json({ items: [brief('first', '2026-10-01T00:00:00Z')], next_cursor: 'second' })))
    await expect(listAllResearchBriefs('project')).rejects.toThrow()
  })
})
