import { describe, expect, it } from 'vitest'
import { ApiError } from '../../lib/api/client'
import { deliveryMessage, taskErrorMessage } from './deliveryDisplay'

describe('task allowance messages', () => {
  it.each([
    'budget: cost limit reached (100 cents across the run tree)',
    'The approved budget is exhausted. Start a new task with a new budget.',
    'The next model call exceeds the remaining estimated budget.',
    'The task allowance cannot cover another request.',
    'llm_call_limit: The task call limit has been reached.',
  ])('localizes %s without monetary details', (error) => {
    expect(deliveryMessage(error, true)).toBe('任务调用额度已耗尽，已保存的结果仍可查看。')
    expect(deliveryMessage(error, false)).toBe('This task’s model-call allowance is exhausted. Saved results remain available.')
  })
  it('uses the structured failure code even when its server detail is not recognizable', () => {
    const error = new ApiError('Internal allowance limit 100 cents', 409, { error_code: 'copilot_task_budget_exhausted' })
    expect(taskErrorMessage(error, true)).toBe('任务调用额度已耗尽，已保存的结果仍可查看。')
    expect(error.message).toBe('Internal allowance limit 100 cents')
  })
  it('distinguishes missing model configuration from exhausted allowance', () => {
    expect(taskErrorMessage(new ApiError('Pricing missing', 409, { error_code: 'llm_pricing_required' }), true)).toBe('模型调用配置尚未就绪，请联系管理员检查。本次未发起调用。')
  })
  it('preserves unrelated failures and scientific cost statements', () => {
    expect(taskErrorMessage(new Error('Storage unavailable'), false)).toBe('Storage unavailable')
    expect(deliveryMessage('The assay cost was compared across protocols.', true)).toBe('The assay cost was compared across protocols.')
  })
})
