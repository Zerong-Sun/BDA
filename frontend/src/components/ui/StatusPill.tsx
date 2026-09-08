import type { ReactNode } from 'react'
import type { StatusTone } from './statusTone'
import { statusTone } from './statusTone'
import { localizeStatusLabel } from './statusLabel'
import { useI18n } from '../../lib/i18n'
import { StatusBadge, type StatusBadgeStatus } from './statusBadge'

const toneMap: Record<StatusTone, StatusBadgeStatus> = {
  green: 'success',
  amber: 'warning',
  blue: 'info',
  red: 'danger',
  neutral: 'neutral',
}

export function StatusPill({
  label,
  children,
  tone = 'neutral',
}: {
  label?: ReactNode
  children?: ReactNode
  tone?: StatusTone
}) {
  const { t } = useI18n()
  const displayLabel = typeof label === 'string' ? localizeStatusLabel(label, t.shared.status) : label
  return <StatusBadge status={toneMap[tone] ?? 'neutral'} label={displayLabel}>{children}</StatusBadge>
}

export function StatusPills({ status }: { status: string }) {
  const labels = status
    .split(/[·,|/]+/)
    .map((part) => part.trim())
    .filter(Boolean)
  if (labels.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {labels.map((label) => (
        <StatusPill key={label} label={label} tone={statusTone(label)} />
      ))}
    </div>
  )
}
