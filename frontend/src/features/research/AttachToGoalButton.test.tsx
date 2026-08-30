import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { ResearchGoal } from '../../lib/api/researchGoals'
import { AttachToGoalButton } from './AttachToGoalButton'

const api = vi.hoisted(() => ({ list: vi.fn(), attach: vi.fn() }))

vi.mock('../../lib/api/researchGoals', async () => {
  const actual = await vi.importActual<typeof import('../../lib/api/researchGoals')>(
    '../../lib/api/researchGoals',
  )
  return { ...actual, listResearchGoals: api.list, attachToResearchGoal: api.attach }
})

function goal(overrides: Partial<ResearchGoal> & { id: string; title: string }): ResearchGoal {
  return {
    project_id: 'project-one',
    parent_id: null,
    detail: '',
    status: 'open',
    sort_order: 0,
    tags: [],
    links: [],
    version: 1,
    created_at: '2026-08-28T00:00:00Z',
    updated_at: '2026-08-28T00:00:00Z',
    ...overrides,
  } as ResearchGoal
}

describe('AttachToGoalButton', () => {
  beforeEach(() => {
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'researcher' }))
    api.attach.mockResolvedValue({ id: 'link-new' })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('attaches the resource to the goal that was picked', async () => {
    api.list.mockResolvedValue([
      goal({ id: 'root', title: 'Can this bind CBD?' }),
      goal({ id: 'child', title: 'Does it fold?', parent_id: 'root' }),
    ])
    renderWithProviders(
      <AttachToGoalButton projectId="project-one" resourceType="candidate" resourceId="cand-1" />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Goal' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Does it fold?' }))

    await waitFor(() =>
      expect(api.attach).toHaveBeenCalledWith('child', {
        resource_type: 'candidate',
        resource_id: 'cand-1',
      }),
    )
  })

  it('shows a goal this resource already sits on as done, and refuses a second click', async () => {
    // The server returns the existing link rather than erroring, so a repeat is
    // harmless - but offering the click implies it would mean something.
    api.list.mockResolvedValue([
      goal({
        id: 'root',
        title: 'Can this bind CBD?',
        links: [
          { id: 'link-one', goal_id: 'root', resource_type: 'candidate', resource_id: 'cand-1', note: '' },
        ],
      }),
    ])
    renderWithProviders(
      <AttachToGoalButton projectId="project-one" resourceType="candidate" resourceId="cand-1" />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Goal' }))
    const item = await screen.findByRole('menuitem', { name: /Can this bind CBD\?/ })
    fireEvent.click(item)

    expect(api.attach).not.toHaveBeenCalled()
  })

  it('says where to make a goal when the project has none', async () => {
    api.list.mockResolvedValue([])
    renderWithProviders(
      <AttachToGoalButton projectId="project-one" resourceType="job" resourceId="job-1" />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Goal' }))
    expect(
      await screen.findByRole('menuitem', { name: 'No goals yet — add one on the Research page.' }),
    ).toBeInTheDocument()
  })
})
