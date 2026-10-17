import { describe, expect, it } from 'vitest'
import { answerPresentation } from './answerPresentation'

describe('latest answer presentation', () => {
  it('folds a saved process section while preserving negative results and next steps', () => {
    const answer = answerPresentation('**本次所做工作（只读）**\n\n`get_workflow_status(limit=50)` → []；`get_compute_status` → jobs=[]。\n\n真实状态分类\n\n真正完成：无。当前无记录不等于历史作业成功。\n\n下一步建议（未执行）\n\n取原始回执，缺失则保持历史状态未知。[cite:8]')
    expect(answer.visible).toContain('真正完成：无。当前无记录不等于历史作业成功。')
    expect(answer.visible).toContain('缺失则保持历史状态未知。[cite:8]')
    expect(answer.visible).not.toContain('get_workflow_status')
    expect(answer.folded).toContain('get_compute_status')
  })
  it('moves conclusions before next steps and keeps unknown scientific paragraphs', () => {
    const answer = answerPresentation('## Next steps\nRead the raw data.\n\n## Conclusion\nBinding remains unverified.[4]\n\n## Caveat\nAn empty table is not proof of absence.')
    expect(answer.visible.indexOf('Binding remains')).toBeLessThan(answer.visible.indexOf('Read the raw data'))
    expect(answer.visible).toContain('An empty table is not proof of absence.')
    expect(answer.folded).toBe('')
  })
  it('folds raw calls and code fences without treating code headings as conclusions', () => {
    const answer = answerPresentation('get_compute_status 返回 []。\n\n```json\n\n## Conclusion\n{"jobs": []}\n```\n\n结论：未获得可验证结果。')
    expect(answer.visible).toBe('结论：未获得可验证结果。')
    expect(answer.folded).toContain('## Conclusion\n{"jobs": []}')
  })
  it('does not invent conclusions for a log-only reply or lose a one-line reply', () => {
    expect(answerPresentation('**本次所做工作**\n\nget_workflow_status → []').visible).toBe('')
    expect(answerPresentation('No validated result yet.').visible).toBe('No validated result yet.')
  })
  it('recognizes inline bold labels without dropping their authored conclusions', () => {
    const answer = answerPresentation('**本次所做工作**（只读）：调用 get_compute_status。\n\n**结论先行**：尚无可验证结果。\n\n**下一步建议**：核对原始文件。')
    expect(answer.folded).toContain('get_compute_status')
    expect(answer.visible).toContain('**结论先行**：尚无可验证结果。')
    expect(answer.visible).toContain('**下一步建议**：核对原始文件。')
  })
  it('separates a raw empty-table sentence from its scientific interpretation', () => {
    const answer = answerPresentation('**作业真实状态**\n\n`get_compute_status` 当前返回 `jobs: []`。没有可验证的运行；空队列不能证明历史成功。')
    expect(answer.visible).toContain('没有可验证的运行；空队列不能证明历史成功。')
    expect(answer.visible).not.toContain('get_compute_status')
    expect(answer.folded).toContain('`jobs: []`')
  })
  it('keeps an unheaded delivery summary ahead of a structured next action', () => {
    const answer = answerPresentation('Saved summary: QC remains pending.\n\n## Next step\nCheck the sequence mapping.')
    expect(answer.visible.indexOf('QC remains pending')).toBeLessThan(answer.visible.indexOf('Next step'))
  })
})

it('keeps subordinate review headings attached to their conclusion', () => {
  const input = '## Conclusion\nBinding is unverified.\n### Limitations\nNo assay has run.\n## Next steps\nRun the assay.'
  expect(answerPresentation(input).visible).toBe(input.replace('\n## Next steps', '\n\n## Next steps'))
})

it('does not interpret a shorter fence inside a longer code block as prose', () => {
  const input = '````text\n```\n## Conclusion\nThis is tool output, not a result.\n````\n\n## Conclusion\nNo validated result.'
  const answer = answerPresentation(input)
  expect(answer.visible).toBe('## Conclusion\nNo validated result.')
  expect(answer.folded).toContain('This is tool output, not a result.')
})

it('keeps a meaningful conclusion containing a workflow identifier visible', () => {
  const input = 'The project-refresh-20261016 run failed; validation is still pending.[cite:2]'
  expect(answerPresentation(input).visible).toBe(input)
})

it('keeps prose after a fenced log even without a blank line', () => {
  const answer = answerPresentation('```json\n{"jobs": []}\n```\nNo validated result exists.[cite:1]')
  expect(answer.visible).toBe('No validated result exists.[cite:1]')
  expect(answer.folded).toContain('{"jobs": []}')
})

it('folds an empty Markdown table while keeping the interpretation immediately below it', () => {
  const answer = answerPresentation('## Results\n| Job | State |\n| --- | --- |\nNo execution is recorded; this is not a successful validation.[cite:1]')
  expect(answer.visible).toContain('No execution is recorded; this is not a successful validation.[cite:1]')
  expect(answer.visible).not.toContain('| Job |')
  expect(answer.folded).toContain('| Job | State |')
})

it('retains populated result tables and their citation markers', () => {
  const input = '## Results\n| Sample | Result |\n| --- | --- |\n| A | Unverified.[cite:1] |'
  expect(answerPresentation(input).visible).toBe(input)
})

it('keeps a caveat on the line after an English tool receipt visible', () => {
  const answer = answerPresentation('get_compute_status -> []\nNo execution is recorded; success is unverified.[cite:2]')
  expect(answer.visible).toBe('No execution is recorded; success is unverified.[cite:2]')
  expect(answer.folded).toContain('get_compute_status -> []')
})
