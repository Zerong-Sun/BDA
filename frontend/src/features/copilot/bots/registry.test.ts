import { describe, expect, it } from 'vitest'
import { matchBot, successorsOf, type CopilotBot } from './registry'

function bot(id: string, triggers: string[], handoff: string[] = []): CopilotBot {
  return {
    id,
    title: id,
    title_zh: id,
    phase: 0,
    summary: `${id} summary`,
    charter: `${id} charter`,
    capabilities: ['project-read'],
    handoff,
    triggers,
  }
}

const ROSTER: CopilotBot[] = [
  bot('structuralist', ['structure', 'residue', '残基'], ['planner']),
  bot('librarian', ['paper', 'literature', '文献'], ['scout']),
  bot('medic', ['failed', 'diagnose'], ['planner']),
]

describe('matchBot', () => {
  it('picks the one bot a message names', () => {
    expect(matchBot('Which residues line the interface?', ROSTER)?.id).toBe('structuralist')
    expect(matchBot('整理一下这些文献', ROSTER)?.id).toBe('librarian')
  })

  it('matches case-insensitively', () => {
    expect(matchBot('Show me the STRUCTURE', ROSTER)?.id).toBe('structuralist')
  })

  it('returns nothing when two bots are named', () => {
    // A tie is not a narrower turn; it is an unanswered question about which
    // half of the request comes first. Choosing one would drop the other.
    expect(matchBot('Find a paper about this residue', ROSTER)).toBeUndefined()
  })

  it('returns nothing when no bot is named', () => {
    expect(matchBot('hello', ROSTER)).toBeUndefined()
  })

  it('returns nothing against an empty roster rather than throwing', () => {
    // The roster is fetched. Before it arrives, and if the request fails, the
    // chat must still send - unhinted, which is the safe direction.
    expect(matchBot('Which residues line the interface?', [])).toBeUndefined()
  })

  it('tolerates a roster entry with no triggers', () => {
    expect(matchBot('anything', [bot('quiet', [])])).toBeUndefined()
  })
})

describe('successorsOf', () => {
  it('resolves handoffs against the roster', () => {
    const medic = ROSTER[2]
    expect(successorsOf({ ...medic, handoff: ['librarian', 'structuralist'] }, ROSTER).map((b) => b.id))
      .toEqual(['librarian', 'structuralist'])
  })

  it('drops a handoff the roster does not contain instead of rendering a dead option', () => {
    expect(successorsOf({ ...ROSTER[0], handoff: ['ghost'] }, ROSTER)).toEqual([])
  })
})
