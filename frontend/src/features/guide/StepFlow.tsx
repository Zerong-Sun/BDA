import { ArrowRight } from '@phosphor-icons/react'
import type { WorkflowStationData } from './guideWorkflowData'
import { useI18n } from '../../lib/i18n'
import './guideFlow.css'

export function StepFlow({ station, active }: { station: WorkflowStationData; active: boolean }) {
  const { language } = useI18n()
  const labels = language === 'zh' ? ['输入', '处理', '输出'] : ['Input', 'Step', 'Output']
  const values = [station.inputs[0], station.title, station.outputs[0]]
  return (
    <ol className="guide-flow grid gap-2 sm:grid-cols-3" data-active={active}
      aria-label={language === 'zh' ? '这一步如何完成' : 'How this step works'}>
      {values.map((value, index) => (
        <li key={labels[index]} className="guide-flow-node relative min-w-0 rounded-lg border border-border-soft bg-surface-2 px-4 py-3"
          style={{ animationDelay: `${index * 70}ms` }}>
          <span className="text-xs font-medium text-accent">{labels[index]}</span>
          <p className="mt-1 text-sm leading-6 text-text-primary">{value}</p>
          {index < values.length - 1 ? <ArrowRight className="absolute -right-3 top-1/2 z-10 hidden size-4 -translate-y-1/2 text-accent sm:block" aria-hidden="true" /> : null}
        </li>
      ))}
    </ol>
  )
}
