import { useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { ArrowRightIcon, ClockCounterClockwiseIcon } from '@phosphor-icons/react'
import { Button } from '../../components/ui/Button'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { isLive, listAgentRunsPage } from '../../lib/api/agentRuns'
import { AgentRunDetail } from './CopilotAgentRuns'
import { deliveryLabel } from './taskPresentation'

/** A read-only entry into persisted work. Opening it never starts a new run. */
export function CopilotReview() {
  const { projectId } = useProjectContext()
  return <ProjectReview key={projectId} projectId={projectId} />
}

function ProjectReview({ projectId }: { projectId: string }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const [runId, setRunId] = useState<string | null>(null)
  const runs = useInfiniteQuery({
    queryKey: ['agent-runs', projectId, 'review'],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => listAgentRunsPage(projectId, pageParam),
    getNextPageParam: (page) => page.next_cursor || undefined,
    enabled: Boolean(projectId),
    refetchInterval: (query) => query.state.data?.pages.some((page) => page.items.some(isLive)) ? 4000 : false,
  })
  if (!projectId) return <div className="p-4"><p className="mb-3">{zh ? '选择项目后查看决策与执行记录。' : 'Choose a project to inspect decisions and execution records.'}</p><Button type="button" render={<Link to="/projects" />}>{zh ? '选择项目' : 'Choose a project'}</Button></div>
  if (runId) return <AgentRunDetail key={runId} runId={runId} projectId={projectId} onBack={() => setRunId(null)} />
  const items = [...new Map(runs.data?.pages.flatMap((page) => page.items).map((run) => [run.id, run])).values()]
  return <section className="copilot-review space-y-4 p-4" aria-label={zh ? '决策与参数' : 'Decisions & parameters'}>
    <div>
      <h3 className="flex items-center gap-2 font-semibold"><ClockCounterClockwiseIcon aria-hidden="true" />{zh ? '检查每一次执行' : 'Inspect each execution'}</h3>
      <p className="mt-1 text-sm text-text-secondary">{zh ? '选择任务，查看交付依据和待确认事项。' : 'Choose a task to review its deliverable, evidence and remaining checks.'}</p>
    </div>
    <Link className="inline-flex min-h-11 items-center gap-2 text-sm text-primary" to={`/research?${new URLSearchParams({ project: projectId, tab: 'timeline' })}`}>{zh ? '查看项目决策树' : 'Open the project decision tree'}<ArrowRightIcon aria-hidden="true" /></Link>
    {runs.isLoading ? <p role="status">{zh ? '加载执行记录…' : 'Loading execution records…'}</p> : null}
    {runs.isSuccess && !items.length ? <p>{zh ? '还没有执行记录。发起任务后，参数和交付内容会保存在这里。' : 'No executions yet. Task parameters and deliverables will appear here.'}</p> : null}
    <ul className="divide-y divide-border-soft">
      {items.map((run) => <li key={run.id}>
        <Button type="button" variant="ghost" className="h-auto w-full flex-col items-start whitespace-normal px-0 py-3 text-left" onClick={() => setRunId(run.id)}>
          <span className="text-xs text-primary">{deliveryLabel(run, zh)}{run.parent_run_id ? (zh ? ' · 子任务' : ' · Subtask') : ''}</span>
          <span className="break-words text-sm font-medium">{run.goal}</span>
          <span className="text-xs text-text-secondary">{run.bot ?? (zh ? '未记录负责人' : 'Owner not recorded')}</span>
        </Button>
      </li>)}
    </ul>
    {runs.isError ? <div role="alert"><p>{zh ? '执行记录加载失败，已加载内容保留。' : 'Execution records could not be loaded. Loaded records are retained.'}</p><Button type="button" variant="outline" onClick={() => { if (runs.isFetchNextPageError) void runs.fetchNextPage(); else void runs.refetch() }}>{zh ? '重试' : 'Retry'}</Button></div> : null}
    {runs.hasNextPage ? <Button type="button" variant="outline" disabled={runs.isFetching} onClick={() => void runs.fetchNextPage()}>{zh ? '加载更多执行记录' : 'Load more executions'}</Button> : null}
  </section>
}
