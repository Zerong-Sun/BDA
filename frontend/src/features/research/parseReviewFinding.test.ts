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
})
