import { describe, expect, it } from 'vitest'
import { flattenDraftGoals, removeGoal, renameGoal, type DecisionTreeProposal } from './decisionTree'

/** Branches attach to goals by title, so every goal edit has to carry the branches with
 *  it. Getting this wrong does not throw on this side - it produces a proposal the server
 *  rejects for an unmatched `goal_title`, and the reviewer sees a 422 about a goal they
 *  deliberately removed. */
const PROPOSAL: DecisionTreeProposal = {
  goals: [
    {
      title: 'expressible candidate',
      detail: '',
      children: [{ title: 'disulfide integrity', detail: '', children: [] }],
    },
    { title: 'safety', detail: '', children: [] },
  ],
  branches: [
    { title: 'folds as a monomer?', summary: '', lane: 'dry', goal_title: 'disulfide integrity', alternatives: [] },
    { title: 'activates the receptor?', summary: '', lane: 'wet', goal_title: 'safety', alternatives: [] },
  ],
}

describe('removeGoal', () => {
  it('takes the subtree and every branch that pointed into it', () => {
    const next = removeGoal(PROPOSAL, 'expressible candidate')
    expect(flattenDraftGoals(next.goals).map((n) => n.goal.title)).toEqual(['safety'])
    // The child's branch goes too: its goal no longer exists.
    expect(next.branches.map((b) => b.goal_title)).toEqual(['safety'])
  })

  it('removing a leaf leaves its siblings and their branches alone', () => {
    const next = removeGoal(PROPOSAL, 'disulfide integrity')
    expect(flattenDraftGoals(next.goals).map((n) => n.goal.title)).toEqual([
      'expressible candidate',
      'safety',
    ])
    expect(next.branches.map((b) => b.title)).toEqual(['activates the receptor?'])
  })

  it('leaves the proposal untouched when nothing matches', () => {
    expect(removeGoal(PROPOSAL, 'not a goal')).toEqual(PROPOSAL)
  })
})

describe('renameGoal', () => {
  it('carries every branch that referenced the old title', () => {
    const next = renameGoal(PROPOSAL, 'safety', 'allergenicity')
    expect(flattenDraftGoals(next.goals).map((n) => n.goal.title)).toContain('allergenicity')
    expect(next.branches.find((b) => b.title === 'activates the receptor?')?.goal_title).toBe(
      'allergenicity',
    )
  })

  it('renames a nested goal too', () => {
    const next = renameGoal(PROPOSAL, 'disulfide integrity', 'cysteine pairing')
    expect(next.goals[0].children[0].title).toBe('cysteine pairing')
    expect(next.branches[0].goal_title).toBe('cysteine pairing')
  })
})

describe('flattenDraftGoals', () => {
  it('reads depth-first with the depth each row renders at', () => {
    expect(flattenDraftGoals(PROPOSAL.goals)).toEqual([
      { goal: PROPOSAL.goals[0], depth: 0 },
      { goal: PROPOSAL.goals[0].children[0], depth: 1 },
      { goal: PROPOSAL.goals[1], depth: 0 },
    ])
  })
})

describe('the shortcut that must not exist', () => {
  it('exposes no way to import a stored draft', async () => {
    // Mirrors the server-side tripwire. If an `importDraft(draftId)` ever appears here,
    // the per-item review becomes optional and a model is setting the project's goals.
    const client = await import('./decisionTree')
    const importers = Object.keys(client).filter((name) => name.toLowerCase().includes('import'))
    expect(importers).toEqual(['importDecisionTree'])
  })
})
