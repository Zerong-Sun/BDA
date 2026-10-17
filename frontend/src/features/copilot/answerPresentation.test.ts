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
})
