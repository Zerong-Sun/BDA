import type { ReactNode } from 'react'
import { Badge } from '@/components/reui/badge'

export type StatusBadgeStatus = 'success' | 'warning' | 'info' | 'danger' | 'neutral'

const statusVariants: Record<
  StatusBadgeStatus,
  'success-light' | 'warning-light' | 'info-light' | 'destructive-light' | 'outline'
> = {
  success: 'success-light',
  warning: 'warning-light',
  info: 'info-light',
  danger: 'destructive-light',
  neutral: 'outline',
}

export function StatusBadge({
  status,
  label,
  children,
}: {
  status: StatusBadgeStatus
  label?: ReactNode
  children?: ReactNode
}) {
  return (
    <Badge variant={statusVariants[status]} radius="full">
      {label ?? children}
    </Badge>
  )
}
