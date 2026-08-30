import { Link, useNavigate } from 'react-router'
import type { ProjectOverview } from '../../lib/api/projects'
import { AppFrame } from '@/components/ui/AppFrame'
import { Button } from '@/components/ui/Button'
import { StatusBadge, type StatusBadgeStatus } from '@/components/ui/statusBadge'
import {
  Stepper,
  StepperIndicator,
  StepperItem,
  StepperNav,
  StepperContent,
  StepperPanel,
  StepperSeparator,
  StepperTitle,
  StepperTrigger,
} from '@/components/reui/stepper'
import { useI18n } from '../../lib/i18n'
import {
  currentStageIndex,
  pipelineStageState,
  type StageState,
} from '../workflow/pipelineStages'

type StepState = StageState

interface WorkflowProgressProps {
  projectQuery: string
  overview?: ProjectOverview | null
  hasProject: boolean
}

export function WorkflowProgress({ projectQuery, overview, hasProject }: WorkflowProgressProps) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const currentIndex = currentStageIndex(hasProject, overview)

  const steps = [
    {
      key: 'research',
      title: t.projects.workflowProgress.research,
      path: '/research',
      body: t.projects.workflowProgress.researchBody,
    },
    {
      key: 'workflow',
      title: t.projects.workflowProgress.workflow,
      path: '/workflow',
      body: t.projects.workflowProgress.workflowBody,
    },
    {
      key: 'candidates',
      title: t.projects.workflowProgress.candidates,
      path: '/candidates',
      body: t.projects.workflowProgress.candidatesBody,
    },
    {
      key: 'results',
      title: t.projects.workflowProgress.results,
      path: '/results',
      body: t.projects.workflowProgress.resultsBody,
    },
  ] as const

  const stateLabel = (state: StepState) => {
    switch (state) {
      case 'done':
        return t.shared.status.done
      case 'current':
        return t.shared.status.current
      case 'locked':
        return t.shared.status.locked
      case 'not_started':
        return t.projects.workflowProgress.notStarted
    }
  }

  const stateStatus = (state: StepState): StatusBadgeStatus => {
    if (state === 'done') return 'success'
    if (state === 'current') return 'info'
    if (state === 'locked') return 'neutral'
    return 'warning'
  }

  const navigateToStep = (value: number) => {
    const index = value - 1
    const step = steps[index]
    if (!step) return
    const state = pipelineStageState(index, hasProject, overview, currentIndex)
    if (state === 'done' || state === 'current') {
      navigate(`${step.path}${projectQuery}`)
    }
  }

  return (
    <section className="mb-6" role="region" aria-labelledby="workflow-progress-heading">
      <h2 id="workflow-progress-heading" className="mb-3 text-lg font-semibold text-text-primary">
        {t.projects.workflowProgress.title}
      </h2>
      <Stepper
        value={Math.max(1, currentIndex + 1)}
        onValueChange={navigateToStep}
      >
        <StepperNav aria-label={t.projects.workflowProgress.title} className="mb-3">
          {steps.map((step, index) => {
            const state = pipelineStageState(index, hasProject, overview, currentIndex)
            return (
              <StepperItem
                key={step.key}
                step={index + 1}
                completed={state === 'done'}
                disabled={state === 'locked' || state === 'not_started'}
              >
                <StepperTrigger
                  type="button"
                  className="shrink-0"
                  onClick={() => navigateToStep(index + 1)}
                >
                  <StepperIndicator>{index + 1}</StepperIndicator>
                  <StepperTitle>{step.title}</StepperTitle>
                  <span className="sr-only">{step.body}</span>
                </StepperTrigger>
                {index < steps.length - 1 ? <StepperSeparator /> : null}
              </StepperItem>
            )
          })}
        </StepperNav>
        <StepperPanel className="sr-only !w-px">
          {steps.map((step, index) => (
            <StepperContent key={step.key} value={index + 1} forceMount>
              {step.title}: {step.body}
            </StepperContent>
          ))}
        </StepperPanel>
      </Stepper>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {steps.map((step, index) => {
          const state = pipelineStageState(index, hasProject, overview, currentIndex)
          return (
            <AppFrame
              key={step.key}
              className={state === 'current' ? 'ring-1 ring-accent' : undefined}
              panelClassName="flex min-h-[8.5rem] flex-col p-4"
            >
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-card-title font-semibold">{step.title}</h3>
                <StatusBadge status={stateStatus(state)} label={stateLabel(state)} />
              </div>
              <p className="mt-2 line-clamp-2 flex-1 text-sm text-text-secondary">{step.body}</p>
              {state === 'current' ? (
                <Button
                  render={<Link to={`${step.path}${projectQuery}`} />}
                  className="mt-3 w-fit"
                >
                  {t.projects.workflowProgress.continue}
                </Button>
              ) : state === 'done' ? (
                <Button
                  render={<Link to={`${step.path}${projectQuery}`} />}
                  variant="ghost"
                  className="mt-3 w-fit"
                >
                  {t.projects.workflowProgress.review}
                </Button>
              ) : null}
            </AppFrame>
          )
        })}
      </div>
    </section>
  )
}
