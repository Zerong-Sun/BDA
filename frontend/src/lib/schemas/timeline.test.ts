import { describe, expect, it } from 'vitest'
import {
  TimelineEntrySchema,
  evidenceLanes,
  groupByPhase,
  isUnbound,
  openQuestions,
  provenanceRefs,
  type TimelineEntry,
} from './timeline'

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

describe('TimelineEntrySchema', () => {
  it('rejects unknown entry types instead of silently weakening the API contract', () => {
    expect(() => entry({ entry_type: 'search_method' as TimelineEntry['entry_type'] })).toThrow()
  })

  it('rejects unknown outcomes instead of rendering an unclassified status', () => {
    expect(() => entry({ outcome: 'probably' as TimelineEntry['outcome'] })).toThrow()
  })
})

describe('the fields a decision tree needs', () => {
  it('defaults the new columns so a response from an older backend still parses', () => {
    // The generated SDK and the running API are deployed separately; a page that throws
    // because a field is absent is a worse failure than one that renders it as unset.
    const parsed = entry()
    expect(parsed.decision_ref).toBeNull()
    expect(parsed.lane).toBe('unspecified')
    expect(parsed.alternatives).toEqual([])
  })

  it('carries the branches that were closed off, with their reasons', () => {
    const parsed = entry({
      alternatives: [{ option: 'keep the empty-MSA contract', rejected_because: 'thaumatin 12.55 A' }],
    })
    expect(parsed.alternatives[0].rejected_because).toBe('thaumatin 12.55 A')
  })
})

describe('isUnbound', () => {
  it('marks a decision that points at nothing resolvable', () => {
    expect(isUnbound(entry({ provenance: {} }))).toBe(true)
    expect(isUnbound(entry({ provenance: { job_ids: ['j1'] } }))).toBe(false)
  })

  it('does not judge a plan, which is written before the evidence exists', () => {
    expect(isUnbound(entry({ entry_type: 'plan', provenance: {} }))).toBe(false)
    expect(isUnbound(entry({ entry_type: 'result', provenance: {} }))).toBe(false)
  })

  it('treats an empty list as no evidence, because it cites nothing', () => {
    expect(isUnbound(entry({ provenance: { job_ids: [] } }))).toBe(true)
  })
})

describe('evidenceLanes', () => {
  it('separates bench identifiers from the rest', () => {
    expect(evidenceLanes(entry({ provenance: { job_ids: ['j'] } }))).toEqual({ dry: true, wet: false })
    expect(evidenceLanes(entry({ provenance: { protein_ids: ['p'] } }))).toEqual({ dry: false, wet: true })
    expect(
      evidenceLanes(entry({ provenance: { job_ids: ['j'], experiment_result_ids: ['e'] } })),
    ).toEqual({ dry: true, wet: true })
  })

  it('reports what the evidence is, not what the lane claims', () => {
    // The disagreement is the point: a wet-lane decision whose only provenance is a
    // scheduler id should be visible as such, not smoothed over.
    const claimed = entry({ lane: 'wet', provenance: { external_refs: ['lsf:4229553'] } })
    expect(evidenceLanes(claimed)).toEqual({ dry: true, wet: false })
  })
})

describe('openQuestions', () => {
  it('returns the unsettled decisions, newest first', () => {
    const rows = [
      entry({ id: 'a', occurred_at: '2026-08-01T00:00:00Z', outcome: 'unspecified' }),
      entry({ id: 'b', occurred_at: '2026-08-05T00:00:00Z', outcome: 'unspecified' }),
      entry({ id: 'c', occurred_at: '2026-08-03T00:00:00Z', outcome: 'refuted' }),
    ]
    expect(openQuestions(rows).map((row) => row.id)).toEqual(['b', 'a'])
  })

  it('drops an open decision that a later one supersedes', () => {
    // Otherwise the "what are we standing on" view keeps offering a branch point that
    // was already walked past.
    const rows = [
      entry({ id: 'old', outcome: 'unspecified' }),
      entry({ id: 'new', outcome: 'unspecified', supersedes_id: 'old', occurred_at: '2026-08-09T00:00:00Z' }),
    ]
    expect(openQuestions(rows).map((row) => row.id)).toEqual(['new'])
  })

  it('ignores plans and results, which are not branch points', () => {
    const rows = [entry({ id: 'p', entry_type: 'plan', outcome: 'unspecified' })]
    expect(openQuestions(rows)).toEqual([])
  })
})
