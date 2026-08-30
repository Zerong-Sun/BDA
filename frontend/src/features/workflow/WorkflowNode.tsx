import { Handle, Position, type NodeProps } from '@xyflow/react'
import clsx from 'clsx'
import { StatusPill } from '../../components/ui/StatusPill'
import { statusTone } from '../../components/ui/statusTone'
import { useI18n } from '../../lib/i18n'
import { DefaultNodeIcon, nodeIconMap, type NodeIconName } from './nodeIcons'
import type { WorkflowNodeData } from './workflowTypes'

const topBorderByStatus: Record<string, string> = {
  queued: 'border-t-accent-2',
  running: 'border-t-info',
  completed: 'border-t-success',
  failed: 'border-t-danger',
  requires_review: 'border-t-accent-2',
}

const statusKeyMap = {
  not_started: 'notStarted',
  queued: 'queued',
  running: 'running',
  completed: 'completed',
  failed: 'failed',
  requires_review: 'needsReview',
  demo: 'demo',
  skipped: 'skipped',
} as const

export function WorkflowNodeCard({ data, selected }: NodeProps) {
  const { t } = useI18n()
  const nodeData = data as WorkflowNodeData
  const Icon = nodeIconMap[nodeData.icon as NodeIconName] ?? DefaultNodeIcon
  const statusKey = nodeData.status ?? 'not_started'
  const mappedKey = statusKeyMap[statusKey as keyof typeof statusKeyMap]
  const statusLabel = mappedKey ? t.shared.status[mappedKey] : statusKey.replaceAll('_', ' ')

  return (
    <article
      className={clsx(
        'group min-h-[4.5rem] w-[12.5rem] max-w-[13.75rem] rounded-xl border border-border-default bg-surface-1 px-3 py-2.5 text-sm shadow-soft',
        'border-t-2',
        topBorderByStatus[statusKey] ?? 'border-t-border-soft',
        selected && 'ring-2 ring-accent ring-offset-1 ring-offset-bg-canvas',
        statusKey === 'running' && 'animate-pulse',
      )}
    >
      <Handle
        id="input"
        type="target"
        position={Position.Left}
        className="!h-2 !w-2 !border-2 !border-bg-canvas !bg-accent opacity-0 transition-opacity group-hover:opacity-100 [.selected_&]:opacity-100"
      />
      <header className="flex min-w-0 items-center gap-2">
        <Icon className="h-4 w-4 shrink-0 text-accent" />
        <span className="truncate text-card-title font-semibold text-text-primary">{nodeData.label}</span>
      </header>
      <p className="mt-0.5 truncate text-xs text-text-secondary">{nodeData.footer || nodeData.description}</p>
      <div className="mt-2 flex items-center justify-between gap-2">
        <StatusPill label={statusLabel} tone={statusTone(statusKey)} />
        {nodeData.resource ? (
          <span className="truncate text-[11px] uppercase text-text-muted">{nodeData.resource}</span>
        ) : null}
      </div>
      <Handle
        id="output"
        type="source"
        position={Position.Right}
        className="!h-2 !w-2 !border-2 !border-bg-canvas !bg-accent opacity-0 transition-opacity group-hover:opacity-100 [.selected_&]:opacity-100"
      />
    </article>
  )
}
