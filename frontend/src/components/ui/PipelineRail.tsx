import { Link, useLocation, useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { BookOpenIcon, CheckIcon, LockIcon } from '@phosphor-icons/react'
import { getProjectOverview } from '../../lib/api/projects'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { derivePipeline, type StageState } from '../../features/workflow/pipelineStages'
import {
  Stepper,
  StepperIndicator,
  StepperItem,
  StepperNav,
  StepperSeparator,
  StepperTitle,
  StepperTrigger,
} from '@/components/reui/stepper'

export function PipelineRail() {
  const { t } = useI18n()
  const location = useLocation()
  const navigate = useNavigate()
  const { projectId, activeProject, hasProject } = useProjectContext()
  const { data: overview } = useQuery({
    queryKey: ['project-overview', projectId],
    queryFn: () => getProjectOverview(projectId),
    enabled: Boolean(projectId),
    staleTime: 0,
    refetchOnMount: 'always',
    refetchInterval: 15_000,
  })

  if (!hasProject) return null

  const { stages, currentIndex: progressIndex } = derivePipeline(hasProject, overview)
  const query = projectId ? `?project=${encodeURIComponent(projectId)}` : ''
  const routeIndex = stages.findIndex(
    (stage) => location.pathname === stage.path || location.pathname.startsWith(`${stage.path}/`),
  )
  const selectedIndex = routeIndex >= 0 ? routeIndex : progressIndex

  const stateCaption = (state: StageState) => {
    switch (state) {
      case 'done':
        return t.shared.status.done
      case 'current':
        return t.pipeline.currentBadge
      case 'locked':
        return t.shared.status.locked
      default:
        return t.projects.workflowProgress.notStarted
    }
  }

  return (
    <nav aria-label={t.pipeline.eyebrow} className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1480px] items-center gap-4 overflow-x-auto px-4 py-2 lg:px-6">
        <Stepper
          value={selectedIndex + 1}
          onValueChange={(step) => {
            const target = stages[step - 1]
            if (target && target.state !== 'locked') navigate(`${target.path}${query}`)
          }}
          className="min-w-[42rem]"
        >
          <StepperNav>
            {stages.map((stage, index) => (
              <StepperItem
                key={stage.key}
                step={index + 1}
                completed={stage.state === 'done'}
                disabled={stage.state === 'locked'}
              >
                <StepperTrigger
                  title={stage.state === 'locked' ? t.pipeline.lockedHint : t.nav[stage.navKey]}
                  className="min-w-0 gap-2 px-2 py-1"
                >
                  <StepperIndicator>
                    {stage.state === 'done' ? (
                      <CheckIcon aria-hidden="true" />
                    ) : stage.state === 'locked' ? (
                      <LockIcon aria-hidden="true" />
                    ) : (
                      index + 1
                    )}
                  </StepperIndicator>
                  <span className="min-w-0 text-left">
                    <StepperTitle className="truncate">{t.nav[stage.navKey]}</StepperTitle>
                    <span className="block truncate text-[10px] uppercase tracking-wide text-muted-foreground">
                      {stateCaption(stage.state)}
                    </span>
                  </span>
                </StepperTrigger>
                {index < stages.length - 1 ? <StepperSeparator /> : null}
              </StepperItem>
            ))}
          </StepperNav>
        </Stepper>
        <span className="ml-auto flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
          <Link to={`/guide${query}`} className="inline-flex items-center gap-1.5 px-2 py-1 font-medium hover:text-foreground">
            <BookOpenIcon className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="hidden sm:inline">{t.pipeline.guide}</span>
          </Link>
          {activeProject ? <span className="hidden max-w-[16rem] truncate lg:inline">{activeProject.name}</span> : null}
        </span>
      </div>
    </nav>
  )
}
