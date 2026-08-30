import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeftIcon, SpinnerGapIcon } from '@phosphor-icons/react'
import {
  cancelAgentRun,
  getAgentRun,
  isLive,
  listAgentRuns,
  listAgentTurns,
  startAgentRun,
  type AgentRun,
  type AgentTurn,
} from '../../lib/api/agentRuns'
import { ApiError } from '../../lib/api/client'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { useToastStore } from '../../components/ui/toastStore'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/textarea'
import { StatusPill } from '../../components/ui/StatusPill'
import type { StatusTone } from '../../components/ui/statusTone'

/**
 * Start a durable agent run, watch where it got to, and stop it.
 *
 * The run outlives this panel — that is the whole point of the substrate under
 * it — so nothing here owns the run's progress. Everything is read back from
 * the transcript, and the panel polls only while something is actually live:
 * a finished run cannot change, so asking again would be asking a question with
 * a known answer.
 *
 * Cancelling carries the version as an ETag. A 412 means the run moved on its
 * own between the read and the click, which is usually the run finishing
 * without help, so the answer is to reload rather than insist.
 */

const REFRESH_WHILE_LIVE_MS = 4000

function statusLabel(status: string, copy: Record<string, string>): string {
  switch (status) {
    case 'running':
      return copy.statusRunning
    case 'awaiting_tasks':
      return copy.statusAwaitingTasks
    case 'succeeded':
      return copy.statusSucceeded
    case 'failed':
      return copy.statusFailed
    default:
      return copy.statusCancelled
  }
}

function toneFor(status: string): StatusTone {
  if (status === 'succeeded') return 'green'
  if (status === 'failed') return 'red'
  if (status === 'running') return 'blue'
  if (status === 'awaiting_tasks') return 'amber'
  return 'neutral'
}

