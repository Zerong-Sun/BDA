import clsx from 'clsx'
import { forwardRef } from 'react'
import { Link, useSearchParams } from 'react-router'
import { IconTile } from '@/components/reui/icon-tile'
import { AppFrame } from '@/components/ui/AppFrame'
import { Button } from '@/components/ui/Button'
import { Disclosure } from '@/components/ui/Disclosure'
import type { WorkflowStationData } from './guideWorkflowData'
import { StepFlow } from './StepFlow'
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
  const [searchParams] = useSearchParams()
  const project = searchParams.get('project')
  const destinations: Record<string, [string, string, string]> = {
    research: ['/research?tab=evidence', 'Open evidence', '打开文献与证据'],
    'target-confirmation': ['/workflow', 'Open target preparation', '打开靶标准备'],
    'pdb-download': ['/research?tab=structures', 'Open structures', '打开结构'],
    'structure-cleaning': ['/workflow', 'Open target preparation', '打开靶标准备'],
    'design-goal': ['/research?tab=goals', 'Open project goals', '打开目标与问题'],
    'agent-planning': ['/bots/planner', 'Open Planner', '打开方案设计 Bot'],
    'model-execution': ['/workflow', 'Open workflow', '打开工作流'],
    'candidate-generation': ['/candidates', 'Open candidates', '打开候选物'],
    'scoring-ranking': ['/candidates', 'Compare candidates', '比较候选物'],
    visualization: ['/candidates', 'Inspect candidate structures', '查看候选物结构'],
    export: ['/results', 'Open results and delivery', '打开结果与交付'],
  }
  const destination = destinations[station.id]
  const destinationPath = destination
    ? `${destination[0]}${project ? `${destination[0].includes('?') ? '&' : '?'}project=${encodeURIComponent(project)}` : ''}`
    : ''
  const Icon = station.icon

  return (
    <article
      ref={ref}
      id={`guide-station-${station.id}`}
      data-step={station.stepNumber}
      data-active={isActive}
      className={clsx(
        'guide-station relative scroll-mt-28',
        'transition-colors duration-200 ease-out',
        'motion-reduce:transition-none motion-reduce:transform-none',
        isActive
          ? 'guide-station-active z-20'
          : isPast ? 'z-10' : 'z-0',
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
          <StepFlow station={station} active={isActive} />
        </div>

        <Disclosure className="rounded-lg border border-border-soft px-4"
          title={language === 'zh' ? '输入、输出和检查项' : 'Inputs, outputs and checks'}>
          <StepDetailPanel station={station} isActive={isActive} />
        </Disclosure>
        {destination && sessionStorage.getItem('bda_token') ? <Button nativeButton={false}
          render={<Link to={destinationPath} />} variant="outline" className="mt-4 h-auto min-h-9 whitespace-normal">
          {destination[language === 'zh' ? 2 : 1]}
        </Button> : null}
      </AppFrame>
    </article>
  )
})
