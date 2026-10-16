import { useEffect } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router'
import { ChatCircleIcon } from '@phosphor-icons/react'
import { NextStep } from '../components/ui/NextStep'
import { Button } from '../components/ui/Button'
import { Disclosure } from '../components/ui/Disclosure'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/Tabs'
import { Alert, AlertDescription } from '../components/reui/alert'
import { Frame, FramePanel } from '../components/reui/frame'
import { ResearchWorkspacePanel } from '../features/research/ResearchWorkspacePanel'
import { ResearchGoalsPanel } from '../features/research/ResearchGoalsPanel'
import { ProjectResearchOverview } from '../features/research/ProjectResearchOverview'
import { ResearchDecisionCenter } from '../features/research/ResearchDecisionCenter'
import { ProjectBriefPanel } from '../features/projects/ProjectBriefPanel'
import { ProjectTimeline } from '../features/timeline/ProjectTimeline'
import { normalizeResearchTab, RESEARCH_TABS, type ResearchTab } from '../features/research/researchUi'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useI18n } from '../lib/i18n'
import { useAppStore, type Language } from '../lib/store/appStore'
import { isDemoProject } from '../features/tour'

export function ResearchPage() {
  const { language, t } = useI18n()
  const [searchParams, setSearchParams] = useSearchParams()
  const rawTab = searchParams.get('tab')
  const { projectId, activeProject } = useProjectContext()
  const retrospective = ['archived', 'completed'].includes(activeProject?.status ?? '')
  const isPd1Demo = Boolean(activeProject && isDemoProject(activeProject))
  const setCopilotDraft = useAppStore((state) => state.setCopilotDraft)
  const setCopilotOpen = useAppStore((state) => state.setCopilotOpen)
  const setCopilotSelectedEntityIds = useAppStore((state) => state.setCopilotSelectedEntityIds)
  const tab = rawTab ? normalizeResearchTab(rawTab) : 'goals'
  const group = tab === 'references' || tab === 'structures' || tab === 'data' ? 'evidence' : tab
  const groups = [
    { key: 'goals', label: retrospective ? (language === 'zh' ? '项目总结' : 'Project summary') : (language === 'zh' ? '目标与问题' : 'Goals & questions') },
    { key: 'evidence', label: language === 'zh' ? '文献与证据' : 'Literature & evidence' },
    { key: 'methods', label: language === 'zh' ? '实验方案' : 'Experiment plan' },
    { key: 'timeline', label: language === 'zh' ? '决策记录' : 'Decision record' },
  ] as const
  useEffect(() => {
    if (rawTab === 'campaigns' || rawTab === tab) return
    const next = new URLSearchParams(searchParams)
    next.set('tab', tab)
    setSearchParams(next, { replace: true })
  }, [rawTab, searchParams, setSearchParams, tab])
  if (rawTab === 'campaigns') {
    const project = searchParams.get('project')
    return <Navigate replace to={`/projects?view=campaigns${project ? `&project=${encodeURIComponent(project)}` : ''}`} />
  }
  const selectTab = (nextTab: ResearchTab) => {
    const next = new URLSearchParams(searchParams)
    next.set('tab', nextTab)
    setSearchParams(next)
  }
  const tabConfig: Record<ResearchTab, { label: string }> = {
    goals: { label: groups[0].label },
    evidence: { label: t.research.workspace.tabEvidence },
    references: { label: t.research.workspace.tabReferences },
    structures: { label: t.research.workspace.tabStructures },
    data: { label: t.research.workspace.tabData },
    methods: { label: t.research.workspace.tabMethods },
    timeline: { label: t.research.workspace.tabTimeline },
  }
  return (
    <div className={`research-page mx-auto max-w-[1360px]${tab === 'structures' ? ' research-page--structures' : ''}`}>
      <Tabs
        value={group}
        onValueChange={(value) => selectTab(value as ResearchTab)}
        data-tour-id="research-tabs"
      >
        <header className="research-page-heading mb-5 border-b border-border-soft pb-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-accent">{t.research.page.eyebrow}</p>
            <h1 className="mt-2 text-3xl font-medium text-text-primary">{t.research.page.title}</h1>
          </div>
          {isPd1Demo ? (
            <Alert className="mt-3" variant="warning">
              <AlertDescription>
                {language === 'zh'
                  ? '公开演示项目 · 候选指标为合成数据，文献与结构保留来源。'
                  : 'Public demo · Candidate metrics are synthetic; literature and structures retain their sources.'}
              </AlertDescription>
            </Alert>
          ) : null}
          {projectId ? (
            <div className="science-route-links">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setCopilotSelectedEntityIds([])
                setCopilotDraft(languagePrompt(tab, tabConfig[tab].label, language))
                setCopilotOpen(true)
              }}
            >
              <ChatCircleIcon aria-hidden="true" />
              {language === 'zh' ? `就「${tabConfig[tab].label}」提问` : `Ask about ${tabConfig[tab].label}`}
            </Button>
            </div>
          ) : null}
          <TabsList
            aria-label={t.research.page.tabsLabel}
            variant="line"
            className="mt-4 grid !h-auto w-full grid-cols-1 gap-1 sm:grid-cols-2 xl:grid-cols-4"
          >
            {groups.map((item) => (
              <TabsTrigger key={item.key} value={item.key} aria-label={item.label} className="h-auto justify-start px-3 py-2">
                {item.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </header>
        {group === 'evidence' ? <nav className="mb-4 flex flex-wrap gap-2" aria-label={language === 'zh' ? '证据资料类型' : 'Evidence categories'}>
          {RESEARCH_TABS.filter((item) => ['evidence', 'references', 'structures', 'data'].includes(item)).map((item) => (
            <Button type="button" key={item} variant={tab === item ? 'secondary' : 'ghost'} size="sm" onClick={() => selectTab(item)} aria-pressed={tab === item}>{tabConfig[item].label}</Button>
          ))}
        </nav> : null}
        {projectId && !retrospective && (group === 'methods' || tab === 'evidence' || tab === 'references') ? <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          {group === 'methods' ? <Button type="button" render={<Link to={`/workflow?project=${encodeURIComponent(projectId)}`} />}>{language === 'zh' ? '准备计算方案' : 'Prepare workflow'}</Button> : null}
          {group === 'evidence' ? <Button type="button" render={<Link to={literatureTaskLink(projectId, tab, language)} />}>{language === 'zh' ? '准备 AI 文献调研任务' : 'Prepare AI literature task'}</Button> : null}
        </div> : null}
        <TabsContent value={group}>
          {!projectId ? (
            <Frame>
              <FramePanel>
                <Alert variant="info">
                  <AlertDescription>{t.research.projectNotice}</AlertDescription>
                </Alert>
              </FramePanel>
            </Frame>
          ) : tab === 'goals' ? (
            <>
            {activeProject && retrospective ? <ProjectResearchOverview key={projectId} project={activeProject} /> : activeProject ? <Disclosure key={`brief-${projectId}-${searchParams.get('brief')}`} title={language === 'zh' ? '研究背景与任务书' : 'Research context'} defaultOpen={searchParams.get('brief') === '1'}>
              <ProjectBriefPanel project={activeProject} />
            </Disclosure> : null}
            {retrospective ? <Disclosure title={language === 'zh' ? '结构化问题与决策定义' : 'Structured questions and decision definitions'}><ResearchDecisionCenter key={`decision-${projectId}`} projectId={projectId} /></Disclosure> : <ResearchDecisionCenter key={`decision-${projectId}`} projectId={projectId} />}
            <Frame>
              <FramePanel>
                <div data-tour-id="research-goals"><Disclosure key={projectId} title={language === 'zh' ? '管理问题与目标树' : 'Manage questions and goal tree'}><ResearchGoalsPanel key={projectId} projectId={projectId} /></Disclosure></div>
              </FramePanel>
            </Frame>
            </>
          ) : tab === 'timeline' ? (
            <div data-tour-id="research-timeline"><div data-tour-id="timeline-page"><ProjectTimeline projectId={projectId} hasPrompt={Boolean(activeProject?.prompt)} /></div></div>
          ) : <div data-tour-id="research-workspace"><ResearchWorkspacePanel view={tab} /></div>}
        </TabsContent>
      </Tabs>
      {projectId && !retrospective ? <NextStep stage="research" /> : null}
    </div>
  )
}

function literatureTaskLink(projectId: string, tab: ResearchTab, language: Language) {
  const draft = language === 'zh'
    ? '请为当前项目检索文献。读取项目任务书，将主题转换为英文检索词，读取可获取的正文或摘要，整理带引用的待审核研究笔记，列出信息缺口和实验方案建议。只准备草案，不审核结论、不提交计算任务。请使用中文汇报。'
    : 'Research this project: read its brief, search literature, read available full text or abstracts, and prepare cited pending-review knowledge notes. Identify evidence gaps and propose experiments. Prepare drafts only; do not approve conclusions or submit compute jobs.'
  return `/bots?${new URLSearchParams({ project: projectId, view: 'tasks', service: 'literature', draft, draft_project: projectId, from: tab })}`
}

function languagePrompt(tab: ResearchTab, label: string, language: Language) {
  return language === 'zh'
    ? `请仅依据项目 Research workspace 分析当前“${label}”视图（${tab}）。引用实体或参考文献 ID，区分证据状态，并明确指出信息缺口。`
    : `Analyze the current Research ${label} (${tab}) using only project workspace evidence. Cite entity/reference IDs, distinguish evidence status, and state any gaps.`
}
