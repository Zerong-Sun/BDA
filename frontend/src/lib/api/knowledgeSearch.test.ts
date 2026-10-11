import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/mocks/handlers'
import { createCopilotKnowledgeEntry, searchCopilotKnowledge, updateCopilotKnowledgeEntry } from './copilot'

const record = { id: 'entry-one', title: 'Protocol', content: 'Original content', entry_type: 'copilot_draft',
  tags: ['抗体'], source: {}, version: 3 }

describe('knowledge search transport and provenance', () => {
  it('forwards literal filters and cursor to the server without a local result cutoff', async () => {
    server.use(http.get('/api/v2/projects/project-one/knowledge', ({ request }) => {
      const search = new URL(request.url).searchParams
      expect(Object.fromEntries(search)).toEqual({ q: '抗体_100%', entry_type: 'copilot_draft', cursor: 'next-page', limit: '50' })
      return HttpResponse.json({ items: [{ ...record, source: { citation: { doi: '10.1/paper' }, source_message_id: 'origin' } }], next_cursor: 'another-page' })
    }))
    const result = await searchCopilotKnowledge('project-one', ' 抗体_100% ', 'copilot_draft', 'next-page')
    expect(result.next_cursor).toBe('another-page')
    expect(result.items[0]).toMatchObject({ source_type: 'unspecified', confidence: 'unassessed', review_status: 'unknown',
      citation: null, source: { citation: { doi: '10.1/paper' }, source_message_id: 'origin' } })
  })

  it('preserves original source fields and structured citations during a versioned edit', async () => {
    const source = { citation: { doi: '10.1/paper' }, source_message_id: 'origin', retrieval: { provider: 'user' }, type: 'copilot',
      editor_metadata: { imported_by: 'original-user' } }
    server.use(http.patch('/api/v2/knowledge/entry-one', async ({ request }) => {
      expect(request.headers.get('If-Match')).toBe('W/"3"')
      const body = await request.json() as { source: Record<string, unknown> }
      expect(body.source).toEqual({ ...source, summary: 'Edited summary', review_status: 'pending_review', confidence: 'unassessed',
        editor_metadata: { imported_by: 'original-user', entry_mode: 'manual' } })
      return HttpResponse.json({ ...record, source: body.source, version: 4 })
    }))
    const result = await updateCopilotKnowledgeEntry('entry-one', { title: 'Protocol', content: 'Edited content', category: 'copilot_draft',
      summary: 'Edited summary', source, confidence: 'unassessed', review_status: 'pending_review', metadata: { entry_mode: 'manual' } }, 3)
    expect(result.version).toBe(4)
    expect(result.source).toMatchObject(source)
  })

  it('returns server-recorded citation and assessment for newly saved knowledge', async () => {
    server.use(http.post('/api/v2/projects/project-one/knowledge', async ({ request }) => {
      const body = await request.json() as { source: Record<string, unknown> }
      expect(body.source).toMatchObject({ citation: 'https://example.org/source', type: 'manual', review_status: 'pending_review' })
      return HttpResponse.json({ ...record, source: body.source, version: 1 })
    }))
    const result = await createCopilotKnowledgeEntry('project-one', { title: 'Protocol', category: 'note', content: 'Original content',
      summary: 'Summary', source_type: 'manual', citation: 'https://example.org/source', review_status: 'pending_review' })
    expect(result).toMatchObject({ citation: 'https://example.org/source', confidence: 'unassessed', review_status: 'pending_review' })
  })
})
