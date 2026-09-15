import { describe, expect, it } from 'vitest'
import type { CopilotBot } from './bots/registry'
import { ownedService, parseMention } from './mentions'

/**
 * Addressing is routing, so every case here is one where getting it wrong sends
 * a message somewhere the person did not intend and says nothing about it.
 */

const bot = (overrides: Partial<CopilotBot> & Pick<CopilotBot, 'id' | 'title' | 'title_zh'>): CopilotBot => ({
  phase: 1, stance: 'produce', summary: '', charter: '', capabilities: [], handoff: [],
  reviews: [], directs: [], reviewed_by: [], triggers: [], task_services: [], task_write_tools: {},
  absorbs: [], ...overrides,
}) as CopilotBot

const ROSTER: CopilotBot[] = [
  bot({ id: 'planner', title: 'Planner', title_zh: '方案设计', task_services: ['planning'], absorbs: ['structuralist'] }),
  bot({ id: 'runner', title: 'Runner', title_zh: '执行与排障', task_services: ['execution'] }),
  bot({ id: 'auditor', title: 'Auditor', title_zh: '复核', stance: 'review' }),
]

describe('parseMention', () => {
  it('returns nothing when the message addresses nobody', () => {
    expect(parseMention('which route fits this target?', ROSTER)).toBeNull()
  })

  it('resolves an id, a title and a Chinese name alike', () => {
    expect(parseMention('@planner draft it', ROSTER)?.bot?.id).toBe('planner')
    expect(parseMention('@Runner start it', ROSTER)?.bot?.id).toBe('runner')
    expect(parseMention('@方案设计 帮我起草', ROSTER)?.bot?.id).toBe('planner')
  })

  it('reads a Chinese name written without a space after it', () => {
    const mention = parseMention('@方案设计帮我起草路线', ROSTER)
    expect(mention?.bot?.id).toBe('planner')
    expect(mention?.body).toBe('帮我起草路线')
  })

  it('sends a retired name to the operator that absorbed it', () => {
    expect(parseMention('@structuralist check the interface', ROSTER)?.bot?.id).toBe('planner')
  })

  it('reports a handle that names nobody instead of guessing an operator', () => {
    const mention = parseMention('@nobody do the thing', ROSTER)
    expect(mention).not.toBeNull()
    expect(mention?.bot).toBeUndefined()
    expect(mention?.handle).toBe('nobody')
  })

  it('ignores an operator named mid-sentence, which is a reference and not an address', () => {
    expect(parseMention('ask @planner about it later', ROSTER)).toBeNull()
  })

  it('keeps the work and drops the address', () => {
    expect(parseMention('@runner 把这个作业跟到底', ROSTER)?.body).toBe('把这个作业跟到底')
  })

  it('tolerates punctuation after the handle', () => {
    expect(parseMention('@planner: draft it', ROSTER)?.bot?.id).toBe('planner')
    expect(parseMention('@方案设计，起草', ROSTER)?.bot?.id).toBe('planner')
  })
})

describe('ownedService', () => {
  it('names the recipe an operator owns, and nothing for one that owns none', () => {
    expect(ownedService(ROSTER[0])).toBe('planning')
    expect(ownedService(ROSTER[2])).toBeUndefined()
    expect(ownedService(undefined)).toBeUndefined()
  })
})
