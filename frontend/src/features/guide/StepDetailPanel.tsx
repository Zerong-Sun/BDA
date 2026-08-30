import clsx from 'clsx'
import { ArrowDown, ArrowUp, UserCheck, Warning } from '@phosphor-icons/react'
import type { Icon } from '@phosphor-icons/react'
import type { WorkflowStationData } from './guideWorkflowData'
import { useI18n } from '../../lib/i18n'

interface StepDetailPanelProps {
  station: WorkflowStationData
  isActive: boolean
}

function DetailList({
  title,
  items,
  icon: Icon,
  variant,
}: {
  title: string
  items: string[]
  icon: Icon
  variant: 'input' | 'output' | 'failure' | 'decision'
}) {
  if (!items.length) return null

  const variantStyles = {
    input: 'text-info',
    output: 'text-accent',
    failure: 'text-warning',
    decision: 'text-accent-2',
  }

  return (
    <div className="space-y-2">
      <h4 className={clsx('flex items-center gap-2 text-xs font-semibold uppercase tracking-wide', variantStyles[variant])}>
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        {title}
      </h4>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item} className="flex items-start gap-2 text-sm leading-relaxed text-text-secondary">
            <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-border-strong" aria-hidden="true" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function StepDetailPanel({ station, isActive }: StepDetailPanelProps) {
  const { language } = useI18n()
  const labels = language === 'zh'
    ? { inputs: '输入', outputs: '输出', failures: '常见失败情况', decisions: '需要您的决定' }
    : { inputs: 'Inputs', outputs: 'Outputs', failures: 'Common failure cases', decisions: 'Your decisions' }
  return (
    <div
      className={clsx(
        'grid gap-5 transition-opacity duration-500',
        isActive ? 'opacity-100' : 'opacity-80',
      )}
    >
      <p className="text-sm leading-relaxed text-text-secondary">{station.technicalDetail}</p>

      <div className="grid gap-5 sm:grid-cols-2">
        <DetailList title={labels.inputs} items={station.inputs} icon={ArrowDown} variant="input" />
        <DetailList title={labels.outputs} items={station.outputs} icon={ArrowUp} variant="output" />
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <DetailList
          title={labels.failures}
          items={station.commonFailures}
          icon={Warning}
          variant="failure"
        />
        {station.userDecisions.length > 0 ? (
          <DetailList
            title={labels.decisions}
            items={station.userDecisions}
            icon={UserCheck}
            variant="decision"
          />
        ) : null}
      </div>
    </div>
  )
}
