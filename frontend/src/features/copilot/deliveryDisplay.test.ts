import { describe, expect, it } from 'vitest'
import { ApiError } from '../../lib/api/client'
import { chatFailureMessage, deliveryMessage, taskErrorMessage } from './deliveryDisplay'

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


describe('safe chat failure messages', () => {
  it.each([
    ['The task allowance cannot cover another request.', '本轮已达到调用限制', 'This turn reached its call limit'],
    ['llm_call_limit: The task call limit has been reached.', '本轮已达到调用限制', 'This turn reached its call limit'],
    ['This request was already attempted; automatic replay is blocked.', '重复调用已阻止', 'duplicate call was blocked'],
    ['Current model prices are not configured; no request was sent.', '模型调用配置尚未就绪', 'not configured correctly'],
    ['Configured credential reference is unavailable', '模型调用配置尚未就绪', 'not configured correctly'],
    ['Model completion exceeded the 180-second total deadline; no response was accepted.', '本次回复超时', 'reply timed out'],
    ['llm_output_truncated', '未得到完整回答', 'no complete answer'],
    ['The provider filtered this response; partial output was not accepted.', '未通过模型服务检查', 'did not accept this response'],
  ])('classifies stored diagnostic %s without exposing it', (diagnostic, chinese, english) => {
    const error = `${diagnostic} Internal endpoint https://secret.invalid?token=example-private-token; 100 cents`
    expect(chatFailureMessage(error, true)).toContain(chinese)
    expect(chatFailureMessage(error, false)).toContain(english)
    for (const zh of [true, false]) expect(chatFailureMessage(error, zh)).not.toMatch(/secret|token|100|cents|https:|¥|计费/)
  })

  it('uses structured codes and safely replaces unknown or missing diagnostics', () => {
    expect(chatFailureMessage(new ApiError('https://secret.invalid', 409, { error_code: 'llm_budget_exhausted' }), true)).toContain('本轮已达到调用限制')
    for (const diagnostic of ['Traceback: auth sk-private at https://secret.invalid', null, undefined]) {
      expect(chatFailureMessage(diagnostic, false)).toBe('No usable answer was generated. Check saved reports first; ask an administrator to inspect the task record if needed.')
      expect(chatFailureMessage(diagnostic, true)).not.toMatch(/Traceback|private|https:/)
    }
  })
})
