import { taskErrorMessage } from './deliveryDisplay'
import { ToolEvidenceLazy } from './ToolEvidenceLazy'
import { useState } from 'react'
import { Link, useLocation } from 'react-router'
import { requireCopilotWrite, useCopilotReadOnly } from './commandAccess'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeftIcon, SpinnerGapIcon } from '@phosphor-icons/react'
import {
  cancelAgentRun,
  continueAgentRun,
  getAgentRun,
  isLive,
  listAgentRuns,
  listAgentTurnsPage,
  startAgentRun,
  type AgentTurn,
} from '../../lib/api/agentRuns'
import { TaskDelivery } from './TaskDelivery'
import { PrepareTaskRetry } from './PrepareTaskRetry'
import { RunParameters } from './RunParameters'
import { AppliedProceduralSkills } from './ProceduralSkills'
import { BotAvatar } from './BotAvatar'
import { useCopilotBots } from './bots/registry'
import { Checkbox } from '../../components/ui/checkbox'
import { Disclosure } from '../../components/ui/Disclosure'
import { deliveryLabel } from './taskPresentation'
import { ApiError } from '../../lib/api/client'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { useToastStore } from '../../components/ui/toastStore'
import { Button } from '../../components/ui/Button'
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

export function CopilotAgentRuns({ initialGoal = '', skills }: { initialGoal?: string; skills?: string[] }) {
  const { t, format, language } = useI18n()
  const readOnly = useCopilotReadOnly()
  const copy = t.copilot.agentRuns
  const { projectId } = useProjectContext()
  const queryClient = useQueryClient()
  const showToast = useToastStore((state) => state.show)
  const [openRunId, setOpenRunId] = useState<string | null>(null)

  const [goal, setGoal] = useState(initialGoal)

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
      requireCopilotWrite()
      if (!projectId) throw new Error(copy.noProject)
      return startAgentRun({
        project_id: projectId,
        goal: goal.trim(),
        ...(skills ? { skills } : {}),
      })
    },
    onSuccess: (accepted) => {
      setGoal('')
      setOpenRunId(accepted.run.id)
      void queryClient.invalidateQueries({ queryKey: ['agent-runs', projectId] })
    },
    onError: (error) =>
      showToast(taskErrorMessage(error, language === 'zh'), 'error'),
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
          <Button type="submit" size="sm" disabled={readOnly || !goal.trim() || start.isPending}>
            {start.isPending ? copy.starting : copy.start}
          </Button>
        </div>
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
                  {format(copy.turns, { count: run.turn_count })}
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

