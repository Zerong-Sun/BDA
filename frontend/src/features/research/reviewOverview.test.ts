import { describe, expect, it } from 'vitest'
import { findingReviewCounts, isNewerSavedRecord, reviewOverview, splitObjectiveQuestions, unsectionedReportOverview } from './reviewOverview'

describe('saved report overview', () => {
  it('prioritizes explicit results and never treats arbitrary methods as results', () => {
    const overview = reviewOverview('## Research objective\nScope\n## Methods\nProtocol only\n## Structure analysis\nMechanism\n## Results\nRecorded outcome\n## Open questions\nStill unresolved')
    expect(overview.findings.map(section => section.body)).toEqual(['Recorded outcome'])
    expect(overview.unresolved.map(section => section.body)).toEqual(['Still unresolved'])
    expect(reviewOverview('## Methods\nProtocol').findings).toEqual([])
  })
  it('keeps route structure out of results and gating among advancement conditions', () => {
    const overview = reviewOverview('## Route structure\nWorkflow only\n## Result gating, and one gate deliberately left open\nHold\n## What this project has established about its own limits\nLimits')
    expect(overview.findings).toEqual([])
    expect(overview.unresolved.map(section => section.body)).toEqual(['Hold', 'Limits'])
  })
  it('separates an authored numbered question list without writing an answer', () => {
    expect(splitObjectiveQuestions('Original objective.\n\n1. Which condition?\n2. Which mechanism?')).toEqual({ objective: 'Original objective.', questions: '1. Which condition?\n2. Which mechanism?' })
    expect(splitObjectiveQuestions('Original objective.\n```\n1. code\n```').questions).toBe('')
    expect(splitObjectiveQuestions('1. Collect sequences\n2. Compare models').questions).toBe('')
    expect(splitObjectiveQuestions('Which ligand?', 'Research questions')).toEqual({ objective: '', questions: 'Which ligand?' })
  })
  it('counts only recorded finding review decisions, preserving unknown and pending states', () => {
    expect(findingReviewCounts([
      { id: 'a', evidence: { review_status: 'accepted' } },
      { id: 'a', evidence: { review_status: 'accepted' } },
      { id: 'b', evidence: { review_status: 'pending_review', evidence_level: 'curated_review' } },
      { id: 'c' },
      { id: 'd', evidence: { review_status: 'future_state' } },
    ])).toEqual([['accepted', 1], ['future_state', 1], ['pending_review', 1], ['unrecorded', 1]])
  })
})

it('requires two known dates before considering progress newer than a saved report', () => {
  expect(isNewerSavedRecord('2026-10-16', '2026-09-16')).toBe(true)
  expect(isNewerSavedRecord('2026-09-16', '2026-09-16')).toBe(false)
  expect(isNewerSavedRecord('2026-10-16', undefined)).toBe(false)
  expect(isNewerSavedRecord(undefined, '2026-09-16')).toBe(false)
  expect(isNewerSavedRecord('invalid', '2026-09-16')).toBe(false)
})


describe('unsectioned legacy report excerpts', () => {
  it('keeps the saved status, caveat and required-input list verbatim', () => {
    const result = unsectionedReportOverview('# Saved note\n\n当前结果：原始输入缺失\n\n已完成：仅来源检查，并非实验通过。\n\n待实际输入补齐：\n\n- 实际批次\n- 原始文件\n\nNot part of the next step.')
    expect(result.excerpt).toBe('当前结果：原始输入缺失\n\n已完成：仅来源检查，并非实验通过。')
    expect(result.next).toBe('待实际输入补齐：\n\n- 实际批次\n- 原始文件')
  })
  it('keeps completion labels with their lists and caveats', () => {
    expect(unsectionedReportOverview('当前结果：输入缺失\n\n已完成：\n\n- 来源检查\n\n- 没有新增实测\n\n待输入补齐：\n\n- 实际批次').excerpt).toBe('当前结果：输入缺失\n\n已完成：\n\n- 来源检查\n\n- 没有新增实测')
  })
  it('retains a pause instead of reviving a historical next-stage suggestion', () => {
    const result = unsectionedReportOverview('本轮状态：用户暂停。\n\n按最新指示暂停。\n\n下一阶段取得真实材料。')
    expect(result.next).toBe('本轮状态：用户暂停。')
  })
  it('preserves whole paragraphs containing authored next-stage advice', () => {
    expect(unsectionedReportOverview('本轮完成比较。下一阶段取得真实数据；目前无优势结论。').next).toBe('本轮完成比较。下一阶段取得真实数据；目前无优势结论。')
  })
  it('does not turn code, tables or structured reports into fallback summaries', () => {
    expect(unsectionedReportOverview('```md\n下一阶段执行伪代码。\n```\n\n| table |\n|---|').excerpt).toBe('')
    expect(unsectionedReportOverview('## Methods\nProtocol only.')).toEqual({ excerpt: '', next: '' })
  })
})
