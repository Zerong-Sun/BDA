import { describe, expect, it } from 'vitest'
import { TimelineEntrySchema, groupByPhase, provenanceRefs, type TimelineEntry } from './timeline'

function entry(overrides: Partial<TimelineEntry> = {}): TimelineEntry {
  return TimelineEntrySchema.parse({
    id: 'id-1',
    project_id: 'p1',
    occurred_at: '2026-08-03T09:00:00Z',
    entry_type: 'decision',
    phase: 'phase-1',
    title: 'a decision',
    summary: 's',
    body: '',
    outcome: 'supported',
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

describe('provenanceRefs', () => {
  it('flattens every identifier kind into one labelled list', () => {
    const refs = provenanceRefs(
      entry({ provenance: { job_ids: ['j1', 'j2'], external_refs: ['lsf:4103824'] } }),
    )
    expect(refs).toEqual([
      { kind: 'job_ids', value: 'j1' },
      { kind: 'job_ids', value: 'j2' },
      { kind: 'external_refs', value: 'lsf:4103824' },
    ])
  })

  it('ignores non-array values instead of throwing', () => {
    // The column is JSON, so a hand-written row could hold anything; the UI must not
    // crash the whole timeline over one malformed entry.
    expect(provenanceRefs(entry({ provenance: { job_ids: 'oops' } }))).toEqual([])
  })
})

describe('groupByPhase', () => {
  it('keeps chronological order of first appearance rather than sorting names', () => {
    const grouped = groupByPhase([
      entry({ id: 'a', phase: 'phase-1' }),
      entry({ id: 'b', phase: 'platform' }),
      entry({ id: 'c', phase: 'phase-1' }),
      entry({ id: 'd', phase: 'phase-2' }),
    ])
    expect(grouped.map((g) => g.phase)).toEqual(['phase-1', 'platform', 'phase-2'])
    expect(grouped[0].entries.map((e) => e.id)).toEqual(['a', 'c'])
  })

  it('handles entries with no phase', () => {
    const grouped = groupByPhase([entry({ id: 'a', phase: '' })])
    expect(grouped).toHaveLength(1)
    expect(grouped[0].phase).toBe('')
  })
})
