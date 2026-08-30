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
import { getGuideWorkflowStations } from './guideWorkflowData'
import { useI18n } from '../../lib/i18n'

interface WorkflowProgressProps {
  activeStep: number
  onStepClick?: (stepNumber: number) => void
  orientation?: 'horizontal' | 'vertical'
  label?: string
}

export function WorkflowProgress({
  activeStep,
  onStepClick,
  orientation = 'horizontal',
  label,
}: WorkflowProgressProps) {
  const { language } = useI18n()
  const stations = getGuideWorkflowStations(language)
  const resolvedLabel = label ?? (language === 'zh' ? '工作流步骤' : 'Workflow steps')
  const totalSteps = stations.length
  const isVertical = orientation === 'vertical'

  const stepper = (
    <Stepper
      value={activeStep}
      onValueChange={(step) => onStepClick?.(step)}
      orientation={orientation}
      aria-label={resolvedLabel}
      className={isVertical ? 'guide-progress' : 'guide-progress min-w-max'}
    >
      <StepperNav
        aria-label={resolvedLabel}
        className={
          isVertical
            ? 'gap-1'
            : 'min-w-max items-center rounded-full border border-accent-border bg-accent-bg px-3 py-2 backdrop-blur-sm'
        }
      >
        {stations.map((station, index) => (
          <StepperItem
            key={station.id}
            step={station.stepNumber}
            completed={station.stepNumber < activeStep}
            className={isVertical ? 'justify-start' : undefined}
          >
            <StepperTrigger
              type="button"
              className={isVertical ? 'w-full justify-start py-1.5 text-left' : 'shrink-0'}
              aria-label={
                language === 'zh'
                  ? `第 ${station.stepNumber} 步：${station.title}`
                  : `Step ${station.stepNumber}: ${station.title}`
              }
            >
              <StepperIndicator>{station.stepNumber}</StepperIndicator>
              <StepperTitle className={isVertical ? undefined : 'sr-only sm:not-sr-only'}>
                {station.title}
              </StepperTitle>
            </StepperTrigger>
            {index < totalSteps - 1 ? <StepperSeparator /> : null}
          </StepperItem>
        ))}
      </StepperNav>
      <StepperPanel className="sr-only">
        {stations.map((station) => (
          <StepperContent key={station.id} value={station.stepNumber} forceMount>
            {station.title}
          </StepperContent>
        ))}
      </StepperPanel>
    </Stepper>
  )

  if (isVertical) return stepper

  return (
    <div
      data-guide-progress-viewport="horizontal"
      className="w-full overflow-x-auto pb-1"
    >
      {stepper}
    </div>
  )
}
