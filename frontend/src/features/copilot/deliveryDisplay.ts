import { ApiError } from '../../lib/api/client'
import type { AgentRun } from '../../lib/api/agentRuns'

/** Match the server's Unicode character count, including original section keys. */
export function reportCharacters(outcome: { summary?: string; sections?: Record<string, string>; missing?: string[]; next_action?: string }): number {
  const fields = [outcome.summary ?? '', outcome.next_action ?? '', ...Object.entries(outcome.sections ?? {}).flat(), ...(outcome.missing ?? [])]
  return fields.reduce((total, value) => total + Array.from(value).length, 0)
}

export function executionLabel(status: AgentRun['status'], zh: boolean): string {
  const labels: Record<string, [string, string]> = {
    running: ['Running', '执行中'], awaiting_tasks: ['Waiting for team results', '等待成员结果'],
    succeeded: ['Execution finished', '执行结束'], failed: ['Execution failed', '执行失败'], cancelled: ['Cancelled', '已取消'],
  }
  return labels[status]?.[zh ? 1 : 0] ?? (zh ? '状态未知' : 'Unknown status')
}

/** Present operational allowance failures without exposing internal monetary limits. */
export function taskAllowanceMessage(error: unknown, zh: boolean): string | undefined {
  const message = error instanceof Error ? error.message : String(error ?? '')
  const payload = error instanceof ApiError && error.payload && typeof error.payload === 'object' ? error.payload as Record<string, unknown> : {}
  const code = typeof payload.error_code === 'string' ? payload.error_code : ''
  const diagnostic = `${code} ${message}`
  if (/\b(?:llm_pricing_required|copilot_budget_pricing_required)\b|Current model prices are not configured|A cost ceiling requires administrator-configured bda_pricing/i.test(diagnostic)) {
    return zh ? '模型调用配置尚未就绪，请联系管理员检查。本次未发起调用。' : 'Model calls are not configured yet. Ask an administrator to check; no call was made.'
  }
  if (/\b(?:llm_budget_exhausted|llm_call_limit|copilot_task_budget_exhausted|copilot_budget_insufficient|copilot_task_turn_limit|copilot_turn_limit_reached)\b|cost limit reached|model call limit reached|The task call limit has been reached|The task allowance cannot cover another request|The approved budget is exhausted|The next model call exceeds the remaining estimated budget|The transcript turn limit was reached/i.test(diagnostic)) {
    return zh ? '任务调用额度已耗尽，已保存的结果仍可查看。' : 'This task’s model-call allowance is exhausted. Saved results remain available.'
  }
  return undefined
}

export function taskErrorMessage(error: unknown, zh: boolean): string {
  return taskAllowanceMessage(error, zh) ?? deliveryMessage(error instanceof Error ? error.message : String(error), zh)
}

export function deliveryMessage(message: string, zh: boolean): string {
  const allowance = taskAllowanceMessage(message, zh)
  if (allowance) return allowance
  if (!zh) return message
  const deadline = /^Model completion exceeded the (\d+)-second total deadline; no response was accepted\.$/.exec(message)
  if (deadline) return `模型在 ${deadline[1]} 秒内未完成回复，本次未生成可接受的报告。`
  if (message === 'Review the failure and continue after correcting the cause.') return '先排查失败原因，修正后再继续任务。'
  return message
}
