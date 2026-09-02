import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { DryLabDecisionTree } from './DryLabDecisionTree'

const listAllTimeline = vi.hoisted(() => vi.fn())
const listResearchGoals = vi.hoisted(() => vi.fn())

vi.mock('../../lib/api/timeline', () => ({ listAllTimeline }))
vi.mock('../../lib/api/researchGoals', () => ({ listResearchGoals }))

const entry = (overrides: Record<string, unknown> = {}) => ({
  id: 'decision-one',
  project_id: 'project-one',
  occurred_at: '2026-08-01T10:00:00Z',
  entry_type: 'decision',
  decision_ref: 'D105',
  lane: 'dry',
  phase: 'binder-route-a',
  title: 'Advance the restrained backbone route',
  summary: 'The restrained route retained the target interface.',
  body: '## Decision basis\n\nAdvance because the interface checks passed.',
  outcome: 'supported',
  provenance: { workflow_run_ids: ['workflow-one'], candidate_ids: ['candidate-one'] },
  alternatives: [],
  code_refs: [{ path: 'qm-scripts/plugins/rfdiffusion/run.sh', role: 'backbone generation' }],
  supersedes_id: null,
  caused_by_id: null,
  tags: ['dry-lab'],
  created_by: 'user-one',
  version: 1,
  created_at: '2026-08-01T10:00:00Z',
  updated_at: '2026-08-01T10:00:00Z',
  ...overrides,
})

const goal = (id: string, entryIds: string[] = []) => ({
  id,
  project_id: 'project-one',
  parent_id: null,
  title: id,
  detail: '',
  status: 'open',
  sort_order: 0,
  tags: [],
  version: 1,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
  links: entryIds.map((resourceId, index) => ({
    id: `${id}-l${index}`,
    goal_id: id,
    resource_type: 'timeline_entry',
    resource_id: resourceId,
    note: '',
  })),
})

describe('DryLabDecisionTree', () => {
  beforeEach(() => {
    useAppStore.setState({ language: 'en' })
    listAllTimeline.mockReset()
    listResearchGoals.mockReset()
  })

  afterEach(cleanup)

  it('shows the same tree the timeline page shows, not a second one', async () => {
    // The point of the convergence: goals are the vertical structure here too, so a
    // decision appears under the goal it is linked to rather than under its phase.
    listAllTimeline.mockResolvedValue([entry()])
    listResearchGoals.mockResolvedValue([goal('produce an expressible candidate', ['decision-one'])])

    renderWithProviders(<DryLabDecisionTree projectId="project-one" />)

    expect(await screen.findByText('produce an expressible candidate')).toBeInTheDocument()
    expect(screen.getByText('Advance the restrained backbone route')).toBeInTheDocument()
    expect(screen.getByText('D105')).toBeInTheDocument()
    expect(listAllTimeline).toHaveBeenCalledWith('project-one')
    expect(listResearchGoals).toHaveBeenCalledWith('project-one')
  })

  it('does not bury a decision that hangs off no goal', async () => {
    listAllTimeline.mockResolvedValue([entry({ id: 'loose', title: 'Unattached ruling' })])
    listResearchGoals.mockResolvedValue([goal('a goal with nothing under it')])

    renderWithProviders(<DryLabDecisionTree projectId="project-one" />)

    expect(await screen.findByText('Unattached ruling')).toBeInTheDocument()
  })

  it('shows an honest empty state without inventing a decision tree', async () => {
    listAllTimeline.mockResolvedValue([])
    listResearchGoals.mockResolvedValue([])
    renderWithProviders(<DryLabDecisionTree projectId="project-one" />)
    expect(await screen.findByText(/No goals or decisions to draw yet/)).toBeInTheDocument()
  })

  it('offers a retry and recovers after a request fails', async () => {
    listAllTimeline.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce([entry()])
    listResearchGoals.mockResolvedValue([goal('g', ['decision-one'])])

    renderWithProviders(<DryLabDecisionTree projectId="project-one" />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the project timeline.')
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Advance the restrained backbone route')).toBeInTheDocument()
    expect(listAllTimeline).toHaveBeenCalledTimes(2)
  })
})
