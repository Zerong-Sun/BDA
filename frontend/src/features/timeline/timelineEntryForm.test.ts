import { describe, expect, it } from 'vitest'
import {
  draftFromEntry,
  draftToBody,
  emptyDraft,
  validateDraft,
  type TimelineEntryDraft,
} from './timelineEntryForm'
import type { TimelineEntry } from '../../lib/schemas/timeline'

function entry(overrides: Partial<TimelineEntry> = {}): TimelineEntry {
  return {
    id: 'e1',
    project_id: 'p1',
    occurred_at: '2026-08-25T11:00:00Z',
    entry_type: 'decision',
    decision_ref: 'D7',
    lane: 'dry',
    phase: 'phase-2',
    title: 'a gate decision',
    summary: 'the middle setting passed',
    body: '**Judgement**: ...',
    outcome: 'supported',
    provenance: { external_refs: ['lsf:1', 'lsf:2'] },
    alternatives: [{ option: 'the low setting', rejected_because: 'did not move enough to count' }],
    code_refs: [{ path: 'scripts/measure.py', role: 'gate readout' }],
    supersedes_id: null,
    caused_by_id: null,
    tags: ['route', 'screening'],
    created_by: null,
    version: 3,
    created_at: '2026-08-25T11:00:00Z',
    updated_at: '2026-08-25T11:00:00Z',
    ...overrides,
  }
}

function draft(overrides: Partial<TimelineEntryDraft> = {}): TimelineEntryDraft {
  return { ...emptyDraft(new Date('2026-09-05T10:30:00Z')), title: 'a decision', ...overrides }
}

describe('emptyDraft', () => {
  it('defaults occurred_at to the given moment at minute precision, in UTC', () => {
    expect(emptyDraft(new Date('2026-09-05T10:30:45Z')).occurred_at).toBe('2026-09-05T10:30')
  })

  it('offers every allowed provenance key and no others', () => {
    expect(Object.keys(emptyDraft().provenance).sort()).toEqual([
      'artifact_ids',
      'candidate_ids',
      'experiment_result_ids',
      'external_refs',
      'finding_ids',
      'job_ids',
      'protein_ids',
      'workflow_run_ids',
    ])
  })
})

describe('draftFromEntry / draftToBody round trip', () => {
  it('returns the entry unchanged through the form', () => {
    const body = draftToBody(draftFromEntry(entry()))
    expect(body).toEqual({
      occurred_at: '2026-08-25T11:00:00Z',
      entry_type: 'decision',
      decision_ref: 'D7',
      lane: 'dry',
      phase: 'phase-2',
      title: 'a gate decision',
      summary: 'the middle setting passed',
      body: '**Judgement**: ...',
      outcome: 'supported',
      provenance: { external_refs: ['lsf:1', 'lsf:2'] },
      alternatives: [{ option: 'the low setting', rejected_because: 'did not move enough to count' }],
      code_refs: [{ path: 'scripts/measure.py', role: 'gate readout' }],
      tags: ['route', 'screening'],
    })
  })

  it('drops a provenance key the backend does not allow rather than round-tripping it', () => {
    const loaded = draftFromEntry(entry({ provenance: { job_ids: ['j1'], made_up_ids: ['x'] } }))
    expect(draftToBody(loaded).provenance).toEqual({ job_ids: ['j1'] })
  })

  it('reads ids one per line and writes them back as a list', () => {
    const loaded = draftFromEntry(entry({ provenance: { job_ids: ['a', 'b'] } }))
    expect(loaded.provenance.job_ids).toBe('a\nb')
    expect(draftToBody(loaded).provenance.job_ids).toEqual(['a', 'b'])
  })

  it('accepts comma separated ids too, and drops blanks', () => {
    const body = draftToBody(draft({ provenance: { ...emptyDraft().provenance, job_ids: 'a, ,b\n\nc' } }))
    expect(body.provenance.job_ids).toEqual(['a', 'b', 'c'])
  })

  it('omits a provenance key with nothing in it instead of storing an empty list', () => {
    expect(draftToBody(draft()).provenance).toEqual({})
  })
})

