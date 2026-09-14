import { useEffect } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeftIcon, ArrowRightIcon } from '@phosphor-icons/react'
import type { HandoffResponse } from '../lib/api/generated'
import { isLive, listAgentRuns, listTaskServices, type AgentRun } from '../lib/api/agentRuns'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useAppStore } from '../lib/store/appStore'
import { useI18n } from '../lib/i18n'
import { projectText } from '../lib/i18n/projectText'
import { Button } from '../components/ui/Button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/Tabs'
import { ApiState } from '../components/ui/ApiState'
import { Frame } from '../components/reui/frame'
import { BotAvatar } from '../features/copilot/BotAvatar'
import { BotRoster } from '../features/copilot/BotRoster'
import { CopilotChat } from '../features/copilot/CopilotChat'
import { AgentRunDetail } from '../features/copilot/CopilotAgentRuns'
import { HandoffCard } from '../features/copilot/CopilotChain'
import { useCopilotHandoffs } from '../features/copilot/handoffs'
import { useCopilotReadOnly } from '../features/copilot/commandAccess'
import { reviewersOf, successorsOf, useCopilotBots, type CopilotBot } from '../features/copilot/bots/registry'
import { BOT_WORKBENCHES, botHref, workbenchHref } from '../features/copilot/bots/workbenches'
import { deliveryLabel } from '../features/copilot/taskPresentation'

/**
 * One operator's responsibility page: what it answers for, what it is holding,
 * what was handed to it and what it handed on, who checks it, and where its work
 * lives. The roster used to be a way to change the chat's scope; a team member
 * is better read as a role with a desk than as a setting.
 */
export function BotDetailPage() {
  const { botId = '' } = useParams()
  const { projectId } = useProjectContext()
  return <BotResponsibility key={`${projectId}:${botId}`} botId={botId} />
}

function BotResponsibility({ botId }: { botId: string }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const navigate = useNavigate()
  const { activeProject, projectId, projectsLoading, projectsError, projectsQueryError, refetchProjects } = useProjectContext()
  const [search, setSearch] = useSearchParams()
  const bots = useCopilotBots()
  const bot = bots.data?.find((entry) => entry.id === botId)
  const setSessionBot = useAppStore((s) => s.setCopilotSessionBot)
  const selectedEntities = useAppStore((s) => s.copilotSelectedEntityIds)
  // Opening an operator's page scopes this project's conversation to it, as
  // choosing it in the roster did before the roster became navigation.
  useEffect(() => {
    if (projectId && bot) setSessionBot(projectId, bot.id)
  }, [projectId, bot, setSessionBot])
  const view = search.get('view') === 'chat' ? 'chat' : 'work'
  const runId = search.get('run')
  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(search)
    if (value) next.set(key, value)
    else next.delete(key)
    setSearch(next)
  }
  const team = `/bots?project=${encodeURIComponent(projectId)}`
  const name = (entry: CopilotBot) => zh ? entry.title_zh : entry.title
  const context = `route=/bots/${botId}; project_id=${projectId}; name=${activeProject?.name ?? ''}; bot=${botId}; ${selectedEntities.map((id) => `entity=${encodeURIComponent(id)}`).join('; ')}`
  const stanceLabel: Record<string, string> = { direct: zh ? '协调' : 'Coordinate', produce: zh ? '研究与产出' : 'Research & produce', review: zh ? '审阅' : 'Review' }

  return <section className="bot-page" data-tour-id="bot-responsibility">
    <header className="science-page-header">
      <div><p className="science-eyebrow"><Link to={projectId ? team : '/bots'} className="inline-flex items-center gap-1"><ArrowLeftIcon aria-hidden="true" />{zh ? '研究团队' : 'Research team'}</Link></p>
        <h1>{bot ? name(bot) : botId}</h1>
        <p>{activeProject ? projectText(activeProject, 'name', language) : (zh ? '选择项目，查看这个 Bot 在项目中的工作。' : 'Choose a project to see this Bot’s work in it.')}</p>
      </div>
    </header>
    <ApiState isLoading={projectsLoading} isError={projectsError} error={projectsQueryError} onRetry={() => void refetchProjects()}>
      {!activeProject ? <div className="science-empty"><BotAvatar id={botId} stance={bot?.stance} /><h2>{zh ? '先选择一个研究项目' : 'Start with a research project'}</h2><p>{zh ? '任务、交接和对话都属于某个项目。' : 'Tasks, handoffs and conversations belong to a project.'}</p><Button type="button" render={<Link to="/projects" />}>{zh ? '查看项目' : 'Browse projects'}<ArrowRightIcon /></Button></div> :
        <div className="bot-workspace-grid">
          <BotRoster projectId={projectId} activeBotId={botId} onAuto={() => { setSessionBot(projectId, null); navigate(`${team}&view=chat`) }} />
          <div className="bot-main">
            <ApiState isLoading={bots.isLoading} isError={bots.isError} error={bots.error} onRetry={() => void bots.refetch()}>
              {bot ? <Tabs value={view} onValueChange={(value) => setParam('view', value === 'chat' ? 'chat' : null)}>
                <div className="bot-selected-header"><BotAvatar id={bot.id} stance={bot.stance} /><div className="min-w-0">
                  <p className="bot-selected-stance">{stanceLabel[bot.stance] ?? bot.stance}</p>
                  <h2>{name(bot)}</h2><p>{bot.summary}</p>
                </div></div>
                <TabsList className="bot-surface-tabs" variant="line" aria-label={zh ? 'Bot 职责页视图' : 'Bot page views'}>
                  <TabsTrigger value="work">{zh ? '职责与工作' : 'Responsibilities & work'}</TabsTrigger>
                  <TabsTrigger value="chat">{zh ? '对话' : 'Conversation'}</TabsTrigger>
                </TabsList>
                <TabsContent value="work">
                  {runId ? <AgentRunDetail key={runId} runId={runId} projectId={projectId} onBack={() => setParam('run', null)} />
                    : <BotWork bot={bot} bots={bots.data ?? []} projectId={projectId} onOpenRun={(id) => setParam('run', id)} onChat={() => setParam('view', 'chat')} />}
                </TabsContent>
                <TabsContent value="chat"><div className="bot-chat-surface"><CopilotChat pageContext={context} externalRoster /></div></TabsContent>
              </Tabs> : <div className="science-empty">
                <h2>{zh ? '名录中没有这个 Bot' : 'This Bot is not in the roster'}</h2>
                <p>{zh ? '它可能已被移出名录；以它身份运行过的任务记录仍会保留。' : 'It may have been retired; tasks that ran as it are still recorded.'}</p>
                <Button type="button" variant="outline" render={<Link to={team} />}>{zh ? '返回研究团队' : 'Back to the research team'}</Button>
              </div>}
            </ApiState>
          </div>
          {bot ? <BotRelations bot={bot} bots={bots.data ?? []} projectId={projectId} /> : null}
        </div>}
    </ApiState>
  </section>
}

