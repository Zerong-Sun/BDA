import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CandidatesPage } from '../../app/Candidates'
import { useAppStore } from '../../lib/store/appStore'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'

vi.mock('./CandidateFilters', () => ({
  CandidateFilters: ({
    onSearchChange,
    onStatusChange,
    onPriorityOnlyChange,
  }: {
    onSearchChange: (value: string) => void
    onStatusChange: (value: string) => void
    onPriorityOnlyChange: (value: boolean) => void
  }) => (
    <div>
      <button type="button" onClick={() => onSearchChange('kinase')}>
        Filter later-page search
      </button>
      <button type="button" onClick={() => onStatusChange('Validated')}>
        Filter later-page status
      </button>
      <button type="button" onClick={() => onPriorityOnlyChange(true)}>
        Filter later-page priority
      </button>
      <button
        type="button"
        onClick={() => {
          onSearchChange('')
          onStatusChange('All')
          onPriorityOnlyChange(false)
        }}
      >
        Reset candidate filters
      </button>
    </div>
  ),
}))

vi.mock('./CandidateDetail', () => ({
  CandidateDetail: () => null,
}))

vi.mock('../workflow/ComputeStatusStrip', () => ({
  ComputeStatusStrip: () => null,
}))

vi.mock('../../components/ui/NextStep', () => ({
  NextStep: () => null,
}))

function candidate(
  id: string,
  {
    name = id,
    status = 'Reserve',
    decision = 'Review',
  }: { name?: string; status?: string; decision?: string } = {},
) {
  return {
    id,
    project_id: 'proj_candidates_integration',
    candidate_key: id,
    name,
    candidate_kind: 'design_candidate' as const,
    status,
    rank: null,
    score: null,
    scores: {},
    properties: { decision },
    structure_artifact_id: null,
    complex_artifact_id: null,
    source_job_id: null,
    version: 1,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
  }
}

describe('CandidatesPage complete cursor collection', () => {
  beforeEach(() => {
    window.location.hash = '/candidates?project=proj_candidates_integration'
    useAppStore.setState({
      activeProjectId: '',
      language: 'en',
    })
  })

  afterEach(() => {
    cleanup()
    window.location.hash = ''
  })

  it('filters search, status, and priority matches fetched only from later cursor pages', async () => {
    const requestedCursors: Array<string | null> = []
    server.use(
      http.get('/api/v2/projects', () =>
        HttpResponse.json({
          items: [
            {
              id: 'proj_candidates_integration',
              organization_id: 'org_test',
              name: 'Cursor candidates',
              project_type: 'protein_design',
              status: 'active',
              owner_id: 'user_test',
              summary: '',
              primary_target_id: null,
              version: 1,
              created_at: '2026-07-01T00:00:00Z',
              updated_at: '2026-07-01T00:00:00Z',
            },
          ],
          next_cursor: null,
        }),
      ),
      http.get('/api/v2/projects/proj_candidates_integration/candidate-funnel', () =>
        HttpResponse.json({
          generated: 4,
          designed: 4,
          folded: 4,
          scored: 4,
          ordered: 0,
        }),
      ),
      http.get('/api/v2/projects/proj_candidates_integration/candidates', ({ request }) => {
        const cursor = new URL(request.url).searchParams.get('cursor')
        requestedCursors.push(cursor)
        if (!cursor) {
          return HttpResponse.json({
            items: [candidate('cand_first_page')],
            next_cursor: 'cursor_search',
          })
        }
        if (cursor === 'cursor_search') {
          return HttpResponse.json({
            items: [candidate('cand_search_later', { name: 'Kinase binder' })],
            next_cursor: 'cursor_status',
          })
        }
        if (cursor === 'cursor_status') {
          return HttpResponse.json({
            items: [candidate('cand_status_later', { status: 'Validated' })],
            next_cursor: 'cursor_priority',
          })
        }
        return HttpResponse.json({
          items: [candidate('cand_priority_later', { decision: 'Anchor' })],
          next_cursor: null,
        })
      }),
    )

    renderWithProviders(<CandidatesPage />)

    expect(
      await screen.findByRole('button', {
        name: 'View details for candidate cand_priority_later',
      }),
    ).toBeInTheDocument()
    expect(requestedCursors).toEqual([
      null,
      'cursor_search',
      'cursor_status',
      'cursor_priority',
    ])

    fireEvent.click(screen.getByRole('button', { name: 'Filter later-page search' }))
    expect(
      screen.getByRole('button', { name: 'View details for candidate cand_search_later' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'View details for candidate cand_first_page' }),
    ).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Reset candidate filters' }))
    fireEvent.click(screen.getByRole('button', { name: 'Filter later-page status' }))
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'View details for candidate cand_status_later' }),
      ).toBeInTheDocument(),
    )
    expect(
      screen.queryByRole('button', { name: 'View details for candidate cand_first_page' }),
    ).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Reset candidate filters' }))
    fireEvent.click(screen.getByRole('button', { name: 'Filter later-page priority' }))
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'View details for candidate cand_priority_later' }),
      ).toBeInTheDocument(),
    )
    expect(
      screen.queryByRole('button', { name: 'View details for candidate cand_first_page' }),
    ).not.toBeInTheDocument()
  })
})