export function CopilotAgentRuns() {
  const { t, format } = useI18n()
  const copy = t.copilot.agentRuns
  const { projectId } = useProjectContext()
  const queryClient = useQueryClient()
  const showToast = useToastStore((state) => state.show)
  const [openRunId, setOpenRunId] = useState<string | null>(null)

  const [goal, setGoal] = useState('')
  const [maxTurns, setMaxTurns] = useState('12')
  const [maxCost, setMaxCost] = useState('')

  const runs = useQuery({
    // The project uuid is part of the key: candidates and runs alike must not
    // leak between projects that happen to be empty.
    queryKey: ['agent-runs', projectId],
    queryFn: () => listAgentRuns(projectId as string),
    enabled: Boolean(projectId),
    refetchInterval: (query) =>
      (query.state.data ?? []).some(isLive) ? REFRESH_WHILE_LIVE_MS : false,
  })

  const start = useMutation({
    mutationFn: () => {
      if (!projectId) throw new Error(copy.noProject)
      const cost = Number(maxCost.trim())
      return startAgentRun({
        project_id: projectId,
        goal: goal.trim(),
        max_turns: Number(maxTurns) || 12,
        max_cost_usd_cents: maxCost.trim() && Number.isFinite(cost) ? cost : null,
      })
    },
    onSuccess: (accepted) => {
      setGoal('')
      setOpenRunId(accepted.run.id)
      void queryClient.invalidateQueries({ queryKey: ['agent-runs', projectId] })
    },
    onError: (error) =>
      showToast(error instanceof Error ? error.message : String(error), 'error'),
  })

  if (!projectId) {
    return <p className="px-3 py-2 text-sm text-text-secondary">{copy.noProject}</p>
  }

  if (openRunId) {
    return (
      <AgentRunDetail
        runId={openRunId}
        projectId={projectId}
        onBack={() => setOpenRunId(null)}
      />
    )
  }

  return (
    <div className="space-y-4 px-3 py-3">
      <p className="text-xs text-text-secondary">{copy.intro}</p>
      <form
        className="space-y-2"
        onSubmit={(event) => {
          event.preventDefault()
          start.mutate()
        }}
      >
        <label className="flex flex-col gap-1 text-sm">
          <span>{copy.goal}</span>
          <Textarea
            placeholder={copy.goalPlaceholder}
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
          />
        </label>
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>{copy.maxTurns}</span>
            <Input
              type="number"
              min={1}
              className="w-20 tabular-nums"
              value={maxTurns}
              onChange={(event) => setMaxTurns(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span>{copy.maxCost}</span>
            <Input
              type="number"
              min={0}
              className="w-24 tabular-nums"
              value={maxCost}
              onChange={(event) => setMaxCost(event.target.value)}
            />
          </label>
          <Button type="submit" size="sm" disabled={!goal.trim() || start.isPending}>
            {start.isPending ? copy.starting : copy.start}
          </Button>
        </div>
        <p className="text-xs text-text-secondary">{copy.costHint}</p>
      </form>

      {runs.data && runs.data.length > 0 ? (
        <ul className="space-y-1">
          {runs.data.map((run) => (
            <li key={run.id}>
              <Button
                type="button"
                variant="ghost"
                className="h-auto w-full flex-col items-start gap-1 border border-border p-2 text-left hover:border-primary"
                onClick={() => setOpenRunId(run.id)}
              >
                <span className="flex w-full items-center gap-2">
                  <StatusPill tone={toneFor(run.status)}>
                    {statusLabel(run.status, copy)}
                  </StatusPill>
                  <span className="truncate text-sm">{run.goal}</span>
                </span>
                <span className="text-xs tabular-nums text-text-secondary">
                  {format(copy.turns, { count: run.turn_count })} · {costLabel(run, copy, format)}
                </span>
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-text-secondary">{runs.isLoading ? '' : copy.empty}</p>
      )}
    </div>
  )
}

function costLabel(
  run: AgentRun,
  copy: Record<string, string>,
  format: (template: string, values: Record<string, string | number>) => string,
): string {
  // The server always sends the subtree total; falling back to the run's own
  // cost keeps an older response readable rather than showing a confident zero.
  const subtree = run.subtree_cost_usd_cents ?? run.cost_usd_cents
  // Only say "with subagents" when there actually are some; on a childless run
  // the two numbers are equal and the longer label would imply otherwise.
  if (subtree > run.cost_usd_cents) {
    return format(copy.costWithSubtree, { cents: run.cost_usd_cents, total: subtree })
  }
  return format(copy.cost, { cents: run.cost_usd_cents })
}

function AgentRunDetail({
  runId,
  projectId,
  onBack,
}: {
  runId: string
  projectId: string
  onBack: () => void
}) {
  const { t, format } = useI18n()
  const copy = t.copilot.agentRuns
  const queryClient = useQueryClient()
  const showToast = useToastStore((state) => state.show)

  const run = useQuery({
    queryKey: ['agent-run', runId],
    queryFn: () => getAgentRun(runId),
    refetchInterval: (query) =>
      query.state.data && isLive(query.state.data) ? REFRESH_WHILE_LIVE_MS : false,
  })

  const turns = useQuery({
    queryKey: ['agent-run-turns', runId],
    queryFn: () => listAgentTurns(runId),
    refetchInterval: run.data && isLive(run.data) ? REFRESH_WHILE_LIVE_MS : false,
  })

  const cancel = useMutation({
    mutationFn: () => {
      if (!run.data) throw new Error(copy.cancel)
      return cancelAgentRun(runId, run.data.version)
    },
    onSuccess: (result) => {
      showToast(format(copy.cancelled, { count: result.cancelled_runs }), 'success')
      void queryClient.invalidateQueries({ queryKey: ['agent-run', runId] })
      void queryClient.invalidateQueries({ queryKey: ['agent-runs', projectId] })
    },
    onError: (error) => {
      // 412 is never an overwrite prompt here: the run moved on its own, which
      // usually means it finished before the click landed.
      if (error instanceof ApiError && error.status === 412) {
        showToast(copy.conflict, 'error')
        void queryClient.invalidateQueries({ queryKey: ['agent-run', runId] })
        return
      }
      showToast(error instanceof Error ? error.message : String(error), 'error')
    },
  })

  return (
    <div className="space-y-3 px-3 py-3">
      <div className="flex items-center gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeftIcon aria-hidden="true" /> {copy.close}
        </Button>
        {run.data && isLive(run.data) ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="ms-auto"
            disabled={cancel.isPending}
            onClick={() => cancel.mutate()}
          >
            {cancel.isPending ? copy.cancelling : copy.cancel}
          </Button>
        ) : null}
      </div>

      {run.data ? (
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <StatusPill tone={toneFor(run.data.status)}>
              {statusLabel(run.data.status, copy)}
            </StatusPill>
            {run.data.status === 'awaiting_tasks' ? (
              <SpinnerGapIcon aria-hidden="true" className="h-3.5 w-3.5 animate-spin" />
            ) : null}
          </div>
          <p className="text-sm">{run.data.goal}</p>
          <p className="text-xs tabular-nums text-text-secondary">
            {format(copy.turns, { count: run.data.turn_count })} ·{' '}
            {costLabel(run.data, copy, format)}
          </p>
          {run.data.status === 'awaiting_tasks' ? (
            <p className="text-xs text-text-secondary">{copy.waitingOn}</p>
          ) : null}
          {run.data.error ? (
            <p role="alert" className="text-xs text-destructive">
              {run.data.error}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="space-y-2">
        <h4 className="text-xs uppercase tracking-wide text-text-secondary">{copy.transcript}</h4>
        {turns.data && turns.data.length > 0 ? (
          <ol className="space-y-2">
            {turns.data.map((turn) => (
              <TranscriptTurn key={turn.id} turn={turn} />
            ))}
          </ol>
        ) : (
          <p className="text-sm text-text-secondary">
            {turns.isLoading ? '' : copy.transcriptEmpty}
          </p>
        )}
      </div>
    </div>
  )
}

function TranscriptTurn({ turn }: { turn: AgentTurn }) {
  const { t, format } = useI18n()
  const copy = t.copilot.agentRuns
  const roles: Record<string, string> = {
    user: copy.roleUser,
    assistant: copy.roleAssistant,
    tool: copy.roleTool,
    system: copy.roleSystem,
  }
  // An assistant turn that only requested tools has no prose; naming the calls
  // is the whole of what happened, and an empty bubble would read as a bug.
  const calls = (turn.tool_calls ?? [])
    .map((call) => {
      const record = call as { name?: unknown; function?: { name?: unknown } }
      return String(record.function?.name ?? record.name ?? '')
    })
    .filter(Boolean)

  return (
    <li className="rounded border border-border p-2">
      <span className="text-xs uppercase tracking-wide text-text-secondary">
        {roles[turn.role] ?? turn.role}
      </span>
      {turn.content ? (
        <p className="mt-1 text-sm whitespace-pre-wrap break-words">{turn.content}</p>
      ) : null}
      {calls.length > 0 ? (
        <p className="mt-1 font-mono text-xs text-text-secondary">
          {format(copy.toolCalls, { names: calls.join(', ') })}
        </p>
      ) : null}
    </li>
  )
}
