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
  it('retains a hold in a heading and excludes the historical plan', () => {
    const result = unsectionedReportOverview('# 项目已暂停\n\n用户要求暂停；以下仅为历史材料，不构成执行安排。\n\n# 历史计划\n\n下一阶段：启动计算。')
    expect(result.next).toBe('项目已暂停')
    expect(result.excerpt).toContain('用户要求暂停')
    expect(result.excerpt).not.toContain('启动计算')
  })
  it('retains a plain prose hold over next-stage advice', () => {
    expect(unsectionedReportOverview('当前结果：未完成。\n\n用户要求暂停，等待进一步通知。\n\n下一阶段：启动计算。').next).toBe('用户要求暂停，等待进一步通知。')
  })
  it('preserves preamble results and next steps when references are appended', () => {
    expect(unsectionedReportOverview('当前结果：输入仍缺失。\n\n下一阶段：仅补齐记录。\n\n## References\nSaved source.')).toEqual({
      excerpt: '当前结果：输入仍缺失。\n\n下一阶段：仅补齐记录。', next: '下一阶段：仅补齐记录。',
    })
  })
  it('does not promote instructions or holds from historical or reference subsections', () => {
    const result = unsectionedReportOverview('# 历史计划\n\n## Next steps\n下一步：启动旧任务。\n\n### Status\n项目已暂停。\n\n# 当前进展\n\n当前结果：等待输入。\n\n下一步：补齐输入。\n\n## References\n\n### 引用状态\n暂停旧项目。')
    expect(result).toEqual({ excerpt: '当前结果：等待输入。\n\n下一步：补齐输入。', next: '下一步：补齐输入。' })
  })
  it('does not end a long code fence at a shorter fence inside it', () => {
    expect(unsectionedReportOverview('````md\n```\n# 项目已暂停\n下一步：代码示例。\n````\n\n当前结果：输入缺失。')).toEqual({ excerpt: '当前结果：输入缺失。', next: '' })
  })
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
    expect(unsectionedReportOverview('## Next steps\nNext step: collect inputs.')).toEqual({ excerpt: '', next: '' })
  })
})
