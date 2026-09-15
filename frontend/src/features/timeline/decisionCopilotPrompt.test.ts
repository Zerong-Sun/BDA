import { describe, expect, it } from 'vitest'
import { buildDecisionCopilotPrompt } from './decisionCopilotPrompt'
import type { TimelineEntry } from '../../lib/schemas/timeline'

const COPY = {
  intro: 'Explain this recorded decision (D8).',
  evidenceRule: 'Use only the record text given below.',
  output: 'Answer four things.',
  evidenceLabel: 'Evidence',
  outcomeHeading: 'Outcome',
  outcomeLabel: 'Refuted',
}

const ENTRY: TimelineEntry = {
  id: 'e1', project_id: 'p1', occurred_at: '2026-08-26T16:00:00Z', entry_type: 'decision',
  decision_ref: 'D8', lane: 'dry', decided_by: 'human', phase: 'phase-2',
  title: 'a recorded call', summary: 'the short form', body: 'the reasoning',
  outcome: 'refuted', provenance: { job_ids: ['j1'], external_refs: ['LSF 1000001'] },
  alternatives: [], code_refs: [], supersedes_id: null, caused_by_id: null, tags: [],
  created_by: null, version: 1, created_at: '2026-08-26T16:00:00Z', updated_at: '2026-08-26T16:00:00Z',
}

describe('the question handed to the Copilot about a decision', () => {
  it('carries the record itself, with its evidence references', () => {
    const prompt = buildDecisionCopilotPrompt(ENTRY, COPY)

    expect(prompt).toContain('D8 · a recorded call')
    expect(prompt).toContain('the short form')
    expect(prompt).toContain('the reasoning')
    expect(prompt).toContain('Outcome: Refuted')
    expect(prompt).toContain('job_ids:j1')
    expect(prompt).toContain('external_refs:LSF 1000001')
    expect(prompt.startsWith('Explain this recorded decision (D8).')).toBe(true)
    expect(prompt.endsWith('Answer four things.')).toBe(true)
  })

  it('drops the sections a sparse record has nothing for, rather than sending empty headings', () => {
    const sparse: TimelineEntry = { ...ENTRY, summary: '', body: '', outcome: 'unspecified', provenance: {} }
    const prompt = buildDecisionCopilotPrompt(sparse, COPY)

    expect(prompt).not.toContain('Outcome:')
    expect(prompt).not.toContain('Evidence:')
    expect(prompt).not.toMatch(/\n\n\n/)
    expect(prompt).toContain('D8 · a recorded call')
  })
})
