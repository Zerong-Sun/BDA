import { cleanup, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { TimelineEntrySchema, type TimelineEntry } from '../../lib/schemas/timeline'
import type { ResearchGoal } from '../../lib/api/researchGoals'
import { DecisionTreeView } from './DecisionTreeView'

afterEach(cleanup)

function entry(id: string, overrides: Partial<TimelineEntry> = {}): TimelineEntry {
  return TimelineEntrySchema.parse({
    id,
    project_id: 'p1',
    occurred_at: '2026-08-03T09:00:00Z',
    entry_type: 'decision',
    phase: '',
    title: id,
    summary: '',
    body: '',
    outcome: 'unspecified',
    provenance: {},
    code_refs: [],
    supersedes_id: null,
    caused_by_id: null,
    tags: [],
    created_by: null,
    version: 1,
    created_at: '2026-08-03T09:00:00Z',
    updated_at: '2026-08-03T09:00:00Z',
    ...overrides,
  })
}

function goal(id: string, entryIds: string[] = []): ResearchGoal {
  return {
    id,
    project_id: 'p1',
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
  } as ResearchGoal
}

describe('DecisionTreeView', () => {
  it('shows the decision number so the tree and DECISIONS.md can be read together', () => {
    renderWithProviders(
      <DecisionTreeView goals={[goal('g', ['d'])]} entries={[entry('d', { decision_ref: 'D105' })]} />,
    )
    expect(screen.getByText('D105')).toBeInTheDocument()
  })

  it('marks a decision that rests on nothing the platform can resolve', () => {
    // Rendering it identically to a well-evidenced one is how the record reads as
    // complete while pointing at almost nothing.
    renderWithProviders(<DecisionTreeView goals={[goal('g', ['d'])]} entries={[entry('d')]} />)
    expect(screen.getByText(/no evidence linked/i)).toBeInTheDocument()
  })

  it('does not mark a decision that cites evidence', () => {
    renderWithProviders(
      <DecisionTreeView goals={[goal('g', ['d'])]} entries={[entry('d', { provenance: { job_ids: ['j'] } })]} />,
    )
    expect(screen.queryByText(/no evidence linked/i)).not.toBeInTheDocument()
  })

  it('shows both lane marks for a decision that spans dry and wet', () => {
    renderWithProviders(
      <DecisionTreeView
        goals={[goal('g', ['d'])]}
        entries={[entry('d', { lane: 'both', provenance: { protein_ids: ['p'], job_ids: ['j'] } })]}
      />,
    )
    expect(screen.getByText('Dry')).toBeInTheDocument()
    expect(screen.getByText('Wet')).toBeInTheDocument()
  })

  it('flags a wet-lane claim whose evidence is not actually bench evidence', () => {
    renderWithProviders(
      <DecisionTreeView
        goals={[goal('g', ['d'])]}
        entries={[entry('d', { lane: 'wet', provenance: { external_refs: ['lsf:4229553'] } })]}
      />,
    )
    expect(screen.getByText(/no bench evidence linked/i)).toBeInTheDocument()
  })

  it('lists decisions that hang off no goal instead of hiding them', () => {
    renderWithProviders(<DecisionTreeView goals={[goal('g')]} entries={[entry('loose')]} />)
    expect(screen.getByText(/not attached to any goal/i)).toBeInTheDocument()
    expect(screen.getByText('loose')).toBeInTheDocument()
  })

  it('says what to do when there is nothing to draw yet', () => {
    renderWithProviders(<DecisionTreeView goals={[]} entries={[]} />)
    expect(screen.getByText(/no goals or decisions to draw yet/i)).toBeInTheDocument()
  })
})