function BotWork({ bot, bots, projectId, onOpenRun, onChat }: { bot: CopilotBot; bots: readonly CopilotBot[]; projectId: string; onOpenRun: (id: string) => void; onChat: () => void }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const navigate = useNavigate()
  const readOnly = useCopilotReadOnly()
  const runs = useQuery({ queryKey: ['agent-runs', projectId], queryFn: () => listAgentRuns(projectId), enabled: Boolean(projectId), refetchInterval: (q) => q.state.data?.some(isLive) ? 4000 : false })
  const services = useQuery({ queryKey: ['copilot-task-services'], queryFn: listTaskServices, enabled: Boolean(bot.task_service) })
  const handoffs = useCopilotHandoffs(projectId)
  const botName = zh ? bot.title_zh : bot.title
  const service = services.data?.find((entry) => entry.id === bot.task_service)
  const held: AgentRun[] = runs.data?.filter((run) => run.bot === bot.id) ?? []
  const received = handoffs.data?.filter((handoff) => handoff.to_bot === bot.id) ?? []
  const sent = handoffs.data?.filter((handoff) => handoff.from_bot === bot.id) ?? []
  // Assigning prepares the composer with this owner and opens it. Nothing
  // starts here: the plan, writes and budget are still reviewed there.
  const assign = () => {
    const store = useAppStore.getState()
    const current = store.copilotTaskDrafts[projectId]
    store.setCopilotTaskDraft(projectId, { goal: current?.goal ?? '', maxTurns: current?.maxTurns ?? 24, maxCost: current?.maxCost ?? '', writes: [], bot: bot.id, preview: true })
    navigate(`/bots?project=${encodeURIComponent(projectId)}&view=tasks`)
  }
  const handoffList = (label: string, items: HandoffResponse[], empty: string) => <div role="group" aria-label={label}>
    <h4>{label} · {items.length}</h4>
    {items.length ? <Frame spacing="sm">{items.map((handoff) => <HandoffCard key={handoff.id} handoff={handoff} bots={bots} onSelectOperator={(id) => navigate(botHref(id, projectId))} />)}</Frame>
      : <p className="text-sm text-text-secondary">{empty}</p>}
  </div>

  return <div className="bot-work">
    <section aria-label={zh ? '职责与边界' : 'Mandate and refusals'}>
      <h3>{zh ? '职责与边界' : 'Mandate and refusals'}</h3>
      <p className="text-sm text-text-secondary">{bot.charter}</p>
    </section>
    <section aria-label={zh ? '托管任务' : 'Guided tasks'}>
      <h3>{zh ? '托管任务' : 'Guided tasks'}</h3>
      {bot.task_service ? <div className="space-y-3">
        <p className="text-sm">{service ? (zh ? `负责“${service.title_zh}”：${service.deliverable_zh}` : `Owns “${service.title}”: ${service.deliverable}`) : (zh ? '负责一类托管任务。' : 'Owns a kind of guided task.')}</p>
        <Button type="button" disabled={readOnly} onClick={assign}>{zh ? `给 ${botName} 分派任务` : `Assign a task to ${botName}`}<ArrowRightIcon aria-hidden="true" /></Button>
      </div> : <div className="space-y-3">
        <p className="text-sm text-text-secondary">{zh ? '不承接托管任务，通过对话、交接和委派开展工作。' : 'Takes no guided tasks; works through conversation, handoffs and delegation.'}</p>
        <Button type="button" variant="outline" onClick={onChat}>{zh ? `与 ${botName} 对话` : `Talk to ${botName}`}</Button>
      </div>}
    </section>
    <section aria-label={zh ? '手上的任务' : 'Tasks it holds'}>
      <h3>{zh ? '手上的任务' : 'Tasks it holds'}{runs.data ? ` · ${held.length}` : ''}</h3>
      <ApiState isLoading={runs.isLoading} isError={runs.isError} error={runs.error} onRetry={() => void runs.refetch()}>
        {held.length ? <div className="space-y-2">{held.map((run) => <Button key={run.id} type="button" variant="outline" className="task-delivery h-auto w-full flex-col items-start whitespace-normal text-left" onClick={() => onOpenRun(run.id)}>
          <span className="task-delivery-status">{deliveryLabel(run, zh)}{run.parent_run_id ? (zh ? ' · 受委派' : ' · Delegated') : ''}</span><span>{run.goal}</span>
        </Button>)}</div> : <p className="text-sm text-text-secondary">{zh ? `还没有以 ${botName} 身份运行的任务。` : `No tasks have run as ${botName} yet.`}</p>}
      </ApiState>
    </section>
    <section aria-label={zh ? '交接' : 'Handoffs'}>
      <h3>{zh ? '交接' : 'Handoffs'}</h3>
      <ApiState isLoading={handoffs.isLoading} isError={handoffs.isError} error={handoffs.error} onRetry={() => void handoffs.refetch()}>
        {handoffList(zh ? '交给它的' : 'Received', received, zh ? '还没有人交接给它。' : 'Nothing has been handed to it yet.')}
        {handoffList(zh ? '它交出的' : 'Sent', sent, zh ? '它还没有交接出去。' : 'It has not handed anything on yet.')}
      </ApiState>
    </section>
  </div>
}

