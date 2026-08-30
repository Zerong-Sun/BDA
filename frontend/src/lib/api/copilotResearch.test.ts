import { describe, expect, it } from 'vitest'
import { looksLikeCopilotResearchResult } from './copilotResearch'

describe('Copilot research result detection', () => {
  it('recognizes schema-versioned graph JSON but ignores ordinary Copilot prose', () => {
    expect(looksLikeCopilotResearchResult('```json\n{"schema_version":"1.0","references":[],"nodes":[]}\n```')).toBe(true)
    expect(looksLikeCopilotResearchResult('Here is a narrative research summary with references.')).toBe(false)
  })
})
