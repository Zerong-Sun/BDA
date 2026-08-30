import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { listAllCandidates } from './candidates'

function candidate(id: string) {
  return {
    id,
    project_id: 'proj_candidates',
    candidate_key: id,
    name: id,
    candidate_kind: 'design_candidate' as const,
    status: 'generated',
    rank: null,
    score: null,
    scores: {},
    properties: {},
    structure_artifact_id: null,
    complex_artifact_id: null,
    source_job_id: null,
    version: 1,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
  }
}

describe('candidate list API', () => {
  it('exhausts cursor pages using only the generated endpoint query contract', async () => {
    const requests: URL[] = []
    server.use(
      http.get('/api/v2/projects/proj_candidates/candidates', ({ request }) => {
        const url = new URL(request.url)
        requests.push(url)
        const cursor = url.searchParams.get('cursor')
        if (!cursor) {
          return HttpResponse.json({
            items: [candidate('cand_1'), candidate('cand_2')],
            next_cursor: 'cursor_2',
          })
        }
        return HttpResponse.json({
          items: [candidate('cand_2'), candidate('cand_3')],
          next_cursor: null,
        })
      }),
    )

    await expect(
      listAllCandidates('proj_candidates', {
        candidate_kind: 'design_candidate',
        limit: 2,
      }),
    ).resolves.toMatchObject({
      items: [
        expect.objectContaining({ id: 'cand_1' }),
        expect.objectContaining({ id: 'cand_2' }),
        expect.objectContaining({ id: 'cand_3' }),
      ],
      next_cursor: null,
    })

    expect(requests).toHaveLength(2)
    expect(requests.map((url) => Object.fromEntries(url.searchParams))).toEqual([
      { limit: '2', candidate_kind: 'design_candidate' },
      { cursor: 'cursor_2', limit: '2', candidate_kind: 'design_candidate' },
    ])
  })

  it('rejects a repeated cursor instead of looping forever', async () => {
    server.use(
      http.get('/api/v2/projects/proj_candidates/candidates', () =>
        HttpResponse.json({
          items: [candidate('cand_1')],
          next_cursor: 'stuck_cursor',
        }),
      ),
    )

    await expect(listAllCandidates('proj_candidates', { limit: 1 })).rejects.toThrow(
      'Candidate pagination repeated cursor "stuck_cursor".',
    )
  })
})