function BotRelations({ bot, bots, projectId }: { bot: CopilotBot; bots: readonly CopilotBot[]; projectId: string }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const resolve = (ids: readonly string[] | undefined) => (ids ?? []).flatMap((id) => bots.filter((entry) => entry.id === id))
  const relations: [string, CopilotBot[]][] = [
    [zh ? '交给' : 'Hands off to', successorsOf(bot, bots)],
    [zh ? '由谁复核' : 'Reviewed by', reviewersOf(bot, bots)],
    [zh ? '复核' : 'Reviews', resolve(bot.reviews)],
    [zh ? '调度' : 'Directs', resolve(bot.directs)],
  ]
  const links = relations.flatMap(([label, entries]) => entries.map((entry) => ({ label, entry })))
  const benches = BOT_WORKBENCHES[bot.id] ?? []

  return <aside className="bot-context">
    <p className="science-eyebrow bot-materials-label">{zh ? '协作关系' : 'WORKS WITH'}</p>
    {links.length ? <nav aria-label={zh ? '协作关系' : 'Works with'}>{links.map(({ label, entry }) => <Link key={`${label}:${entry.id}`} to={botHref(entry.id, projectId)} className="bot-relation">
      <span><small>{label}</small>{zh ? entry.title_zh : entry.title}</span><ArrowRightIcon aria-hidden="true" />
    </Link>)}</nav> : <p className="mt-2 text-sm text-text-secondary">{zh ? '没有声明的协作关系。' : 'No declared collaborators.'}</p>}
    {benches.length ? <>
      <p className="science-eyebrow bot-materials-label">{zh ? '使用的工作台' : 'WORKBENCHES'}</p>
      <nav aria-label={zh ? '使用的工作台' : 'Workbenches'}>{benches.map((bench) => <Link key={`${bench.path}:${bench.tab ?? ''}`} to={workbenchHref(bench, projectId)}>{zh ? bench.zh : bench.en}<ArrowRightIcon aria-hidden="true" /></Link>)}</nav>
    </> : null}
  </aside>
}
