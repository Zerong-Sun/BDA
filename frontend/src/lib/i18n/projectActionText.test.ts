import { describe, expect, it } from 'vitest'
import { en, zh } from './index'
import { projectActionText } from './projectText'

describe('project API action labels', () => {
  it.each([
    ['create_workflow', '创建工作流', 'Create workflow'],
    ['edit_workflow', '继续工作流', 'Continue workflow'],
    ['review_candidates', '查看候选物', 'Review candidates'],
    ['review_results', '解读验证结果', 'Read validation results'],
    ['primary_target_missing', '完成靶标准备', 'Resolve target readiness'],
    ['target_identity_unconfirmed', '确认此靶标身份', 'Confirm this target identity'],
    ['target_structure_unavailable', '准备结构', 'Prepare structure'],
  ])('translates the API code %s in both languages', (code, chinese, english) => {
    expect(projectActionText(code, zh)).toBe(chinese)
    expect(projectActionText(code, en)).toBe(english)
  })

  it.each(['Approve the prepared structure.', '请复核靶标身份。', 'future_action_code', '__proto__'])('preserves an unknown server explanation: %s', (value) => {
    expect(projectActionText(value, zh)).toBe(value)
    expect(projectActionText(value, en)).toBe(value)
  })
})
