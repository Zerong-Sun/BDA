import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { PlayCircle, X } from '@phosphor-icons/react'
import { useQuery } from '@tanstack/react-query'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/reui/alert'
import { AppFrame } from '@/components/ui/AppFrame'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { getProjectOverview } from '../lib/api/projects'
import { useDeleteProjectLifecycle } from '../lib/hooks/useDeleteProjectLifecycle'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useAppStore } from '../lib/store/appStore'
import { useI18n } from '../lib/i18n'
import { PageHead } from '../components/ui/PageHead'
import { ApiState } from '../components/ui/ApiState'
import { OverviewCards } from '../features/experiments/OverviewCards'
import { DesignPromptCard } from '../features/experiments/DesignPromptCard'
import { ActiveProjectPanel } from '../features/experiments/ActiveProjectPanel'
import { WorkflowProgress } from '../features/experiments/WorkflowProgress'
import { ProjectLibrary } from '../features/experiments/ProjectLibrary'
import { ManageProjectDrawer } from '../features/experiments/ManageProjectDrawer'
import { CampaignPanel } from '../features/research/CampaignPanel'
import { findDemoProject, isDemoProject } from '../features/tour'

export function ExperimentsPage() {
  const { t, format, language } = useI18n()
  const setCopilotOpen = useAppStore((s) => s.setCopilotOpen)
  const setAppMode = useAppStore((s) => s.setAppMode)
  const appMode = useAppStore((s) => s.appMode)
  const tourState = useAppStore((s) => s.tourState)
  const startTour = useAppStore((s) => s.startTour)
  const resumeTour = useAppStore((s) => s.resumeTour)
  const [showIntro, setShowIntro] = useState(() => localStorage.getItem('bda_intro_dismissed') !== 'true')
  const [manageOpen, setManageOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [demoUnavailable, setDemoUnavailable] = useState(false)
  const { visibleProjects, projectId, setProjectId, activeProject, refetchProjects } = useProjectContext()
  const projectDelete = useDeleteProjectLifecycle()
  const [searchParams] = useSearchParams()
  const showCampaigns = searchParams.get('view') === 'campaigns'

  const openCreate = () => {
    setCreateOpen(true)
    setManageOpen(true)
  }

  const exploreDemo = () => {
    const demo = findDemoProject(visibleProjects)
    if (!demo) {
      setDemoUnavailable(true)
      return
    }
    setDemoUnavailable(false)
    setAppMode('demo')
    setProjectId(demo.id)
    if (tourState.status === 'paused') resumeTour()
    else if (tourState.status !== 'active') startTour('projects')
  }

  const { data: overview, isLoading: overviewLoading, isError: overviewError, error: overviewQueryError, refetch } =
    useQuery({
      queryKey: ['project-overview', projectId],
      queryFn: () => getProjectOverview(projectId),
      enabled: Boolean(projectId),
    })

  const query = projectId ? `?project=${encodeURIComponent(projectId)}` : ''

  return (
    <section>
      <PageHead
        eyebrow={t.experiments.eyebrow}
        title={t.experiments.title}
        actions={
          <div className="flex flex-wrap gap-2">
            {!showIntro ? (
              <Button type="button" variant="ghost" size="sm" onClick={() => setShowIntro(true)}>
                {t.experimentsExt.gettingStarted}
              </Button>
            ) : null}
            <Button type="button" onClick={openCreate}>
              {t.common.newExperiment}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!projectId}
              render={projectId ? <Link to={`/autopilot?project=${encodeURIComponent(projectId)}`} /> : undefined}
            >
              Autopilot
            </Button>
          </div>
        }
      />

      {appMode === 'demo' ? (
        <Alert className="mb-5" variant="warning">
          <AlertTitle>{t.demoMode}</AlertTitle>
          <AlertDescription>{t.workflowExt.toolbar.demoMode}</AlertDescription>
        </Alert>
      ) : null}

      {activeProject && isDemoProject(activeProject) ? (
        <Alert className="mb-5" variant="warning">
          <AlertDescription>
            {language === 'zh'
              ? 'PD‑1 项目仅包含预计算的合成演示数据；它不是实时模型运行、真实实验结果或科研结论。'
              : 'The PD-1 project contains precomputed synthetic demo data only; it is not a live model run, experimental result, or research conclusion.'}
          </AlertDescription>
        </Alert>
      ) : null}

      {showIntro ? (
        <AppFrame className="mb-6" panelClassName="p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-medium text-accent">{t.experimentsExt.gettingStarted}</p>
              <p className="mt-1 text-sm text-text-secondary">{t.experimentsExt.gettingStartedBody}</p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={t.experimentsExt.dismissAriaLabel}
              onClick={() => {
                localStorage.setItem('bda_intro_dismissed', 'true')
                setShowIntro(false)
              }}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={exploreDemo}>
              <PlayCircle className="h-4 w-4" />
              {t.experimentsExt.exploreDemo}
            </Button>
            {demoUnavailable ? (
              <Alert className="w-full" variant="warning">
                <AlertDescription>{language === 'zh' ? 'PD‑1 演示项目不可用。请同步内置研究包后重试；只读用户需要联系管理员。' : 'The PD-1 demo project is unavailable. Sync the built-in research package and retry; viewers may need an administrator.'}</AlertDescription>
                <AlertAction>
                  <Button type="button" size="sm" variant="outline" onClick={() => void refetchProjects()}>{t.common.retry}</Button>
                </AlertAction>
              </Alert>
            ) : null}
          </div>
        </AppFrame>
      ) : null}

      <div data-tour-id="project-library">
      <ProjectLibrary
        onCreate={openCreate}
        onManage={(project) => {
          setProjectId(project.id)
          setManageOpen(true)
        }}
        projectDelete={projectDelete}
      />
      </div>

      {showCampaigns ? <div className="mb-6"><CampaignPanel /></div> : null}

      <ActiveProjectPanel
        project={activeProject}
        projectQuery={query}
        readOnly={appMode === 'demo'}
        onManage={() => setManageOpen(true)}
        onCreate={openCreate}
      />

      <WorkflowProgress projectQuery={query} overview={overview} hasProject={Boolean(projectId)} />

      {projectId ? (
        <ApiState
          isLoading={overviewLoading}
          isError={overviewError}
          error={overviewQueryError}
          isEmpty={!overviewLoading && !overviewError && !overview}
          emptyMessage={t.projectLibrary.overviewEmpty}
          onRetry={() => void refetch()}
          loadingSkeleton={
            <AppFrame className="mb-6" panelClassName="grid gap-3 p-4 xl:grid-cols-4">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-24 w-full" />
              ))}
            </AppFrame>
          }
        >
          {overview ? <OverviewCards overview={overview} /> : null}
        </ApiState>
      ) : null}

      {overview ? <DesignPromptCard project={overview.project} /> : null}

      <AppFrame className="mb-6" panelClassName="flex flex-wrap items-center justify-between gap-3 p-4">
        <div>
          <h2 className="text-card-title font-semibold">{t.experiments.copilotTitle}</h2>
          <p className="mt-1 text-sm text-text-secondary">{t.experiments.copilotBody}</p>
        </div>
        <Button type="button" variant="outline" onClick={() => setCopilotOpen(true)}>
          {t.experimentsExt.openCopilotChat}
        </Button>
      </AppFrame>

      {projectDelete.isSuccess ? (
        <Alert className="mb-4" variant="success">
          <AlertDescription>
            {format(t.experimentsExt.projectMovedToTrash, {
              trashRoot: `${projectDelete.data.retention_days ?? 30} days`,
            })}
          </AlertDescription>
        </Alert>
      ) : null}
      {projectDelete.isError ? (
        <Alert className="mb-4" variant="destructive">
          <AlertDescription>
            {projectDelete.error instanceof Error ? projectDelete.error.message : t.experimentsExt.projectDeleteFailed}
          </AlertDescription>
        </Alert>
      ) : null}

      <ManageProjectDrawer
        open={manageOpen}
        onClose={() => setManageOpen(false)}
        creating={createOpen}
        onCreatingChange={setCreateOpen}
      />
    </section>
  )
}
