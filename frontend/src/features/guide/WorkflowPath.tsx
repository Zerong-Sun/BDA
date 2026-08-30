import clsx from 'clsx'

interface WorkflowPathProps {
  totalSteps: number
  activeStep: number
  orientation?: 'horizontal' | 'vertical'
}

export function WorkflowPath({ totalSteps, activeStep, orientation = 'vertical' }: WorkflowPathProps) {
  const progressPercent = totalSteps > 1 ? ((activeStep - 1) / (totalSteps - 1)) * 100 : 0

  if (orientation === 'horizontal') {
    return (
      <div className="guide-path-horizontal relative h-1 w-full overflow-hidden rounded-full" aria-hidden="true">
        <div className="absolute inset-0 bg-accent-bg" />
        <div
          className="guide-path-glow absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-accent-pressed to-accent transition-all duration-700 ease-out motion-reduce:transition-none"
          style={{ width: `${Math.max(progressPercent, 4)}%` }}
        />
      </div>
    )
  }

  return (
    <div
      className="guide-path-vertical pointer-events-none absolute left-6 top-0 hidden h-full w-px md:left-1/2 md:block md:-translate-x-1/2"
      aria-hidden="true"
    >
      <div className="absolute inset-0 bg-accent-bg" />
      <div
        className={clsx(
          'guide-path-glow absolute left-0 top-0 w-full bg-gradient-to-b from-accent-pressed via-accent to-accent/30',
          'transition-all duration-700 ease-out motion-reduce:transition-none',
        )}
        style={{ height: `${Math.max(progressPercent, 2)}%` }}
      />
    </div>
  )
}
