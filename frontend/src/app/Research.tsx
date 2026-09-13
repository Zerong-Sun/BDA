import { useEffect, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router'
import { ChatCircleIcon } from '@phosphor-icons/react'
import { CopilotWorkspace } from '../features/copilot/CopilotWorkspace'
import { NextStep } from '../components/ui/NextStep'
import { Button } from '../components/ui/Button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/Tabs'
import { Alert, AlertDescription } from '../components/reui/alert'
import { Frame, FramePanel } from '../components/reui/frame'
import { ResearchWorkspacePanel } from '../features/research/ResearchWorkspacePanel'
import { ResearchGoalsPanel } from '../features/research/ResearchGoalsPanel'
import { ProjectTimeline } from '../features/timeline/ProjectTimeline'
import { normalizeResearchTab, RESEARCH_TABS, type ResearchTab } from '../features/research/researchUi'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useI18n } from '../lib/i18n'
import { useAppStore, type Language } from '../lib/store/appStore'
import { isDemoProject } from '../features/tour'
import { ProjectBriefPanel } from '../features/projects/ProjectBriefPanel'
import { projectText } from '../lib/i18n/projectText'

export function ResearchPage() {
  const { language, t } = useI18n()
  const [searchParams, setSearchParams] = useSearchParams()
  const [researchAgentOpen, setResearchAgentOpen] = useState(false)
  const rawTab = searchParams.get('tab')
  const { projectId, activeProject } = useProjectContext()
  const isPd1Demo = Boolean(activeProject && isDemoProject(activeProject))
  const setCopilotDraft = useAppStore((state) => state.setCopilotDraft)
  const setCopilotOpen = useAppStore((state) => state.setCopilotOpen)
  const setCopilotSelectedEntityIds = useAppStore((state) => state.setCopilotSelectedEntityIds)
  const tab = rawTab ? normalizeResearchTab(rawTab) : 'goals'
  const group = tab === 'references' || tab === 'structures' || tab === 'data' ? 'evidence' : tab
  const groups = [
    { key: 'goals', label: language === 'zh' ? '目标与问题' : 'Goals & questions' },
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
    setSearchParams(next, { replace: true })
  }
  const tabConfig: Record<ResearchTab, { label: string }> = {
    goals: { label: t.research.goals.title },
    evidence: { label: t.research.workspace.tabEvidence },
    references: { label: t.research.workspace.tabReferences },
    structures: { label: t.research.workspace.tabStructures },
    data: { label: t.research.workspace.tabData },
    methods: { label: t.research.workspace.tabMethods },
    timeline: { label: t.research.workspace.tabTimeline },
  }
  return (
    <div className="research-page mx-auto max-w-[1360px]">
      <Tabs
        value={group}
        onValueChange={(value) => selectTab(value as ResearchTab)}
        data-tour-id="research-tabs"
      >
        <header className="mb-5 border-b border-border-soft pb-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-accent">{t.research.page.eyebrow}</p>
            <h1 className="mt-2 text-3xl font-medium text-text-primary">{activeProject ? projectText(activeProject, 'name', language) : t.research.page.title}</h1>
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
            <Button type="button" render={<Link to={`/bots?project=${encodeURIComponent(projectId)}`} />}>{language === 'zh' ? '进入 Bot 工作区' : 'Open Bot workspace'}</Button>
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
              {t.copilot.drawer.toggleLabel}: {tabConfig[tab].label}
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
        {projectId && (group === 'methods' || group === 'evidence') ? <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          {group === 'methods' ? <Button type="button" render={<Link to={`/workflow?project=${encodeURIComponent(projectId)}`} />}>{language === 'zh' ? '准备计算方案' : 'Prepare workflow'}</Button> : null}
          {group === 'evidence' ? <Button type="button" onClick={() => setResearchAgentOpen(!researchAgentOpen)} aria-expanded={researchAgentOpen}>{language === 'zh' ? 'AI 辅助文献调研' : 'Research with AI'}</Button> : null}
        </div> : null}
        {projectId && group === 'evidence' && researchAgentOpen ? <CopilotWorkspace key={projectId} initialService="literature" initialGoal={language === 'zh'
          ? '请为当前项目检索文献。读取项目任务书，将主题转换为英文检索词，调用文献检索并等待完成，读取可获取的正文或摘要，保存带引用的待审核研究笔记，列出信息缺口和实验方案建议。只保存草案，不审核结论、不提交计算任务。请使用中文汇报。'
          : 'Research this project: read its brief, search literature, wait for retrieval, read available full text or abstracts, and save cited pending-review knowledge notes. Identify evidence gaps and propose experiments. Save drafts only; do not approve conclusions or submit compute jobs.'} /> : null}
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
            {activeProject ? <ProjectBriefPanel project={activeProject} /> : null}
            <Frame>
              <FramePanel>
                <div data-tour-id="research-goals"><ResearchGoalsPanel key={projectId} projectId={projectId} /></div>
              </FramePanel>
            </Frame>
            </>
          ) : tab === 'timeline' ? (
            <div data-tour-id="research-timeline"><ProjectTimeline projectId={projectId} hasPrompt={Boolean(activeProject?.prompt)} /></div>
          ) : <div data-tour-id="research-workspace"><ResearchWorkspacePanel view={tab} /></div>}
        </TabsContent>
      </Tabs>
      {projectId ? <NextStep stage="research" /> : null}
    </div>
  )
}

function languagePrompt(tab: ResearchTab, label: string, language: Language) {
  return language === 'zh'
    ? `请仅依据项目 Research workspace 分析当前“${label}”视图（${tab}）。引用实体或参考文献 ID，区分证据状态，并明确指出信息缺口。`
    : `Analyze the current Research ${label} (${tab}) using only project workspace evidence. Cite entity/reference IDs, distinguish evidence status, and state any gaps.`
}
