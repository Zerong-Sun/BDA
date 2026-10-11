import { useNavigate, useSearchParams, Link } from 'react-router'
import { ArrowRightIcon, GearIcon } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
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
import { ProceduralSkillCatalog } from '../features/copilot/ProceduralSkills'
import { useCopilotBots } from '../features/copilot/bots/registry'
import { botDisplayText } from '../features/copilot/bots/displayText'
import { botHref } from '../features/copilot/bots/workbenches'
import { BotRoster } from '../features/copilot/BotRoster'
import { managesProject, useProjectAccess } from '../lib/hooks/useProjectAccess'
import { currentRole } from '../features/research/jsonHelpers'
import { BotAvatar } from '../features/copilot/BotAvatar'
import { ProjectBriefPanel } from '../features/projects/ProjectBriefPanel'
import { normalizeResearchTab } from '../features/research/researchUi'

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
  const savedTaskDraft = useAppStore((s) => s.copilotTaskDrafts[projectId])
  const requestedService = search.get('service') === 'literature' ? 'literature' : undefined
  const incomingGoal = requestedService && search.get('draft_project') === projectId
    ? (search.get('draft') ?? '').trim().slice(0, 4000) : ''
  const clearIncomingDraft = (keepCurrent = false) => {
    const next = new URLSearchParams(search)
    next.delete('draft')
    next.delete('draft_project')
    next.delete('run')
    if (keepCurrent) next.delete('service')
    next.set('view', 'tasks')
    setSearch(next, { replace: true })
  }
  const acceptIncomingDraft = () => {
    setTaskDraft(projectId, { goal: incomingGoal, bot: null, service: 'literature', preview: true, writes: [], maxTurns: 24, maxCost: '' })
    clearIncomingDraft()
  }
  useEffect(() => {
    if (!projectId || !incomingGoal || savedTaskDraft?.goal.trim()) return
    setTaskDraft(projectId, { goal: incomingGoal, bot: null, service: 'literature', preview: true, writes: [], maxTurns: 24, maxCost: '' })
    const next = new URLSearchParams(search)
    next.delete('draft')
    next.delete('draft_project')
    next.delete('run')
    next.set('view', 'tasks')
    setSearch(next, { replace: true })
  }, [incomingGoal, projectId, savedTaskDraft?.goal, search, setSearch, setTaskDraft])
  const selected = bots.data?.find((bot) => bot.id === selectedId)
  // `chat` was this page's conversation tab before the room existed. An old
  // link resolves to the room rather than landing silently on the default,
  // because the room contains what that tab used to show.
  const requested = search.get('view') === 'chat' ? 'room' : search.get('view') ?? ''
  const view = ['room', 'tasks', 'handoffs', 'skills'].includes(requested) ? requested : 'room'
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
          <BotRoster projectId={projectId} autoActive={view === 'room' && !selectedId} onAuto={() => selectBot(null)} />
          <div className="bot-main">
            <Tabs value={view} onValueChange={selectView}>
              <TabsList className="bot-surface-tabs" variant="line" aria-label={zh ? '研究团队视图' : 'Research team views'}>
                <TabsTrigger value="room">{zh ? '研究室' : 'Research room'}</TabsTrigger>
                <TabsTrigger value="tasks">{zh ? '任务与交付' : 'Tasks & deliverables'}</TabsTrigger>
                <TabsTrigger value="handoffs">{zh ? 'Bot 交接' : 'Bot handoffs'}</TabsTrigger>
                <TabsTrigger value="skills">{zh ? '科学方法' : 'Scientific methods'}</TabsTrigger>
              </TabsList>
              <TabsContent value="tasks">
                {search.get('from') ? <Button type="button" variant="link" render={<Link to={`/research?${new URLSearchParams({ project: projectId, tab: normalizeResearchTab(search.get('from')) })}`} />}>{zh ? '返回研究资料' : 'Back to research materials'}</Button> : null}
                {incomingGoal && savedTaskDraft?.goal.trim() ? <section className="m-4 grid gap-3 border border-border p-4" aria-label={zh ? '传入的文献任务草稿' : 'Incoming literature task draft'}><p className="text-sm">{zh ? '已有未提交的任务草稿。选择保留，或改用这份文献调研草稿；此步骤不会启动任务。' : 'An unsent task draft already exists. Keep it or replace it with this literature draft; this does not start a task.'}</p><p className="whitespace-pre-wrap text-sm text-muted-foreground">{incomingGoal}</p><div className="flex flex-wrap gap-2"><Button type="button" onClick={acceptIncomingDraft}>{zh ? '使用文献调研草稿' : 'Use literature draft'}</Button><Button type="button" variant="outline" onClick={() => clearIncomingDraft(true)}>{zh ? '保留当前草稿' : 'Keep current draft'}</Button></div></section> : null}
                <CopilotWorkspace pageContext={context} initialService={requestedService} ignoreDraft rememberDraft openRunId={search.get('run')} onRunChange={selectRun} />
              </TabsContent>
              <TabsContent value="room">
                {selected ? <div className="bot-selected-header"><BotAvatar id={selected.id} stance={selected.stance} /><div><h2>{name(selected)}</h2><p>{botDisplayText(selected, language).summary}</p>
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
              <TabsContent value="skills"><ProceduralSkillCatalog /></TabsContent>
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
