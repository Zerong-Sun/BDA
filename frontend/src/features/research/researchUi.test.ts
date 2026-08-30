import { describe, expect, it } from 'vitest'
import {
  buildLiteratureClaimReviewContent,
  buildTargetEvidenceReviewContent,
  localizeToken,
  normalizeResearchTab,
  RESEARCH_TABS,
  shouldAllowLiteratureReview,
  shouldAllowTargetEvidenceReview,
  shouldOfferReviewPromotion,
  shouldTruncateReviewStatement,
} from './researchUi'

describe('researchUi', () => {
  it('opens on the goal tree, then the evidence views, methods, and the timeline', () => {
    // `goals` is first because it holds the questions the other views answer, and
    // `timeline` is last because it records how those views came to say what they say.
    // Neither is the fallback: an old bookmark with no ?tab= still lands on evidence.
    expect(RESEARCH_TABS).toEqual([
      'goals', 'evidence', 'references', 'structures', 'data', 'methods', 'timeline',
    ])
    expect(normalizeResearchTab('unknown')).toBe('evidence')
    expect(normalizeResearchTab('goals')).toBe('goals')
  })

  it('migrates legacy flat and nested tab ids to the v2 workspace views', () => {
    expect(normalizeResearchTab('atlas')).toBe('evidence')
    expect(normalizeResearchTab('review')).toBe('evidence')
    expect(normalizeResearchTab('review-map')).toBe('evidence')
    expect(normalizeResearchTab('target')).toBe('structures')
    expect(normalizeResearchTab('knowledge')).toBe('data')
    expect(normalizeResearchTab('literature')).toBe('references')
    expect(normalizeResearchTab('library')).toBe('data')
    expect(normalizeResearchTab('unknown')).toBe('evidence')
  })

  it('localizes known backend tokens and keeps unknown ones readable', () => {
    expect(localizeToken('evidence_review', { evidence_review: '证据审核' })).toBe('证据审核')
    expect(localizeToken('some_new_stage', {})).toBe('some new stage')
    expect(localizeToken('', {})).toBe('')
    expect(localizeToken(null, {})).toBe('')
  })

  it('opens target evidence review during collecting and evidence review stages', () => {
    expect(shouldAllowTargetEvidenceReview('collecting_evidence')).toBe(true)
    expect(shouldAllowTargetEvidenceReview('evidence_review')).toBe(true)
    expect(shouldAllowTargetEvidenceReview('hotspot_review')).toBe(false)
  })

  it('allows literature review only for admin and researcher roles', () => {
    expect(shouldAllowLiteratureReview('admin')).toBe(true)
    expect(shouldAllowLiteratureReview('researcher')).toBe(true)
    expect(shouldAllowLiteratureReview('viewer')).toBe(false)
    expect(shouldAllowLiteratureReview('')).toBe(false)
  })

  it('offers promotion only for accepted evidence-like items', () => {
    expect(shouldOfferReviewPromotion('accepted')).toBe(true)
    expect(shouldOfferReviewPromotion('confirmed')).toBe(true)
    expect(shouldOfferReviewPromotion('pending_review')).toBe(false)
    expect(shouldOfferReviewPromotion('rejected')).toBe(false)
  })

  it('flags long review statements for truncation', () => {
    expect(shouldTruncateReviewStatement('Short note')).toBe(false)
    expect(shouldTruncateReviewStatement('line\n'.repeat(13))).toBe(true)
    expect(shouldTruncateReviewStatement('a'.repeat(721))).toBe(true)
  })

  it('formats target evidence into review-friendly markdown', () => {
    const content = buildTargetEvidenceReviewContent({
      title: 'PD-1 ectodomain structure',
      claim: 'The ectodomain contains an experimentally resolved binding surface.',
      excerpt: 'Residues in the FG loop participate in ligand recognition.',
      identifier: 'PDB 4ZQK',
      url: 'https://example.org/4zqk',
      evidence_level: 'A',
      source_type: 'pdb',
    })

    expect(content).toContain('## PD-1 ectodomain structure')
    expect(content).toContain('Evidence level: A')
    expect(content).toContain('Source type: pdb')
    expect(content).toContain('PDB 4ZQK')
    expect(content).toContain('https://example.org/4zqk')
  })

  it('formats literature claims into review-friendly markdown', () => {
    const content = buildLiteratureClaimReviewContent({
      claim: 'Blocking PD-1 can rescue T-cell activity in vitro.',
      confidence: 'high',
      review_status: 'accepted',
      document_id: 'doc-123',
    })

    expect(content).toContain('## Literature claim')
    expect(content).toContain('Blocking PD-1 can rescue T-cell activity in vitro.')
    expect(content).toContain('Confidence: high')
    expect(content).toContain('Review status: accepted')
    expect(content).toContain('Document: doc-123')
  })
})
