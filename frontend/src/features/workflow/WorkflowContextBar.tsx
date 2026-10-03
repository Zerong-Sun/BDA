import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getClusterHealth, listComputeNodes } from '../../lib/api/registry'
import { getHealth } from '../../lib/api/health'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useAppStore } from '../../lib/store/appStore'
import { StatusPill } from '../../components/ui/StatusPill'
import { useI18n } from '../../lib/i18n'
import { projectText } from '../../lib/i18n/projectText'
import { resolveStoredText } from '../../lib/i18n/localizedText'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
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
  const { t, language } = useI18n()
  const { data: nodes = [] } = useQuery({
    queryKey: ['compute-nodes'],
    queryFn: listComputeNodes,
  })
  const { data: clusterHealth } = useQuery({
    queryKey: ['cluster-health'],
    queryFn: getClusterHealth,
    refetchInterval: 30_000,
  })
  const backendHealth = useQuery({ queryKey: ['backend-health'], queryFn: getHealth, retry: false, refetchInterval: 15_000, staleTime: 10_000 })

  const gpuAvailable = nodes.some(
    (node) =>
      String(node.labels.accelerator ?? node.labels.resource_type ?? '').toLowerCase().includes('gpu') &&
      node.enabled &&
      node.health_status === 'healthy',
  )
  const computeOffline = backendHealth.isError || (clusterHealth?.connected !== true && !gpuAvailable)
  const activeRun = projectWorkflowRuns.find((r) => r.id === workflowRunId)
  const runName = (run: WorkflowContextBarProps['projectWorkflowRuns'][number]) => {
    const localized = run.graph.localized_content as Record<string, unknown> | undefined
    return resolveStoredText(localized?.name, language, run.name || routeLabel(run.id, run.graph))
  }

  if (!activeProject) return null

  return (
    <Frame variant="inverse" spacing="xs" className="mb-3">
      <FramePanel fit className="flex flex-wrap items-center justify-between gap-3 text-sm">
      <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
        <div className="min-w-0">
          <span className="text-xs text-text-muted">{t.workflowExt.contextBar.project}</span>
          <p className="truncate font-medium text-text-primary" title={projectText(activeProject, 'name', language)}>
            {projectText(activeProject, 'name', language)}
          </p>
        </div>
        {activeRun || workflowStatus ? (
          <div className="min-w-0">
            <span className="text-xs text-text-muted">{t.workflowExt.contextBar.route}</span>
            <p className="truncate text-text-primary">
              {activeRun
                ? `${runName(activeRun)} · ${activeRun.status}`
                : workflowStatus ?? '—'}
            </p>
          </div>
        ) : null}
        {projectWorkflowRuns.length > 1 ? (
          <Select value={workflowRunId ?? null} items={projectWorkflowRuns.map((run) => ({ value: run.id, label: runName(run) }))} onValueChange={(value) => { if (value) onSelectRun(value) }}>
            <SelectTrigger className="w-full sm:w-80" aria-label={language === 'zh' ? '选择工作流' : 'Select workflow'}><SelectValue /></SelectTrigger>
            <SelectContent>{projectWorkflowRuns.map((run) => <SelectItem key={run.id} value={run.id}>{runName(run)}</SelectItem>)}</SelectContent>
          </Select>
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
