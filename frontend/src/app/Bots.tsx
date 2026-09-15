import { useNavigate, useSearchParams, Link } from 'react-router'
import { ArrowRightIcon, GearIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useAppStore } from '../lib/store/appStore'
import { useI18n } from '../lib/i18n'
import { projectText } from '../lib/i18n/projectText'
import { Button } from '../components/ui/Button'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/Tabs'
import { ApiState } from '../components/ui/ApiState'
import { CopilotWorkspace } from '../features/copilot/CopilotWorkspace'
import { Room } from '../features/copilot/Room'
import { CopilotChain } from '../features/copilot/CopilotChain'
import { CopilotSettings } from '../features/copilot/CopilotSettings'
import { useCopilotBots } from '../features/copilot/bots/registry'
import { botHref } from '../features/copilot/bots/workbenches'
import { BotRoster } from '../features/copilot/BotRoster'
import { managesProject, useProjectAccess } from '../lib/hooks/useProjectAccess'
import { currentRole } from '../features/research/jsonHelpers'
import { BotAvatar } from '../features/copilot/BotAvatar'
import { ProjectBriefPanel } from '../features/projects/ProjectBriefPanel'

export function BotsPage() {
  const { projectId } = useProjectContext()
  return <BotProjectWorkspace key={projectId} />
}

