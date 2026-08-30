import { describe, expect, it } from 'vitest'
import { CandidateListSchema, CandidateSchema } from './candidate'

const validCandidate = {
  id: 'PD1Binder_c4361', project_id: 'proj_pd1_0423', candidate_key: 'PD1Binder_c4361',
  name: 'scaffold_a', status: 'validated', rank: 1, score: 0.91,
  scores: { interface_score: 0.91, pred_kd: '0.6 nM', plddt: 88.2 },
  properties: { decision: 'Anchor' }, structure_artifact_id: null, complex_artifact_id: null,
  source_job_id: null, version: 1, created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
}

describe('CandidateSchema', () => {
  it('accepts a native v2 candidate payload', () => {
    expect(CandidateSchema.parse(validCandidate).id).toBe('PD1Binder_c4361')
  })

  it('rejects invalid typed resource fields', () => {
    expect(() => CandidateSchema.parse({ ...validCandidate, rank: 'bad' })).toThrow()
  })

  it('accepts generated backbones before scoring metrics exist', () => {
    const parsed = CandidateSchema.parse({ ...validCandidate, score: null, scores: {}, status: 'generated_backbone' })
    expect(parsed.score).toBeNull()
    expect(parsed.scores).toEqual({})
  })
})

describe('CandidateListSchema', () => {
  it('accepts native cursor pages', () => {
    const parsed = CandidateListSchema.parse({ items: [validCandidate], next_cursor: null })
    expect(parsed.items).toHaveLength(1)
    expect(parsed.next_cursor).toBeNull()
  })
})
