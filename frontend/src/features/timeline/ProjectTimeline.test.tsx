import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ProjectTimeline } from './ProjectTimeline'
import type { TimelineEntry } from '../../lib/schemas/timeline'
import { useAppStore } from '../../lib/store/appStore'

const { listAllTimeline, listResearchGoals } = vi.hoisted(() => ({
  listAllTimeline: vi.fn(),
  listResearchGoals: vi.fn(),
}))

vi.mock('../../lib/api/timeline', async () => {
  const actual = await vi.importActual<typeof import('../../lib/api/timeline')>('../../lib/api/timeline')
  return { ...actual, listAllTimeline }
})
vi.mock('../../lib/api/researchGoals', async () => {
  const actual =
    await vi.importActual<typeof import('../../lib/api/researchGoals')>('../../lib/api/researchGoals')
  return { ...actual, listResearchGoals }
})

const ENTRY: TimelineEntry = {
  id: 'e1',
  project_id: 'p1',
  occurred_at: '2026-08-26T16:00:00Z',
  entry_type: 'decision',
  decision_ref: 'D8',
  lane: 'dry',
    decided_by: 'human',
  phase: 'phase-2',
  title: 'a recorded call',
  summary: '',
  body: '',
  outcome: 'refuted',
  provenance: { job_ids: ['j1'] },
  alternatives: [],
  code_refs: [],
  supersedes_id: null,
  caused_by_id: null,
  tags: [],
  created_by: null,
  version: 1,
  created_at: '2026-08-26T16:00:00Z',
  updated_at: '2026-08-26T16:00:00Z',
}

beforeEach(() => {
  listAllTimeline.mockReset().mockResolvedValue([ENTRY])
  listResearchGoals.mockReset().mockResolvedValue([])
})

afterEach(cleanup)

describe('the filter row', () => {
  it('shows readable labels rather than the internal sentinels', async () => {
    // Base UI's Select.Value renders the raw value unless handed a formatter, so the
    // unfiltered state used to display `__all__` in all four controls.
    renderWithProviders(<ProjectTimeline projectId="p1" />)
    await waitFor(() => expect(screen.getByText('a recorded call')).toBeInTheDocument())

    expect(screen.queryByText('__all__')).not.toBeInTheDocument()
    expect(screen.queryByText('__nophase__')).not.toBeInTheDocument()
    for (const label of ['All lanes', 'All phases', 'All kinds', 'All outcomes']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    }
  })
})

describe('writing an entry', () => {
  it('offers a way in from a populated record', async () => {
    renderWithProviders(<ProjectTimeline projectId="p1" />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'New entry' })).toBeInTheDocument())
  })

  it('offers one from an empty record too, next to the bootstrap', async () => {
    listAllTimeline.mockResolvedValue([])
    renderWithProviders(<ProjectTimeline projectId="p1" hasPrompt />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'New entry' })).toBeInTheDocument())
  })
})

describe('the loading state', () => {
  it('shows skeletons, like every other page, and names itself for screen readers', () => {
    listAllTimeline.mockReturnValue(new Promise(() => {}))
    const { container } = renderWithProviders(<ProjectTimeline projectId="p1" />)
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
    expect(screen.getByText('Loading timeline...')).toHaveClass('sr-only')
  })
})

describe('having the Copilot explain a decision', () => {
  const decision = {
    ...ENTRY,
    summary: 'More sampling cannot unblock this route.',
    body: 'The reference set had no independent measurement to calibrate against.',
  }

  it('offers the entry point on the default tree view, where a reader actually lands', async () => {
    useAppStore.setState({ copilotDraft: '', copilotOpen: false })
    listAllTimeline.mockResolvedValue([decision])
    renderWithProviders(<ProjectTimeline projectId="p1" />)

    // The tree tab is selected on arrival; the control must exist without changing tabs.
    expect(await screen.findByRole('tab', { name: 'Decision tree' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(await screen.findByRole('button', { name: 'Ask Copilot to explain this decision' }))

    const draft = useAppStore.getState().copilotDraft
    // The record's own text travels in the question: research_context indexes findings,
    // references, datasets and structures, never timeline entries, so an entity id here
    // would ground the answer in nothing.
    expect(draft).toContain('D8')
    expect(draft).toContain('More sampling cannot unblock this route.')
    expect(draft).toContain('The reference set had no independent measurement to calibrate against.')
    expect(draft).toContain('job_ids:j1')
    expect(useAppStore.getState().copilotOpen).toBe(true)
  })

  it('offers it on the timeline list too', async () => {
    useAppStore.setState({ copilotDraft: '', copilotOpen: false })
    listAllTimeline.mockResolvedValue([decision])
    renderWithProviders(<ProjectTimeline projectId="p1" />)

    fireEvent.click(await screen.findByRole('tab', { name: 'Timeline' }))
    const asks = await screen.findAllByRole('button', { name: 'Ask Copilot to explain this decision' })
    fireEvent.click(asks[0])

    expect(useAppStore.getState().copilotDraft).toContain('D8')
  })

  it('does not offer it on an entry that is not a decision', async () => {
    listAllTimeline.mockResolvedValue([{ ...ENTRY, entry_type: 'result', decision_ref: null }])
    renderWithProviders(<ProjectTimeline projectId="p1" />)

    fireEvent.click(await screen.findByRole('tab', { name: 'Timeline' }))
    await waitFor(() => expect(screen.getByText('a recorded call')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Ask Copilot to explain this decision' })).not.toBeInTheDocument()
  })
})
