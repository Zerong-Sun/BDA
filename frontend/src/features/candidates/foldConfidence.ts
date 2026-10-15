import { candidateScore, type Candidate } from '../../lib/schemas/candidate'

/** A reversible display cutoff, not a statement about experimental activity. */
export const FOLD_CONFIDENCE_FLOOR = 70
export type FoldConfidenceVerdict = 'passed' | 'screened_out' | 'not_folded' | 'scale_unknown'

/** Existing AlphaFold parser provenance remains sufficient; value size never is. */
export function canonicalFoldConfidence(candidate: Candidate): number | null {
  const value = candidateScore(candidate, 'plddt')
  if (value === null || !Number.isFinite(value) || value < 0 || value > 100) return null
  const declaration = candidate.properties.confidence_scale
  if (declaration !== undefined && (!declaration || typeof declaration !== 'object' || Array.isArray(declaration))) return null
  const metadata = declaration && typeof declaration === 'object'
    ? (declaration as Record<string, unknown>).plddt : undefined
  if (metadata !== undefined && (!metadata || typeof metadata !== 'object' || Array.isArray(metadata))) return null
  if (metadata && typeof metadata === 'object') {
    const context = metadata as Record<string, unknown>
    return context.stored_scale === 'percent_0_100' && (context.scale_status === undefined || context.scale_status === 'known') ? value : null
  }
  const method = candidate.properties.folded_by ?? candidate.properties.predicted_by
  return method === 'alphafold2_superfold' || method === 'alphafold3' ? value : null
}

export function foldConfidenceVerdict(candidate: Candidate, floor = FOLD_CONFIDENCE_FLOOR): FoldConfidenceVerdict {
  const raw = candidateScore(candidate, 'plddt')
  if (raw === null) return 'not_folded'
  const value = canonicalFoldConfidence(candidate)
  if (value === null) return 'scale_unknown'
  return value < floor ? 'screened_out' : 'passed'
}

export function screenByFoldConfidence(candidates: Candidate[], floor = FOLD_CONFIDENCE_FLOOR) {
  const visible: Candidate[] = []
  const screenedOut: Candidate[] = []
  const uncertain: Candidate[] = []
  for (const candidate of candidates) {
    const verdict = foldConfidenceVerdict(candidate, floor)
    if (verdict === 'screened_out') screenedOut.push(candidate)
    else visible.push(candidate)
    if (verdict === 'scale_unknown') uncertain.push(candidate)
  }
  return { visible, screenedOut, uncertain }
}