function BotProjectWorkspace() {
  const { language } = useI18n()
  const zh = language === 'zh'
  const { activeProject, projectId, projectsLoading, projectsError, projectsQueryError, refetchProjects } = useProjectContext()
  const [search, setSearch] = useSearchParams()
  const navigate = useNavigate()
  const [settings, setSettings] = useState(false)
  // Model configuration is a project manager's decision; researchers and viewers work with the model they are given.
  const access = useProjectAccess(projectId)
  const canConfigure = managesProject(access.data) || currentRole() === 'admin'
  const bots = useCopilotBots()
  const selectedEntities = useAppStore((s) => s.copilotSelectedEntityIds)
  const selectedId = useAppStore((s) => s.copilotSessions[projectId]?.bot ?? null)
  const setBot = useAppStore((s) => s.setCopilotSessionBot)
  const setTaskDraft = useAppStore((s) => s.setCopilotTaskDraft)
  const selected = bots.data?.find((bot) => bot.id === selectedId)
  // `chat` was this page's conversation tab before the room existed. An old
  // link resolves to the room rather than landing silently on the default,
  // because the room contains what that tab used to show.
  const requested = search.get('view') === 'chat' ? 'room' : search.get('view') ?? ''
  const view = ['room', 'tasks', 'handoffs'].includes(requested) ? requested : 'room'
  const selectView = (value: string) => { const next = new URLSearchParams(search); next.set('view', value); setSearch(next) }
  const selectRun = (id: string | null) => {
    const next = new URLSearchParams(search)
    next.set('view', 'tasks')
    if (id) next.set('run', id)
    else next.delete('run')
    setSearch(next)
  }
  const selectBot = (id: string | null) => { setBot(projectId, id); selectView('room') }
  // Addressing someone in the room can prepare a task for them. It prepares
  // only: the composer still reviews the plan, the writes and the budget,
  // which is where starting a run has always been approved.
  const assignFromRoom = (goal: string, bot: string, service: string) => {
    const current = useAppStore.getState().copilotTaskDrafts[projectId]
    setTaskDraft(projectId, {
      goal,
      maxTurns: current?.maxTurns ?? 24,
      maxCost: current?.maxCost ?? '',
      writes: [],
      bot,
      service,
      preview: true,
    })
    selectView('tasks')
  }
  const context = `route=/bots; project_id=${projectId}; name=${activeProject?.name ?? ''}; query=${search.toString()}; ${selectedEntities.map((id) => `entity=${encodeURIComponent(id)}`).join('; ')}`
  const name = (bot: { title: string; title_zh: string }) => zh ? bot.title_zh : bot.title

  return <section className="bot-page" data-tour-id="bot-workspace">
    <header className="science-page-header">
      <div><p className="science-eyebrow">{zh ? 'AI FOR SCIENCE / 研究协作' : 'AI FOR SCIENCE / COLLABORATION'}</p>
        <h1>{zh ? '研究团队' : 'Research team'}</h1>
        <p>{activeProject ? projectText(activeProject, 'name', language) : (zh ? '选择项目，让对话有上下文。' : 'Choose a project to give the conversation context.')}</p>
      </div>
      {projectId && canConfigure ? <Button type="button" variant="outline" onClick={() => setSettings(!settings)} aria-expanded={settings}><GearIcon />{zh ? '模型设置' : 'Model settings'}</Button> : null}
    </header>
    <ApiState isLoading={projectsLoading} isError={projectsError} error={projectsQueryError} onRetry={() => void refetchProjects()}>
      {!activeProject ? <div className="science-empty"><BotAvatar id="director" stance="direct" /><h2>{zh ? '先选择一个研究项目' : 'Start with a research project'}</h2><p>{zh ? '任务、证据和对话会保存在同一个项目里。' : 'Tasks, evidence and conversations stay together in the same project.'}</p><Button type="button" render={<Link to="/projects" />}>{zh ? '查看项目' : 'Browse projects'}<ArrowRightIcon /></Button></div> : <>
        {settings && canConfigure ? <div className="mb-6 rounded-lg border border-border p-4"><CopilotSettings /></div> : null}
        <div className="bot-workspace-grid">
          <BotRoster projectId={projectId} autoActive={view === 'chat' && !selectedId} onAuto={() => selectBot(null)} />
          <div className="bot-main">
            <Tabs value={view} onValueChange={selectView}>
              <TabsList className="bot-surface-tabs" variant="line" aria-label={zh ? '研究团队视图' : 'Research team views'}>
                <TabsTrigger value="room">{zh ? '研究室' : 'Research room'}</TabsTrigger>
                <TabsTrigger value="tasks">{zh ? '任务与交付' : 'Tasks & deliverables'}</TabsTrigger>
                <TabsTrigger value="handoffs">{zh ? 'Bot 交接' : 'Bot handoffs'}</TabsTrigger>
              </TabsList>
              <TabsContent value="tasks"><CopilotWorkspace pageContext={context} ignoreDraft rememberDraft openRunId={search.get('run')} onRunChange={selectRun} /></TabsContent>
              <TabsContent value="room">
                {selected ? <div className="bot-selected-header"><BotAvatar id={selected.id} stance={selected.stance} /><div><h2>{name(selected)}</h2><p>{selected.summary}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs"><Button type="button" size="sm" variant="outline" render={<Link to={botHref(selected.id, projectId)} />}>{zh ? '查看职责页' : 'Open responsibility page'}</Button><Button type="button" size="sm" variant="ghost" onClick={() => setBot(projectId, null)}>{zh ? '改为自动匹配' : 'Switch to auto-match'}</Button></div>
                </div></div> : null}
                <Room
                  pageContext={context}
                  onOpenRun={selectRun}
                  onOpenBot={(id: string) => navigate(botHref(id, projectId))}
                  onAssign={assignFromRoom}
                />
              </TabsContent>
              <TabsContent value="handoffs"><CopilotChain onSelectOperator={(id) => navigate(botHref(id, projectId))} /></TabsContent>
            </Tabs>
          </div>
          <aside className="bot-context"><ProjectBriefPanel project={activeProject} compact />
            <p className="science-eyebrow bot-materials-label">{zh ? '项目资料' : 'PROJECT MATERIALS'}</p>
            <nav aria-label={zh ? '项目资料' : 'Project materials'}>{[
              ['evidence', zh ? '文献与证据' : 'Literature & evidence'], ['structures', zh ? '结构对照' : 'Structure comparison'], ['methods', zh ? '实验方案' : 'Experiment plan'], ['timeline', zh ? '决策记录' : 'Decision record'],
            ].map(([tab, label]) => <Link key={tab} to={`/research?project=${encodeURIComponent(projectId)}&tab=${tab}`}>{label}<ArrowRightIcon /></Link>)}</nav>
          </aside>
        </div>
      </>}
    </ApiState>
  </section>
}
