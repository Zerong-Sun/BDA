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

export function deliveryMessage(message: string, zh: boolean): string {
  if (!zh) return message
  const deadline = /^Model completion exceeded the (\d+)-second total deadline; no response was accepted\.$/.exec(message)
  if (deadline) return `模型在 ${deadline[1]} 秒内未完成回复，本次未生成可接受的报告。`
  if (message === 'Review the failure and continue after correcting the cause.') return '先排查失败原因，修正后再继续任务。'
  return message
}
