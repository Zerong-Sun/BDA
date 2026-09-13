import { useSearchParams, Link } from 'react-router'
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
import { CopilotChat } from '../features/copilot/CopilotChat'
import { CopilotChain } from '../features/copilot/CopilotChain'
import { CopilotSettings } from '../features/copilot/CopilotSettings'
import { byStance, successorsOf, useCopilotBots } from '../features/copilot/bots/registry'
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
  const [settings, setSettings] = useState(false)
  const bots = useCopilotBots()
  const selectedEntities = useAppStore((s) => s.copilotSelectedEntityIds)
  const selectedId = useAppStore((s) => s.copilotSessions[projectId]?.bot ?? null)
  const setBot = useAppStore((s) => s.setCopilotSessionBot)
  const selected = bots.data?.find((bot) => bot.id === selectedId)
  const view = ['tasks', 'chat', 'handoffs'].includes(search.get('view') ?? '') ? search.get('view')! : 'tasks'
  const selectView = (value: string) => { const next = new URLSearchParams(search); next.set('view', value); setSearch(next) }
  const selectBot = (id: string | null) => { setBot(projectId, id); selectView('chat') }
  const context = `route=/bots; project_id=${projectId}; name=${activeProject?.name ?? ''}; query=${search.toString()}; ${selectedEntities.map((id) => `entity=${encodeURIComponent(id)}`).join('; ')}`
  const name = (bot: { title: string; title_zh: string }) => zh ? bot.title_zh : bot.title

  return <section className="bot-page" data-tour-id="bot-workspace">
    <header className="science-page-header">
      <div><p className="science-eyebrow">{zh ? 'AI FOR SCIENCE / 研究协作' : 'AI FOR SCIENCE / COLLABORATION'}</p>
        <h1>{zh ? '你的 Bot 工作区' : 'Your Bot workspace'}</h1>
        <p>{activeProject ? projectText(activeProject, 'name', language) : (zh ? '选择项目，让对话有上下文。' : 'Choose a project to give the conversation context.')}</p>
      </div>
      {projectId ? <Button type="button" variant="outline" onClick={() => setSettings(!settings)} aria-expanded={settings}><GearIcon />{zh ? '模型设置' : 'Model settings'}</Button> : null}
    </header>
    <ApiState isLoading={projectsLoading} isError={projectsError} error={projectsQueryError} onRetry={() => void refetchProjects()}>
      {!activeProject ? <div className="science-empty"><BotAvatar id="director" stance="direct" /><h2>{zh ? '先选择一个研究项目' : 'Start with a research project'}</h2><p>{zh ? '任务、证据和对话会保存在同一个项目里。' : 'Tasks, evidence and conversations stay together in the same project.'}</p><Button type="button" render={<Link to="/projects" />}>{zh ? '查看项目' : 'Browse projects'}<ArrowRightIcon /></Button></div> : <>
        {settings ? <div className="mb-6 rounded-lg border border-border p-4"><CopilotSettings /></div> : null}
        <div className="bot-workspace-grid">
          <aside className="bot-roster" aria-label={zh ? '研究 Bot 名录' : 'Research Bot roster'}>
            <h2>{zh ? '研究伙伴' : 'Research team'}</h2>
            <p className="mb-4 text-xs text-text-muted">{zh ? '选择职责，开始对话。' : 'Choose a responsibility to start a conversation.'}</p>
            <Button variant="ghost" className="bot-roster-item" type="button" aria-pressed={view === 'chat' && !selectedId} onClick={() => selectBot(null)}><BotAvatar id="auto" stance="direct" /><span><strong>{zh ? '自动匹配' : 'Auto-match'}</strong><small>{zh ? '根据问题选择 Bot' : 'Match the question to a Bot'}</small></span></Button>
            <ApiState isLoading={bots.isLoading} isError={bots.isError} error={bots.error} onRetry={() => void bots.refetch()}>
              {byStance(bots.data ?? []).map((group) => <div key={group.stance}>
                <p className="bot-stance">{({ direct: zh ? '协调' : 'Coordinate', produce: zh ? '研究与产出' : 'Research & produce', review: zh ? '审阅' : 'Review' })[group.stance]}</p>
                {group.bots.map((bot) => <Button variant="ghost" type="button" className="bot-roster-item" key={bot.id} aria-pressed={view === 'chat' && selectedId === bot.id} onClick={() => selectBot(bot.id)}><BotAvatar id={bot.id} stance={bot.stance} /><span><strong>{name(bot)}</strong><small>{bot.id}</small></span></Button>)}
              </div>)}
              {bots.data?.length === 0 ? <p className="text-sm text-text-secondary">{zh ? '暂无可用 Bot。可在模型设置中检查配置。' : 'No Bots available. Check model settings.'}</p> : null}
            </ApiState>
          </aside>
          <div className="bot-main">
            <Tabs value={view} onValueChange={selectView}>
              <TabsList className="bot-surface-tabs" variant="line" aria-label={zh ? 'Bot 工作区视图' : 'Bot workspace views'}>
                <TabsTrigger value="tasks">{zh ? '任务与交付' : 'Tasks & deliverables'}</TabsTrigger>
                <TabsTrigger value="chat">{zh ? '对话' : 'Conversation'}</TabsTrigger>
                <TabsTrigger value="handoffs">{zh ? 'Bot 交接' : 'Bot handoffs'}</TabsTrigger>
              </TabsList>
              <TabsContent value="tasks"><CopilotWorkspace pageContext={context} ignoreDraft /></TabsContent>
              <TabsContent value="chat">
                {selected ? <div className="bot-selected-header"><BotAvatar id={selected.id} stance={selected.stance} /><div><h2>{name(selected)}</h2><p>{selected.summary}</p>
                  {successorsOf(selected, bots.data ?? []).length ? <div className="mt-2 flex flex-wrap items-center gap-2 text-xs"><span>{zh ? '可交接给' : 'Can hand off to'}</span>{successorsOf(selected, bots.data ?? []).map((bot) => <Button type="button" size="sm" variant="link" key={bot.id} onClick={() => selectBot(bot.id)}>{name(bot)}<ArrowRightIcon /></Button>)}</div> : null}
                </div></div> : null}
                <div className="bot-chat-surface"><CopilotChat pageContext={context} externalRoster /></div>
              </TabsContent>
              <TabsContent value="handoffs"><CopilotChain onSelectOperator={selectBot} /></TabsContent>
            </Tabs>
          </div>
          <aside className="bot-context"><ProjectBriefPanel project={activeProject} compact />
            <nav aria-label={zh ? '项目资料' : 'Project materials'}>{[
              ['evidence', zh ? '文献与证据' : 'Literature & evidence'], ['structures', zh ? '结构对照' : 'Structure comparison'], ['methods', zh ? '实验方案' : 'Experiment plan'], ['timeline', zh ? '决策记录' : 'Decision record'],
            ].map(([tab, label]) => <Link key={tab} to={`/research?project=${encodeURIComponent(projectId)}&tab=${tab}`}>{label}<ArrowRightIcon /></Link>)}</nav>
          </aside>
        </div>
      </>}
    </ApiState>
  </section>
}
