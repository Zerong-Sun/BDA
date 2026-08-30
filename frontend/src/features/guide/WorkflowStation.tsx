import clsx from 'clsx'
import { forwardRef } from 'react'
import { IconTile } from '@/components/reui/icon-tile'
import { AppFrame } from '@/components/ui/AppFrame'
import type { WorkflowStationData } from './guideWorkflowData'
import { StepAnimationPlaceholder } from './StepAnimationPlaceholder'
import { StepDetailPanel } from './StepDetailPanel'
import { useI18n } from '../../lib/i18n'

interface WorkflowStationProps {
  station: WorkflowStationData
  isActive: boolean
  isPast: boolean
  index: number
}

export const WorkflowStation = forwardRef<HTMLElement, WorkflowStationProps>(function WorkflowStation(
  { station, isActive, isPast, index },
  ref,
) {
  const { language } = useI18n()
  const Icon = station.icon
  const isFuture = !isActive && !isPast

  return (
    <article
      ref={ref}
      id={`guide-station-${station.id}`}
      data-step={station.stepNumber}
      data-active={isActive}
      className={clsx(
        'guide-station relative scroll-mt-28',
        'transition-all duration-700 ease-out',
        'motion-reduce:transition-none motion-reduce:transform-none',
        isActive
          ? [
              'guide-station-active z-20 scale-[1.02]',
              'md:scale-[1.03]',
            ]
          : isPast
            ? 'z-10 opacity-70 blur-[0.3px]'
            : 'z-0 opacity-55 blur-[0.5px]',
        isFuture && 'guide-station-future',
      )}
      aria-current={isActive ? 'step' : undefined}
    >
      {/* Isometric building accent */}
      <div
        className={clsx(
          'pointer-events-none absolute -right-2 -top-2 h-16 w-16 opacity-40 transition-opacity duration-700',
          isActive ? 'opacity-70' : 'opacity-20',
        )}
        aria-hidden="true"
      >
        <div className="guide-building-block h-full w-full" />
      </div>

      <AppFrame
        className={isActive ? 'ring-1 ring-accent' : undefined}
        panelClassName="relative p-5 sm:p-6 md:p-8"
      >
        <header className="mb-5 flex flex-wrap items-start gap-4">
          <IconTile variant={isActive ? 'soft' : 'frame'} size="lg" className={isActive ? 'text-accent' : undefined}>
            <Icon
              className={clsx('h-5 w-5 transition-colors', isActive ? 'text-accent' : 'text-text-muted')}
              aria-hidden="true"
            />
          </IconTile>

          <div className="min-w-0 flex-1">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span
                className={clsx(
                  'inline-flex rounded-full px-2.5 py-0.5 font-mono text-fine font-semibold uppercase tracking-wider',
                  isActive
                    ? 'border border-accent-border bg-accent-bg text-accent'
                    : 'border border-border-soft bg-surface-2 text-text-muted',
                )}
              >
                {language === 'zh' ? `第 ${station.stepNumber} 步` : `Step ${station.stepNumber}`}
              </span>
              <span className="font-mono text-fine uppercase tracking-wider text-text-muted">{station.stationLabel}</span>
            </div>
            <h3
              className={clsx(
                'text-lg font-semibold leading-snug transition-colors sm:text-xl',
                isActive ? 'text-text-primary' : 'text-text-secondary',
              )}
            >
              {station.title}
            </h3>
          </div>

          <span
            className="hidden font-mono text-4xl font-light tabular-nums text-accent/15 md:block"
            aria-hidden="true"
          >
            {String(index + 1).padStart(2, '0')}
          </span>
        </header>

        <p className="mb-6 text-sm leading-relaxed text-text-secondary sm:text-base">{station.beginnerExplanation}</p>

        <div className="mb-6">
          <StepAnimationPlaceholder stepId={station.id} />
        </div>

        <StepDetailPanel station={station} isActive={isActive} />
      </AppFrame>
    </article>
  )
})
