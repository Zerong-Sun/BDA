import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { ActivityDrawer } from './ActivityDrawer'

const api = vi.hoisted(() => ({ list: vi.fn() }))

vi.mock('../../lib/api/operations', async () => {
  const actual = await vi.importActual<typeof import('../../lib/api/operations')>(
    '../../lib/api/operations',
  )
  return { ...actual, listOperations: api.list }
})

vi.mock('../../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => ({ projectId: 'project-one', activeProject: null, projects: [] }),
}))

const NOW = '2026-08-28T10:00:00Z'

function operation(overrides: Record<string, unknown>) {
  return {
    id: 'op-1',
    project_id: 'project-one',
    organization_id: null,
    kind: 'literature.search',
    resource_type: 'project',
    resource_id: 'res-1',
    status: 'running',
    progress: {},
    result: {},
    error_code: null,
    error_message: null,
    version: 1,
    created_at: NOW,
    updated_at: NOW,
    started_at: NOW,
    finished_at: null,
    ...overrides,
  }
}

describe('ActivityDrawer', () => {
  beforeEach(() => {
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'researcher' }))
    useAppStore.setState({ activityOpen: true })
    api.list.mockResolvedValue({ items: [], next_cursor: null })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    useAppStore.setState({ activityOpen: false })
  })

  it('opens on the caller’s own work rather than the whole project', async () => {
    renderWithProviders(<ActivityDrawer />)
    await waitFor(() => expect(api.list).toHaveBeenCalled())
    expect(api.list.mock.calls[0][0]).toMatchObject({ mine: true })
  })

  it('shows a failure with the server’s own message', async () => {
    api.list.mockResolvedValue({
      items: [
        operation({
          id: 'op-failed',
          kind: 'experiment_results.import',
          status: 'failed',
          error_message: 'row 42 references an unknown candidate',
          finished_at: NOW,
        }),
      ],
      next_cursor: null,
    })
    renderWithProviders(<ActivityDrawer />)
    expect(await screen.findByText('experiment_results.import')).toBeInTheDocument()
    expect(screen.getByText('row 42 references an unknown candidate')).toBeInTheDocument()
  })

  it('offers a researcher no "everything" scope, because the server would fence it anyway', async () => {
    renderWithProviders(<ActivityDrawer />)
    fireEvent.click(await screen.findByRole('combobox', { name: 'Scope' }))
    expect(await screen.findByRole('option', { name: 'Mine' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'This project' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Everything' })).toBeNull()
  })

  it('offers an admin the global scope', async () => {
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'admin' }))
    renderWithProviders(<ActivityDrawer />)
    fireEvent.click(await screen.findByRole('combobox', { name: 'Scope' }))
    expect(await screen.findByRole('option', { name: 'Everything' })).toBeInTheDocument()
  })

  it('links a candidate operation back to the candidate it acted on', async () => {
    api.list.mockResolvedValue({
      items: [operation({ resource_type: 'candidate', resource_id: 'cand-9' })],
      next_cursor: null,
    })
    renderWithProviders(<ActivityDrawer />)
    const link = await screen.findByRole('link', { name: /candidate/ })
    // The test harness mounts a hash router, hence the leading '#'.
    expect(link).toHaveAttribute('href', '#/candidates?project=project-one&candidate=cand-9')
  })
})