export function AgentRunDetail({
  runId,
  projectId,
  onBack,
}: {
  runId: string
  projectId: string
  onBack: () => void
}) {
  const { t, format, language } = useI18n()
  const location = useLocation()
  const inWorkspace = location.pathname === '/bots' && new URLSearchParams(location.search).get('run') === runId
  const readOnly = useCopilotReadOnly()
  const copy = t.copilot.agentRuns
  const queryClient = useQueryClient()
  const showToast = useToastStore((state) => state.show)

  const [followup, setFollowup] = useState('')
  const [retainedWrites, setRetainedWrites] = useState<string[] | null>(null)
  const run = useQuery({
    queryKey: ['agent-run', projectId, runId],
    queryFn: async () => {
      const result = await getAgentRun(runId)
      if (result.project_id !== projectId) throw new Error(language === 'zh' ? '此任务不属于当前项目，请返回任务列表。' : 'This task belongs to another project. Return to the task list.')
      return result
    },
    refetchInterval: (query) =>
      query.state.data && isLive(query.state.data) ? REFRESH_WHILE_LIVE_MS : false,
  })

  const bots = useCopilotBots()
  const owner = bots.data?.find((bot) => bot.id === run.data?.bot)

  const turns = useInfiniteQuery({
    queryKey: ['agent-run-turns', projectId, runId, 'pages'],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => listAgentTurnsPage(runId, pageParam),
    getNextPageParam: (page) => page.next_cursor || undefined,
    enabled: Boolean(run.data) && !run.isError,
    refetchInterval: run.data && isLive(run.data) ? REFRESH_WHILE_LIVE_MS : false,
  })
  const transcript = [...new Map(turns.data?.pages.flatMap((page) => page.items).map((turn) => [turn.id, turn])).values()]

  const cancel = useMutation({
    mutationFn: () => {
      requireCopilotWrite()
      if (!run.data) throw new Error(copy.cancel)
      return cancelAgentRun(runId, run.data.version)
    },
    onSuccess: (result) => {
      showToast(result.cancelled_runs > 0 ? format(copy.cancelled, { count: result.cancelled_runs })
        : (language === 'zh' ? '任务已结束，已刷新最终结果。' : 'The task already ended. Its final result has been refreshed.'), 'success')
      void queryClient.invalidateQueries({ queryKey: ['agent-run', projectId, runId] })
      void queryClient.invalidateQueries({ queryKey: ['agent-runs', projectId] })
    },
    onError: (error) => {
      // 412 is never an overwrite prompt here: the run moved on its own, which
      // usually means it finished before the click landed.
      if (error instanceof ApiError && error.status === 412) {
        showToast(copy.conflict, 'error')
        void queryClient.invalidateQueries({ queryKey: ['agent-run', projectId, runId] })
        return
      }
      showToast(taskErrorMessage(error, language === 'zh'), 'error')
    },
  })

  const continuation = useMutation({
    mutationFn: () => { requireCopilotWrite(); return continueAgentRun(runId, run.data!.version, followup.trim(), retainedWrites ?? undefined) },
    onSuccess: () => {
      setFollowup('')
      setRetainedWrites(null)
      void queryClient.invalidateQueries({ queryKey: ['agent-run', projectId, runId] })
      void queryClient.invalidateQueries({ queryKey: ['agent-run-turns', projectId, runId] })
      void queryClient.invalidateQueries({ queryKey: ['agent-runs', projectId] })
    },
    onError: () => { void queryClient.invalidateQueries({ queryKey: ['agent-run', projectId, runId] }) },
  })

  return (
    <div className="space-y-3 px-3 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeftIcon aria-hidden="true" /> {copy.close}
        </Button>
        <Button type="button" variant="outline" size="sm" disabled={run.isFetching || turns.isFetching} onClick={() => { void run.refetch(); if (run.data && !run.isError) void turns.refetch() }}>{run.isFetching || turns.isFetching ? (language === 'zh' ? '刷新中…' : 'Refreshing…') : (language === 'zh' ? '刷新记录' : 'Refresh records')}</Button>
        {run.data && !inWorkspace ? <Button type="button" variant="ghost" size="sm" render={<Link to={`/bots?${new URLSearchParams({ project: projectId, view: 'tasks', run: runId })}`} />}>{language === 'zh' ? '在工作区展开' : 'Open workspace'}</Button> : null}
        {run.data && isLive(run.data) ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="ms-auto"
            disabled={readOnly || cancel.isPending}
            onClick={() => cancel.mutate()}
          >
            {cancel.isPending ? copy.cancelling : copy.cancel}
          </Button>
        ) : null}
      </div>
      {cancel.isPending ? <p role="status" className="text-sm text-text-secondary">{language === 'zh' ? '正在请求取消。当前调用可能需要先结束；请等待后台确认。' : 'Cancellation requested. The current call may need to finish; waiting for backend confirmation.'}</p> : null}

      {run.data ? (
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <StatusPill tone={toneFor(run.data.status)}>
              {deliveryLabel(run.data, language === 'zh')}
            </StatusPill>
            {run.data.status === 'awaiting_tasks' ? (
              <SpinnerGapIcon aria-hidden="true" className="h-3.5 w-3.5 animate-spin" />
            ) : null}
          </div>
          {run.data.bot ? (
            <p className="task-owner-heading text-text-secondary">
              {owner ? <BotAvatar id={owner.id} stance={owner.stance} /> : null}
              {language === 'zh' ? `负责人：${owner?.title_zh ?? run.data.bot}` : `Owner: ${owner?.title ?? run.data.bot}`}
            </p>
          ) : null}
          {run.data.goal.length > 160 ? <Disclosure title={language === 'zh' ? '查看完整任务要求' : 'Full task request'}><p className="whitespace-pre-wrap break-words text-sm leading-7">{run.data.goal}</p></Disclosure> : <p className="text-sm leading-7">{run.data.goal}</p>}
          <p className="text-xs tabular-nums text-text-secondary">
            {format(copy.turns, { count: run.data.turn_count })}
          </p>
          {run.data.status === 'awaiting_tasks' ? (
            <p className="text-xs text-text-secondary">{copy.waitingOn}</p>
          ) : null}
        </div>
      ) : null}

      {readOnly ? <p role="status" className="text-sm text-text-secondary">{language === 'zh' ? '只读模式：可以查看任务与交付物。' : 'Read-only mode: you can inspect tasks and deliverables.'}</p> : null}
      {run.data ? <TaskDelivery run={run.data} /> : null}
      {run.data ? <AppliedProceduralSkills contract={run.data.task_contract ?? {}} outcome={run.data.outcome ?? {}} /> : null}
      {run.isLoading ? <p role="status">{language === 'zh' ? '加载任务交付…' : 'Loading task delivery…'}</p> : null}
      {run.error || turns.error ? <div className="space-y-2"><p role="alert">{run.error instanceof Error ? run.error.message : (language === 'zh' ? '任务记录加载失败，请重试。' : 'Task records could not be loaded. Try again.')}</p><Button type="button" variant="outline" onClick={() => { if (run.isError) void run.refetch(); if (turns.isError) void turns.refetch() }}>{language === 'zh' ? '重新加载任务记录' : 'Reload task records'}</Button></div> : null}
      {run.data && !run.data.parent_run_id && ['succeeded', 'failed'].includes(run.data.status) ? <form className="space-y-3 rounded-lg border border-border bg-surface-2 p-3" onSubmit={(event) => { event.preventDefault(); if (!readOnly && followup.trim() && !continuation.isPending) continuation.mutate() }}>
        <h4 className="text-sm font-semibold">{language === 'zh' ? '继续处理此任务' : 'Continue working on this task'}</h4>
        <label className="block text-sm">{language === 'zh' ? '补充信息或修改要求' : 'Add information or revise the request'}<Textarea placeholder={language === 'zh' ? '说明要补充的证据、修改的范围或已修正的问题' : 'Describe new evidence, scope changes or the issue you corrected'} disabled={readOnly || continuation.isPending} value={followup} onChange={(e) => setFollowup(e.target.value)} /></label>
        {Array.isArray(run.data.task_contract?.authorized_writes) && run.data.task_contract.authorized_writes.length ? <div className="space-y-1 text-sm"><p>{language === 'zh' ? '继续时可取消下列写入授权：' : 'You may revoke these writes before continuing:'}</p>{(run.data.task_contract.authorized_writes as string[]).map((tool) => <label key={tool} className="flex items-center gap-2"><Checkbox disabled={readOnly || continuation.isPending} checked={(retainedWrites ?? run.data!.task_contract!.authorized_writes as string[]).includes(tool)} onCheckedChange={(checked) => { const current = retainedWrites ?? run.data!.task_contract!.authorized_writes as string[]; setRetainedWrites(checked ? [...current, tool] : current.filter((value) => value !== tool)) }} />{tool === 'start_literature_search' ? (language === 'zh' ? '外部文献检索' : 'External literature search') : tool === 'create_knowledge_draft' ? (language === 'zh' ? '保存待审核笔记' : 'Save research notes') : tool}</label>)}</div> : null}
        <p className="text-xs text-text-secondary">{language === 'zh' ? '沿用本任务剩余调用额度；达到上限后停止。' : 'Uses this task’s remaining model calls and stops at its limit.'}</p>
        <Button type="submit" disabled={readOnly || !followup.trim() || continuation.isPending}>{continuation.isPending ? (language === 'zh' ? '提交中…' : 'Submitting…') : (language === 'zh' ? '继续此任务' : 'Continue this task')}</Button>
        {continuation.error ? <p role="alert">{taskErrorMessage(continuation.error, language === 'zh')}</p> : null}
      </form> : null}
      <Disclosure key={runId} title={copy.transcript}>
        {transcript.length > 0 ? (
          <ol className="space-y-2">
            {transcript.map((turn) => (
              <TranscriptTurn key={turn.id} turn={turn} projectId={projectId} />
            ))}
          </ol>
        ) : (
          <p className="text-sm text-text-secondary">
            {turns.isLoading ? '' : copy.transcriptEmpty}
          </p>
        )}
        {turns.hasNextPage ? <Button type="button" variant="outline" disabled={turns.isFetching} onClick={() => void turns.fetchNextPage()}>{language === 'zh' ? '加载后续记录' : 'Load later records'}</Button> : null}
      </Disclosure>
      {run.data ? <PrepareTaskRetry run={run.data} followup={followup} disabled={readOnly || continuation.isPending} /> : null}
      {run.data ? <RunParameters run={run.data} /> : null}

    </div>
  )
}

function TranscriptTurn({ turn, projectId }: { turn: AgentTurn; projectId: string }) {
  const { t, format, language } = useI18n()
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
        <div className="mt-1 text-sm whitespace-pre-wrap break-words">{turn.role === 'tool' ? <Disclosure title={copy.roleTool}><pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all text-xs">{turn.content}</pre></Disclosure> : turn.content}</div>
      ) : null}
      {turn.role === 'tool' ? <ToolEvidenceLazy projectId={projectId} calls={turn.tool_calls} content={turn.content} /> : null}
      {calls.length > 0 ? (
        <p className="mt-1 font-mono text-xs text-text-secondary">
          {format(copy.toolCalls, { names: calls.join(', ') })}
        </p>
      ) : null}
      {calls.length > 0 ? <Disclosure title={language === 'zh' ? '查看调用参数' : 'Inspect call parameters'}>
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(turn.tool_calls, null, 2)}</pre>
      </Disclosure> : null}
    </li>
  )
}
