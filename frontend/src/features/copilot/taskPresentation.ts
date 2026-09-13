import type { AgentRun } from '../../lib/api/agentRuns'

export type ServiceKind = 'brief' | 'literature' | 'planning' | 'execution' | 'interpretation'

/** A visible, editable routing suggestion; never an authorization decision. */
export function suggestService(goal: string): ServiceKind {
  if (/文献|调研|综述|literature|research|review evidence/i.test(goal)) return 'literature'
  if (/任务书|研究目标|prompt|brief|objective/i.test(goal)) return 'brief'
  if (/失败|异常|运行|作业|error|job|execut|monitor|fail/i.test(goal)) return 'execution'
  if (/方案|路线|workflow|plan|design|设计/i.test(goal)) return 'planning'
  return 'interpretation'
}

export function isQuestion(goal: string): boolean {
  return /[?？]$|^(什么是|解释一下|请解释|如何理解|what is|what are|explain|why\b)/i.test(goal.trim()) &&
    !/帮我|请.*(?:生成|检索|调研|起草)|please.*(?:research|draft|prepare)/i.test(goal)
}

export function deliveryState(run: AgentRun): string {
  return String(run.outcome?.status ?? ({ running: 'running', awaiting_tasks: 'waiting', failed: 'blocked', cancelled: 'cancelled' } as Record<string, string>)[run.status] ?? 'review_required')
}
export function deliveryLabel(run: AgentRun, zh: boolean): string {
  const labels: Record<string, [string, string]> = {
    running: ['Working', '进行中'], waiting: ['Waiting for results', '等待结果'],
    completed: ['Draft ready for review', '交付物待审核'], partial: ['Partially delivered', '部分完成'],
    blocked: ['Blocked', '受阻'], needs_input: ['Needs your input', '需要补充信息'],
    review_required: ['Needs review', '需要审核'], cancelled: ['Cancelled', '已取消'],
  }
  return (labels[deliveryState(run)] ?? labels.review_required)[zh ? 1 : 0]
}
