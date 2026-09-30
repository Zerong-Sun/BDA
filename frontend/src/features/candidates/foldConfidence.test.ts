import { describe, expect, it } from 'vitest'
import type { Candidate } from '../../lib/schemas/candidate'
import { canonicalFoldConfidence, foldConfidenceVerdict, screenByFoldConfidence } from './foldConfidence'
const candidate = (plddt: unknown, properties: Record<string, unknown> = {}): Candidate => ({
  id: 'test', project_id: 'project', candidate_key: 'test', name: 'Synthetic candidate', status: 'scored',
  rank: null, score: null, scores: { plddt }, properties, structure_artifact_id: null,
  complex_artifact_id: null, source_job_id: null, version: 1, created_at: '', updated_at: '',
})
describe('explicit confidence scales', () => {
  it('does not infer scales from either large or fractional values', () => {
    for (const value of [0, 0.8, 85, 101]) expect(foldConfidenceVerdict(candidate(value))).toBe('scale_unknown')
  })
  it('preserves existing AlphaFold source contracts including legitimately low scores', () => {
    expect(foldConfidenceVerdict(candidate(0.8, { folded_by: 'alphafold2_superfold' }))).toBe('screened_out')
    expect(foldConfidenceVerdict(candidate(85, { predicted_by: 'alphafold3' }))).toBe('passed')
  })
  it('only hides confirmed low scores and preserves uncertain or missing results', () => {
    const low = candidate(50, { confidence_scale: { plddt: { stored_scale: 'percent_0_100' } } })
    const uncertain = candidate(0.9)
    const missing = candidate(null)
    const result = screenByFoldConfidence([low, uncertain, missing])
    expect(result.screenedOut).toEqual([low])
    expect(result.visible).toEqual([uncertain, missing])
    expect(result.uncertain).toEqual([uncertain])
  })
  it('does not let provider fallback override an explicit conflict or unknown scale', () => {
    for (const metadata of [{ stored_scale: 'unknown' }, { stored_scale: 'percent_0_100', scale_status: 'scale_conflict' }]) {
      expect(canonicalFoldConfidence(candidate(90, { folded_by: 'alphafold3', confidence_scale: { plddt: metadata } }))).toBeNull()
    }
  })
  it('does not convert raw Boltz history or accept non-finite/out-of-range declared values', () => {
    expect(foldConfidenceVerdict(candidate(0.9, { predicted_by: 'boltz2' }))).toBe('scale_unknown')
    for (const value of [NaN, Infinity, -1, 101]) expect(foldConfidenceVerdict(candidate(value, { folded_by: 'alphafold3' }))).toBe('scale_unknown')
  })
  it('does not wash malformed explicit declarations through a provider fallback', () => {
    for (const declaration of ['bad', [], null, { plddt: 'bad' }, { plddt: { stored_scale: 'percent_0_100', scale_status: 'unknown' } }]) {
      expect(canonicalFoldConfidence(candidate(90, { folded_by: 'alphafold3', confidence_scale: declaration }))).toBeNull()
    }
  })

})
