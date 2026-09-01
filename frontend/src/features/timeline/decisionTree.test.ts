import { describe, expect, it } from 'vitest'
import { TimelineEntrySchema, type TimelineEntry } from '../../lib/schemas/timeline'
import type { ResearchGoal } from '../../lib/api/researchGoals'
import { buildDecisionTree, flattenGoalNodes, subtreeDecisionCount } from './decisionTree'

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

function goal(id: string, parent: string | null, links: Array<[string, string]> = []): ResearchGoal {
  return {
    id,
    project_id: 'p1',
    parent_id: parent,
    title: id,
    detail: '',
    status: 'open',
    sort_order: 0,
    tags: [],
    version: 1,
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
    links: links.map(([type, resourceId], index) => ({
      id: `${id}-link-${index}`,
      goal_id: id,
      resource_type: type,
      resource_id: resourceId,
      note: '',
    })),
  } as ResearchGoal
}

describe('buildDecisionTree', () => {
  it('hangs a decision off every goal it constrains', () => {
    // The reason the timeline has no parent_id. D109 used dry re-analysis to revoke a
    // wet expression authorisation, so it constrains both goals at once; a single parent
    // pointer would push one of the two relationships back into prose.
    const d109 = entry('d109')
    const tree = buildDecisionTree(
      [goal('expressible', null, [['timeline_entry', 'd109']]), goal('safety', null, [['timeline_entry', 'd109']])],
      [d109],
    )
    expect(tree.roots.map((node) => node.goal.id)).toEqual(['expressible', 'safety'])
    expect(tree.roots[0].decisions[0].entry.id).toBe('d109')
    expect(tree.roots[1].decisions[0].entry.id).toBe('d109')
    expect(tree.unattached).toEqual([])
  })

  it('nests goals and counts the decisions in a whole subtree', () => {
    const tree = buildDecisionTree(
      [
        goal('root', null),
        goal('child', 'root', [['timeline_entry', 'a']]),
        goal('grandchild', 'child', [['timeline_entry', 'b']]),
      ],
      [entry('a'), entry('b')],
    )
    expect(subtreeDecisionCount(tree.roots[0])).toBe(2)
    expect(flattenGoalNodes(tree.roots).map((node) => node.goal.id)).toEqual(['root', 'child', 'grandchild'])
    expect(flattenGoalNodes(tree.roots).map((node) => node.depth)).toEqual([0, 1, 2])
  })

  it('folds a superseded decision into its replacement instead of listing both', () => {
    const older = entry('d108', { occurred_at: '2026-08-01T00:00:00Z' })
    const newer = entry('d109', { occurred_at: '2026-08-09T00:00:00Z', supersedes_id: 'd108' })
    const tree = buildDecisionTree(
      [goal('g', null, [['timeline_entry', 'd108'], ['timeline_entry', 'd109']])],
      [older, newer],
    )
    expect(tree.roots[0].decisions.map((node) => node.entry.id)).toEqual(['d109'])
    // Overturned reasoning stays reachable - deleting it is how a project forgets its
    // own mistakes - but it does not sit beside the decision that replaced it.
    expect(tree.roots[0].decisions[0].superseded.map((row) => row.id)).toEqual(['d108'])
  })

  it('surfaces decisions that hang off no goal rather than dropping them', () => {
    const tree = buildDecisionTree([goal('g', null)], [entry('loose')])
    expect(tree.roots[0].decisions).toEqual([])
    expect(tree.unattached.map((node) => node.entry.id)).toEqual(['loose'])
  })

  it('counts only decisions as unattached; a result is not a branch point', () => {
    const tree = buildDecisionTree([], [entry('r', { entry_type: 'result' }), entry('d')])
    expect(tree.unattached.map((node) => node.entry.id)).toEqual(['d'])
  })

  it('ignores links to other resource kinds and to entries that are gone', () => {
    const tree = buildDecisionTree(
      [goal('g', null, [['candidate', 'c1'], ['timeline_entry', 'deleted']])],
      [entry('present')],
    )
    // A dangling link reads as a missing reference, not an error: that is the trade the
    // link table was designed around.
    expect(tree.roots[0].decisions).toEqual([])
    expect(tree.unattached.map((node) => node.entry.id)).toEqual(['present'])
  })

  it('shows a goal whose parent is missing at the root instead of dropping it', () => {
    const tree = buildDecisionTree([goal('orphan', 'not-in-this-response')], [])
    expect(tree.roots.map((node) => node.goal.id)).toEqual(['orphan'])
  })

  it('orders a goal-s decisions by when they happened', () => {
    const tree = buildDecisionTree(
      [goal('g', null, [['timeline_entry', 'late'], ['timeline_entry', 'early']])],
      [
        entry('late', { occurred_at: '2026-08-20T00:00:00Z' }),
        entry('early', { occurred_at: '2026-08-02T00:00:00Z' }),
      ],
    )
    expect(tree.roots[0].decisions.map((node) => node.entry.id)).toEqual(['early', 'late'])
  })
})
