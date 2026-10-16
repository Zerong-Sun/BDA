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

/** Persisted chat exceptions are diagnostics, never user-facing prose. */
export function chatFailureMessage(error: unknown, zh: boolean): string {
  const message = error instanceof Error ? error.message : typeof error === 'string' ? error : ''
  const payload = error instanceof ApiError && error.payload && typeof error.payload === 'object' ? error.payload as Record<string, unknown> : {}
  const diagnostic = `${typeof payload.error_code === 'string' ? payload.error_code : ''} ${message}`
  if (/\b(?:llm_duplicate_call|copilot_duplicate_message|copilot_duplicate_task)\b|This request was already attempted|automatic replay is blocked/i.test(diagnostic)) {
    return zh ? '相同请求已处理过或正在处理，重复调用已阻止。请查看已有回复或已保存报告，不要重复发送。' : 'This request was already attempted or is being processed. The duplicate call was blocked. Check the existing reply or saved report instead of resending it.'
  }
  if (/\b(?:llm_pricing_required|copilot_budget_pricing_required|llm_scope_required|llm_endpoint_missing|credential_unavailable|llm_config_reserved_fields|copilot_output_limit_invalid|llm_multiple_completions_not_allowed)\b|Current model prices are not configured|A cost ceiling requires administrator-configured bda_pricing|A durable task scope is required|LLM provider endpoint is not configured|Configured credential reference is unavailable|LLM provider config cannot set reserved request fields|A positive output token limit is required|Each model call must request exactly one completion/i.test(diagnostic)) {
    return zh ? '模型调用配置尚未就绪，请联系管理员检查。可先查看已保存报告。' : 'Model calls are not configured correctly. Ask an administrator to check; saved reports remain available.'
  }
  if (taskAllowanceMessage(error, zh)) {
    return zh ? '本轮已达到调用限制并停止。可缩小范围继续提问，或新建对话；已保存报告仍可查看。' : 'This turn reached its call limit and stopped. Narrow the question to continue, or start a new conversation; saved reports remain available.'
  }
  if (/\b(?:llm_completion_deadline_exceeded|ReadTimeout|ConnectTimeout|WriteTimeout|PoolTimeout)\b|Model completion exceeded the \d+(?:\.\d+)?-second total deadline|timed? ?out/i.test(diagnostic)) {
    return zh ? '本次回复超时，未获得可用回答。请先查看已有记录；后续提问可缩小范围，避免反复重试。' : 'The reply timed out and no usable answer was received. Check existing records first; narrow any follow-up question instead of retrying repeatedly.'
  }
  if (/\b(?:llm_unbounded_input|llm_output_truncated)\b|This input requires a bounded token estimate|The model reached its output limit/i.test(diagnostic)) {
    return zh ? '本次请求或回复超出处理范围，未得到完整回答。请查看已保存报告，并将问题拆成更小的范围。' : 'The request or reply exceeded the supported size, so no complete answer was obtained. Check saved reports and split the question into smaller parts.'
  }
  if (/\bllm_output_filtered\b|The provider filtered this response/i.test(diagnostic)) {
    return zh ? '本次回复未通过模型服务检查，未生成可用回答。请查看已有资料。' : 'The model service did not accept this response, so no usable answer was generated. Check the existing materials.'
  }
  return zh ? '本次未能生成可用回答。请先查看已保存报告；如需排查，请联系管理员检查任务记录。' : 'No usable answer was generated. Check saved reports first; ask an administrator to inspect the task record if needed.'
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
