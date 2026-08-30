import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getClusterHealth, listComputeNodes } from '../../lib/api/registry'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useAppStore } from '../../lib/store/appStore'
import { StatusPill } from '../../components/ui/StatusPill'
import { useI18n } from '../../lib/i18n'
import { Frame, FramePanel } from '../../components/reui/frame'
import { Button } from '../../components/ui/Button'

function routeLabel(runId: string, metrics: Record<string, unknown> | undefined) {
  const route = String(metrics?.route ?? metrics?.label ?? '')
  if (route) return route.replace(/_/g, ' ')
  const status = String(metrics?.status ?? '')
  if (status) return `${status} run`
  return runId.replace(/^run_/, '').slice(-18)
}

interface WorkflowContextBarProps {
  workflowRunId?: string
  workflowStatus?: string
  projectWorkflowRuns: Array<{
    id: string
    name: string
    status: string
    graph: Record<string, unknown>
  }>
  onSelectRun: (runId: string) => void
}

export function WorkflowContextBar({
  workflowRunId,
  workflowStatus,
  projectWorkflowRuns,
  onSelectRun,
}: WorkflowContextBarProps) {
  const { activeProject } = useProjectContext()
  const setSettingsOpen = useAppStore((s) => s.setSettingsOpen)
  const { t } = useI18n()
  const { data: nodes = [] } = useQuery({
    queryKey: ['compute-nodes'],
    queryFn: listComputeNodes,
  })
  const { data: clusterHealth } = useQuery({
    queryKey: ['cluster-health'],
    queryFn: getClusterHealth,
    refetchInterval: 30_000,
  })

  const gpuAvailable = nodes.some(
    (node) =>
      String(node.labels.accelerator ?? node.labels.resource_type ?? '').toLowerCase().includes('gpu') &&
      node.enabled &&
      node.health_status !== 'unhealthy',
  )
  const computeOffline = clusterHealth?.connected !== true && !gpuAvailable
  const activeRun = projectWorkflowRuns.find((r) => r.id === workflowRunId)

  if (!activeProject) return null

  return (
    <Frame variant="inverse" spacing="xs" className="mb-3">
      <FramePanel fit className="flex flex-wrap items-center justify-between gap-3 text-sm">
      <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
        <div className="min-w-0">
          <span className="text-xs text-text-muted">{t.workflowExt.contextBar.project}</span>
          <p className="truncate font-medium text-text-primary" title={activeProject.name}>
            {activeProject.name}
          </p>
        </div>
        {activeRun || workflowStatus ? (
          <div className="min-w-0">
            <span className="text-xs text-text-muted">{t.workflowExt.contextBar.route}</span>
            <p className="truncate text-text-primary">
              {activeRun
                ? `${activeRun.name} · ${activeRun.status}`
                : workflowStatus ?? '—'}
            </p>
          </div>
        ) : null}
        {projectWorkflowRuns.length > 1 ? (
          <div className="flex flex-wrap gap-1">
            {projectWorkflowRuns.map((run) => (
              <Button type="button"
                key={run.id}
                size="xs"
                variant={run.id === workflowRunId ? 'secondary' : 'outline'}
                className={`rounded-lg ${
                  run.id === workflowRunId
                    ? 'border-accent-border bg-accent-bg text-text-primary'
                    : 'border-border-soft text-text-secondary hover:border-accent/40'
                }`}
                onClick={() => onSelectRun(run.id)}
              >
                {run.name || routeLabel(run.id, run.graph)}
              </Button>
            ))}
          </div>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="ghost" className="h-auto flex-wrap gap-1.5 p-1" onClick={() => setSettingsOpen(true)}>
          <StatusPill
            label={computeOffline ? t.workflowExt.contextBar.computeOffline : t.workflowExt.contextBar.computeOnline}
            tone={computeOffline ? 'amber' : 'green'}
          />
          {clusterHealth?.mode === 'remote_lsf' ? (
            <StatusPill
              label={
                clusterHealth.connected
                  ? t.workflowExt.contextBar.lsfConnected
                  : t.workflowExt.contextBar.lsfUnreachable
              }
              tone={clusterHealth.connected ? 'green' : 'amber'}
            />
          ) : null}
          <StatusPill
            label={gpuAvailable ? t.workflowExt.contextBar.gpuAvailable : t.workflowExt.contextBar.gpuUnavailable}
            tone={gpuAvailable ? 'green' : 'neutral'}
          />
        </Button>
        <Button
          variant="link"
          size="sm"
          render={<Link to="/experiments" />}
        >
          {t.workflowExt.contextBar.manage}
        </Button>
      </div>
      </FramePanel>
    </Frame>
  )
}