describe('validateDraft', () => {
  it('accepts a minimal entry', () => {
    expect(validateDraft(draft())).toEqual([])
  })

  it('requires a title', () => {
    expect(validateDraft(draft({ title: '   ' }))).toEqual([{ field: 'title', code: 'required' }])
  })

  it('rejects a title past the column width', () => {
    expect(validateDraft(draft({ title: 'x'.repeat(301) }))).toEqual([
      { field: 'title', code: 'too_long', limit: 300 },
    ])
  })

  it('rejects an unparseable timestamp', () => {
    expect(validateDraft(draft({ occurred_at: 'not-a-date' }))).toContainEqual({
      field: 'occurred_at',
      code: 'bad_timestamp',
    })
  })

  it('rejects a timestamp V8 would leniently mis-parse rather than reject', () => {
    // Date.parse('not-a-date:00Z') returns 2000-01-01, not NaN. Shape is checked first.
    expect(validateDraft(draft({ occurred_at: 'not-a-date' })).length).toBe(1)
  })

  it('rejects a day that does not exist instead of rolling it over', () => {
    expect(validateDraft(draft({ occurred_at: '2026-02-31T10:00' }))).toContainEqual({
      field: 'occurred_at',
      code: 'bad_timestamp',
    })
  })

  it('rejects an empty timestamp', () => {
    expect(validateDraft(draft({ occurred_at: '' }))).toContainEqual({
      field: 'occurred_at',
      code: 'bad_timestamp',
    })
  })

  describe('the lane rule, mirroring check_lane_evidence', () => {
    const settledWet = {
      entry_type: 'decision' as const,
      lane: 'wet' as const,
      outcome: 'supported' as const,
    }

    it('refuses a settled wet decision that cites no bench evidence', () => {
      expect(validateDraft(draft(settledWet))).toContainEqual({
        field: 'provenance',
        code: 'lane_evidence_missing',
      })
    })

    it('is satisfied by an experiment result', () => {
      const provenance = { ...emptyDraft().provenance, experiment_result_ids: 'r1' }
      expect(validateDraft(draft({ ...settledWet, provenance }))).toEqual([])
    })

    it('is satisfied by a construct', () => {
      const provenance = { ...emptyDraft().provenance, protein_ids: 'p1' }
      expect(validateDraft(draft({ ...settledWet, provenance }))).toEqual([])
    })

    it('is not satisfied by dry evidence alone', () => {
      const provenance = { ...emptyDraft().provenance, job_ids: 'j1' }
      expect(validateDraft(draft({ ...settledWet, provenance }))).toContainEqual({
        field: 'provenance',
        code: 'lane_evidence_missing',
      })
    })

    it('applies to the both lane as well', () => {
      expect(validateDraft(draft({ ...settledWet, lane: 'both' }))).toContainEqual({
        field: 'provenance',
        code: 'lane_evidence_missing',
      })
    })

    it('leaves an OPEN wet decision alone - writing the question down must stay possible', () => {
      expect(validateDraft(draft({ ...settledWet, outcome: 'unspecified' }))).toEqual([])
    })

    it('does not apply to a plan, which is written before the evidence exists', () => {
      expect(validateDraft(draft({ ...settledWet, entry_type: 'plan' }))).toEqual([])
    })
  })

  describe('alternatives', () => {
    it('drops a wholly blank row rather than blocking the save', () => {
      const value = draft({ alternatives: [{ option: '', rejected_because: '' }] })
      expect(validateDraft(value)).toEqual([])
      expect(draftToBody(value).alternatives).toEqual([])
    })

    it('refuses an option with no reason', () => {
      expect(validateDraft(draft({ alternatives: [{ option: 'an option', rejected_because: '  ' }] }))).toEqual([
        { field: 'alternatives.0.rejected_because', code: 'alternative_incomplete' },
      ])
    })

    it('refuses a reason with no option', () => {
      expect(validateDraft(draft({ alternatives: [{ option: '', rejected_because: 'too slow' }] }))).toEqual([
        { field: 'alternatives.0.option', code: 'alternative_incomplete' },
      ])
    })

    it('reports the index so the right row can be marked', () => {
      const value = draft({
        alternatives: [
          { option: 'a', rejected_because: 'b' },
          { option: 'c', rejected_because: '' },
        ],
      })
      expect(validateDraft(value)).toEqual([
        { field: 'alternatives.1.rejected_because', code: 'alternative_incomplete' },
      ])
    })

    it('caps the reason at the backend length', () => {
      const value = draft({ alternatives: [{ option: 'a', rejected_because: 'x'.repeat(2001) }] })
      expect(validateDraft(value)).toEqual([
        { field: 'alternatives.0.rejected_because', code: 'too_long', limit: 2000 },
      ])
    })
  })

  describe('code refs', () => {
    it('drops a wholly blank row', () => {
      const value = draft({ code_refs: [{ path: '', role: '' }] })
      expect(validateDraft(value)).toEqual([])
      expect(draftToBody(value).code_refs).toEqual([])
    })

    it('requires a path when a role was given', () => {
      expect(validateDraft(draft({ code_refs: [{ path: '', role: 'gate' }] }))).toEqual([
        { field: 'code_refs.0.path', code: 'required' },
      ])
    })
  })
})

describe('draftToBody', () => {
  it('turns a blank decision number into null, not an empty string', () => {
    // Two entries holding "" would collide on the unique constraint; NULL is the real
    // "this entry has no number".
    expect(draftToBody(draft({ decision_ref: '   ' })).decision_ref).toBeNull()
  })

  it('trims a decision number', () => {
    expect(draftToBody(draft({ decision_ref: ' D9 ' })).decision_ref).toBe('D9')
  })

  it('splits tags on commas and whitespace', () => {
    expect(draftToBody(draft({ tags: 'route, screening  headline' })).tags).toEqual([
      'route',
      'screening',
      'headline',
    ])
  })

  it('keeps the body verbatim - markdown indentation is content', () => {
    expect(draftToBody(draft({ body: '  indented\n\n  block  ' })).body).toBe('  indented\n\n  block  ')
  })

  it('sends the timestamp as UTC, matching how the rest of the app reads it', () => {
    expect(draftToBody(draft({ occurred_at: '2026-08-26T16:00' })).occurred_at).toBe(
      '2026-08-26T16:00:00Z',
    )
  })
})
