import { describe, expect, it } from 'vitest'
import { toCopilotApiMessages } from './copilot'

describe('toCopilotApiMessages', () => {
  it('removes empty assistant placeholders and UI meta', () => {
    expect(
      toCopilotApiMessages([
        { role: 'user', content: '完善项目综述', meta: { reviewIntent: true } },
        { role: 'assistant', content: '' },
        { role: 'assistant', content: '  Draft answer  ' },
      ]),
    ).toEqual([
      { role: 'user', content: '完善项目综述' },
      { role: 'assistant', content: 'Draft answer' },
    ])
  })

  it('drops whitespace-only messages', () => {
    expect(
      toCopilotApiMessages([
        { role: 'system', content: '   ' },
        { role: 'user', content: 'valid prompt' },
      ]),
    ).toEqual([{ role: 'user', content: 'valid prompt' }])
  })

  it('preserves system context messages with trimmed content', () => {
    expect(
      toCopilotApiMessages([
        { role: 'system', content: '  route=/research  ' },
        { role: 'user', content: '完善项目综述' },
      ]),
    ).toEqual([
      { role: 'system', content: 'route=/research' },
      { role: 'user', content: '完善项目综述' },
    ])
  })
})
