import type { AgentRun } from '../../lib/api/agentRuns'
import { matchBot, resolveBot, type CopilotBot } from './bots/registry'

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

/**
 * What a run's transport status implies about its delivery, for a run that has
 * not computed one yet. A run carries both, and they answer different
 * questions: `failed` is how the process ended, `blocked` is what the person
 * now has in hand.
 */
const STATUS_FALLBACK: Record<string, string> = {
  running: 'running', awaiting_tasks: 'waiting', failed: 'blocked', cancelled: 'cancelled',
}

const DELIVERY_LABELS: Record<string, [string, string]> = {
  running: ['Working', '进行中'], waiting: ['Waiting for results', '等待结果'],
  completed: ['Draft ready for review', '交付物待审核'], partial: ['Partially delivered', '部分完成'],
  blocked: ['Blocked', '受阻'], needs_input: ['Needs your input', '需要补充信息'],
  review_required: ['Needs review', '需要审核'], cancelled: ['Cancelled', '已取消'],
}

export function deliveryState(run: AgentRun): string {
  return String(run.outcome?.status ?? STATUS_FALLBACK[run.status] ?? 'review_required')
}
export function deliveryLabel(run: AgentRun, zh: boolean): string {
  return (DELIVERY_LABELS[deliveryState(run)] ?? DELIVERY_LABELS.review_required)[zh ? 1 : 0]
}

/**
 * The same label for a room entry, which carries the delivery the server
 * already resolved rather than the whole run. Sharing the table is the point:
 * a task reading "Needs your input" in the inbox and something else in the
 * room would be two vocabularies for one state.
 */
export function roomTaskLabel(task: { status: string; delivery_state?: string | null }, zh: boolean): string {
  const state = task.delivery_state || STATUS_FALLBACK[task.status] || 'review_required'
  return (DELIVERY_LABELS[state] ?? DELIVERY_LABELS.review_required)[zh ? 1 : 0]
}

/** One kind of guided task and the operator accountable for it. */
export interface TaskOwner {
  key: string
  bot: CopilotBot
  service: ServiceKind
}

/** Every (operator, recipe) an operator answers for, in the roster's chain order. */
export function taskOwners(bots: readonly CopilotBot[]): TaskOwner[] {
  return bots.flatMap((bot) => (bot.task_services ?? []).map((service) => ({ key: `${bot.id}:${service}`, bot, service: service as ServiceKind })))
}

export function ownerOf(kind: string, owners: readonly TaskOwner[]): TaskOwner | undefined {
  return owners.find((owner) => owner.service === kind)
}

/**
 * A visible suggestion of who should own a goal and as which kind of task. An
 * operator the goal names outranks the keyword guess; within that operator the
 * guessed kind is kept when it owns it.
 */
export function suggestAssignee(goal: string, owners: readonly TaskOwner[]): TaskOwner | undefined {
  const guess = suggestService(goal)
  const named = matchBot(goal, [...new Map(owners.map((owner) => [owner.bot.id, owner.bot])).values()])
  if (named) {
    const own = owners.filter((owner) => owner.bot.id === named.id)
    return own.find((owner) => owner.service === guess) ?? own[0]
  }
  return ownerOf(guess, owners)
}

export interface OwnerGroup {
  key: string
  botId: string | null
  bot: CopilotBot | undefined
  runs: AgentRun[]
}

/**
 * Tasks under the operator that answers for them, in roster order. A run
 * recorded under a retired id groups under the operator that absorbed it; an id
 * nothing resolves keeps its own group; runs started without an owner come last.
 */
export function groupRunsByOwner(runs: readonly AgentRun[], bots: readonly CopilotBot[]): OwnerGroup[] {
  const groups = new Map<string | null, OwnerGroup>()
  for (const run of runs) {
    const bot = resolveBot(run.bot, bots)
    const botId = bot?.id ?? run.bot ?? null
    const group = groups.get(botId) ?? { key: botId ?? 'unassigned', botId, bot, runs: [] }
    group.runs.push(run)
    groups.set(botId, group)
  }
  const rank = (group: OwnerGroup) => group.botId === null ? bots.length + 1 : group.bot ? bots.indexOf(group.bot) : bots.length
  return [...groups.values()].sort((a, b) => rank(a) - rank(b))
}
