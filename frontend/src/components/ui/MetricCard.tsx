import type { ReactNode } from 'react'
import { StatusPill } from './StatusPill'
import type { StatusTone } from './statusTone'
import { AppFrame } from './AppFrame'

interface MetricCardProps {
  label: string
  value: string
  supporting?: string
  statusTone?: StatusTone
  action?: ReactNode
}

export function MetricCard({ label, value, supporting, statusTone, action }: MetricCardProps) {
  return (
    <AppFrame
      className="min-h-[7.5rem]"
      panelClassName="flex min-w-0 flex-col p-4"
      aria-label={label}
    >
      <span className="text-xs font-medium text-text-muted">{label}</span>
      <strong className="mt-2 line-clamp-2 text-lg font-semibold leading-snug text-text-primary" title={value}>
        {value}
      </strong>
      {supporting ? (
        statusTone ? (
          <div className="mt-2">
            <StatusPill label={supporting} tone={statusTone} />
          </div>
        ) : (
          <p className="mt-2 line-clamp-2 text-sm text-text-secondary">{supporting}</p>
        )
      ) : null}
      {action ? <div className="mt-auto pt-2">{action}</div> : null}
    </AppFrame>
  )
}
