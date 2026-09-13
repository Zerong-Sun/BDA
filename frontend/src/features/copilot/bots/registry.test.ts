import { describe, expect, it } from 'vitest'
import {
  byStance,
  matchBot,
  reviewersOf,
  successorsOf,
  type CopilotBot,
  type Stance,
} from './registry'

function bot(
  id: string,
  triggers: string[],
  handoff: string[] = [],
  overrides: Partial<CopilotBot> = {},
): CopilotBot {
  return {
    id,
    title: id,
    title_zh: id,
    phase: 0,
    stance: 'produce',
    summary: `${id} summary`,
    charter: `${id} charter`,
    capabilities: ['project-read'],
    handoff,
    reviews: [],
    directs: [],
    reviewed_by: [],
    triggers,
    ...overrides,
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

  it('lets the more specific phrase win over a shorter token inside it', () => {
    // One phrase matched twice is not two operators named. Before this, both
    // `librarian` and `auditor` became unroutable by the word that names them:
    // "literature review" hit the long phrase and the bare "review" at once.
    const SPECIFICITY: CopilotBot[] = [
      bot('librarian', ['literature review', 'paper']),
      bot('auditor', ['review'], [], { stance: 'review', reviews: ['planner'] }),
    ]

    expect(matchBot('write me a literature review', SPECIFICITY)?.id).toBe('librarian')
    expect(matchBot('please review the plan', SPECIFICITY)?.id).toBe('auditor')
  })

  it('still ties when two equally specific tokens are hit', () => {
    const SPECIFICITY: CopilotBot[] = [
      bot('librarian', ['paper']),
      bot('structuralist', ['residue']),
    ]

    expect(matchBot('a paper about a residue', SPECIFICITY)).toBeUndefined()
  })

  it('does not let a longer unrelated token outrank a shorter one', () => {
    // Containment, not length. A message naming both a route and an interface
    // contact really has named two operators, and ranking "interface contact"
    // above "plan" on size alone would silently drop half the request - the
    // exact failure the tie rule exists to prevent.
    const SPECIFICITY: CopilotBot[] = [
      bot('planner', ['plan', 'route', 'draft']),
      bot('structuralist', ['interface contact']),
    ]

    expect(matchBot('plan a route for the draft interface contact', SPECIFICITY)).toBeUndefined()
  })

  it('resolves a contained token even when the container is matched once', () => {
    // The discard is per matched token, not per bot: `librarian` keeps the
    // phrase, `auditor` loses only the occurrence inside it.
    const SPECIFICITY: CopilotBot[] = [
      bot('librarian', ['literature review']),
      bot('auditor', ['review', 'verdict'], [], { stance: 'review', reviews: ['planner'] }),
    ]

    expect(matchBot('literature review', SPECIFICITY)?.id).toBe('librarian')
    // ...but a second, independent reason to call the auditor restores the tie.
    expect(matchBot('literature review and a verdict', SPECIFICITY)).toBeUndefined()
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

describe('byStance', () => {
  const MIXED: CopilotBot[] = [
    bot('planner', ['route'], [], { reviewed_by: ['auditor'] }),
    bot('auditor', ['review'], [], { stance: 'review', reviews: ['planner'] }),
    bot('conductor', ['delegate'], [], { stance: 'direct', directs: ['planner'] }),
  ]

  it('groups operators by what they are for, coordination first', () => {
    // Not by phase: a director is not the step before the chain and a reviewer
    // is not the step after it, which is exactly what one ordered list says.
    expect(byStance(MIXED).map((group) => group.stance)).toEqual(['direct', 'produce', 'review'])
    expect(byStance(MIXED)[1].bots.map((b) => b.id)).toEqual(['planner'])
  })

  it('omits a stance no operator holds rather than rendering an empty group', () => {
    expect(byStance([MIXED[0]]).map((group) => group.stance)).toEqual(['produce'])
  })

  it('returns nothing for an empty roster', () => {
    expect(byStance([])).toEqual([])
  })

  it('drops an operator whose stance the client does not know', () => {
    // A roster served by a newer backend must not crash an older client, and a
    // stance this build cannot label has no group to render into.
    const future = bot('future', [], [], { stance: 'arbitrate' as unknown as Stance })
    expect(byStance([...MIXED, future]).flatMap((group) => group.bots.map((b) => b.id)))
      .not.toContain('future')
  })
})

describe('reviewersOf', () => {
  const ROSTER_WITH_REVIEW: CopilotBot[] = [
    bot('planner', [], [], { reviewed_by: ['auditor', 'steward'] }),
    bot('auditor', [], [], { stance: 'review', reviews: ['planner'] }),
  ]

  it('resolves who checks an operator against the roster', () => {
    expect(reviewersOf(ROSTER_WITH_REVIEW[0], ROSTER_WITH_REVIEW).map((b) => b.id)).toEqual([
      'auditor',
    ])
  })

  it('is empty for an operator nobody reviews', () => {
    expect(reviewersOf(ROSTER_WITH_REVIEW[1], ROSTER_WITH_REVIEW)).toEqual([])
  })
})
