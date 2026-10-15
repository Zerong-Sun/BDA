import { describe, expect, it } from 'vitest'
import { firstSentenceForTitle, parseReviewFinding } from './parseReviewFinding'

describe('parseReviewFinding', () => {
  it('keeps full first line as title without 80-char truncation', () => {
    const title = 'Expression system to build small de novo binders'
    const content = `${title}\n\nFor hydrophobic-pocket mini-binders, screen soluble expression hosts.`
    const payload = parseReviewFinding(content, 'purification_plan')
    expect(payload.title).toBe(title)
    expect(payload.content).toContain('hydrophobic-pocket')
  })

  it('does not split E. coli titles at the abbreviation period', () => {
    const sentence =
      'For small de novo binders, screen E. coli soluble expression with removable tags, SEC, LC-MS, and aggregation checks.'
    expect(firstSentenceForTitle(sentence)).toBe(sentence)
  })

  it('preserves a cited opening sentence in the saved prose', () => {
    const content = 'Measured binding increased.[cite:1]\n\nAn untested hypothesis follows.'
    expect(parseReviewFinding(content, 'binding_strategy').content).toBe(content)
    const legacy = 'Measured binding increased.[PMID:12345678]\n\nContext.'
    expect(parseReviewFinding(legacy, 'binding_strategy').content).toBe(legacy)
  })

  it('preserves an uncited measurement in the opening sentence', () => {
    const content = 'Expression yield was 2 mg/L.\n\nVerify aggregation before the next round.'
    expect(parseReviewFinding(content, 'purification_plan').content).toBe(content)
  })

  it('removes only an explicit uncited heading that is already stored as the title', () => {
    const payload = parseReviewFinding('## Expression results\n\nMeasured yield was 2 mg/L.', 'purification_plan')
    expect(payload.title).toBe('Expression results')
    expect(payload.content).toBe('Measured yield was 2 mg/L.')
  })
})
