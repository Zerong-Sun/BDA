import { useEffect } from 'react'
import { Navigate, useSearchParams } from 'react-router'
import { ChatCircleIcon } from '@phosphor-icons/react'
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

export function ResearchPage() {
  const { language, t } = useI18n()
  const [searchParams, setSearchParams] = useSearchParams()
  const rawTab = searchParams.get('tab')
  const { projectId } = useProjectContext()
  const setCopilotDraft = useAppStore((state) => state.setCopilotDraft)
  const setCopilotOpen = useAppStore((state) => state.setCopilotOpen)
  const setCopilotSelectedEntityIds = useAppStore((state) => state.setCopilotSelectedEntityIds)
  const tab = normalizeResearchTab(rawTab)
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
    <div className="mx-auto max-w-[1180px]">
      <Tabs
        value={tab}
        onValueChange={(value) => selectTab(value as ResearchTab)}
        data-tour-id="research-tabs"
      >
        <header className="mb-5 border-b border-border-soft pb-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-accent">{t.research.page.eyebrow}</p>
            <h1 className="text-xl font-semibold text-text-primary">{t.research.page.title}</h1>
          </div>
          {projectId ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => {
                setCopilotSelectedEntityIds([])
                setCopilotDraft(languagePrompt(tab, tabConfig[tab].label, language))
                setCopilotOpen(true)
              }}
            >
              <ChatCircleIcon aria-hidden="true" />
              {t.copilot.drawer.toggleLabel}: {tabConfig[tab].label}
            </Button>
          ) : null}
          <TabsList
            aria-label={t.research.page.tabsLabel}
            variant="line"
            className="mt-4 grid !h-auto w-full grid-cols-1 gap-1 sm:grid-cols-2 xl:grid-cols-6"
          >
            {RESEARCH_TABS.map((item, index) => (
              <TabsTrigger
                key={item}
                value={item}
                aria-label={tabConfig[item].label}
                className="h-auto min-w-0 justify-start px-3 py-2 text-left"
              >
                <span aria-hidden="true" className="text-[10px] font-semibold text-primary">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <span className="truncate">{tabConfig[item].label}</span>
              </TabsTrigger>
            ))}
          </TabsList>
        </header>
        <TabsContent value={tab}>
          {!projectId ? (
            <Frame>
              <FramePanel>
                <Alert variant="info">
                  <AlertDescription>{t.research.projectNotice}</AlertDescription>
                </Alert>
              </FramePanel>
            </Frame>
          ) : tab === 'goals' ? (
            <Frame>
              <FramePanel>
                <div data-tour-id="research-goals"><ResearchGoalsPanel projectId={projectId} /></div>
              </FramePanel>
            </Frame>
          ) : tab === 'timeline' ? (
            <div data-tour-id="research-timeline"><ProjectTimeline projectId={projectId} /></div>
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
