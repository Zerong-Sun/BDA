import { describe, expect, it } from 'vitest'
import { detectReviewIntent, isResearchPageContext } from './reviewIntent'
import { parseReviewFinding } from './parseReviewFinding'
import { inferTrackFromText, isReviewTrack, REVIEW_SECTION_ORDER } from './reviewTracks'

describe('reviewIntent', () => {
  it('detects Chinese review completion prompts', () => {
    expect(detectReviewIntent('请完善项目的结合策略章节')).toBe(true)
    expect(detectReviewIntent('补充研究综述中的风险段落')).toBe(true)
    expect(detectReviewIntent('解释候选物评分')).toBe(false)
  })

  it('detects English review completion prompts', () => {
    expect(detectReviewIntent('Complete the research review for binding strategy')).toBe(true)
    expect(detectReviewIntent('Summarize the top candidate')).toBe(false)
  })

  it('recognizes research page context markers', () => {
    expect(isResearchPageContext('route=/research; research_tab=evidence')).toBe(true)
    expect(isResearchPageContext('route=/workflow; project_id=proj_test')).toBe(false)
    expect(isResearchPageContext(undefined)).toBe(false)
  })
})

describe('parseReviewFinding', () => {
  it('extracts title, sources, and uncertainty', () => {
    const payload = parseReviewFinding(
      [
        'Cutinase binds fungal cell walls',
        '',
        'Source: https://example.org/paper',
        'DOI 10.1234/example',
        '',
        '待验证：是否需要全长酶。',
      ].join('\n'),
      'binding_strategy',
    )

    expect(payload.finding_type).toBe('binding_strategy')
    expect(payload.title).toContain('Cutinase')
    expect(payload.evidence?.evidence_level).toBe('copilot_synthesis')
    expect(payload.evidence?.source_refs).toEqual(expect.arrayContaining(['https://example.org/paper', '10.1234/example']))
    expect(payload.evidence?.uncertainty).toContain('是否需要全长酶')
  })

  it('uses markdown headings as titles and keeps the body as statement', () => {
    const payload = parseReviewFinding('## Binding hotspot summary\n\nHotspot cluster at interface A.', 'binding_strategy')
    expect(payload.title).toBe('Binding hotspot summary')
    expect(payload.content).toContain('Hotspot cluster at interface A.')
  })

  it('falls back when content is only a short title line', () => {
    const payload = parseReviewFinding('Binding hotspot summary', 'binding_strategy')
    expect(payload.title).toBe('Binding hotspot summary')
    expect(payload.content).toBe('Binding hotspot summary')
  })
})

describe('reviewTracks', () => {
  it('infers track from section label text', () => {
    expect(inferTrackFromText('请完善结合方式与识别策略', 'zh')).toBe('binding_strategy')
    expect(inferTrackFromText('Expand the functional validation plan', 'en')).toBe('functional_validation')
  })

  it('validates known review tracks', () => {
    for (const track of REVIEW_SECTION_ORDER) {
      expect(isReviewTrack(track)).toBe(true)
    }
    expect(isReviewTrack('unknown_track')).toBe(false)
  })
})
