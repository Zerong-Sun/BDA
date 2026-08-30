import { useQuery } from '@tanstack/react-query'
import { CloudCheck, CloudX } from '@phosphor-icons/react'
import { Badge } from '../../components/reui/badge'
import { Frame, FramePanel } from '../../components/reui/frame'
import { getClusterHealth, listComputeNodes } from '../../lib/api/registry'
import { getHealth } from '../../lib/api/health'
import { useI18n } from '../../lib/i18n'

export function ComputeStatusStrip() {
  const { t, format } = useI18n()
  const { data: nodes = [] } = useQuery({
    queryKey: ['compute-nodes'],
    queryFn: listComputeNodes,
  })
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
  })
  const { data: clusterHealth } = useQuery({
    queryKey: ['cluster-health'],
    queryFn: getClusterHealth,
    refetchInterval: 30_000,
  })

  const gpuNodes = nodes.filter((node) =>
    String(node.labels.accelerator ?? node.labels.resource_type ?? '').toLowerCase().includes('gpu'),
  )
  const cpuNodes = nodes.filter((node) => !gpuNodes.some((gpuNode) => gpuNode.id === node.id))
  const gpuAvailable = gpuNodes.some((node) => node.enabled && node.health_status !== 'unhealthy')
  const cpuAvailable = cpuNodes.some((node) => node.enabled && node.health_status !== 'unhealthy')

  return (
    <Frame variant="inverse" spacing="xs" className="mb-4">
      <FramePanel fit className="flex flex-wrap items-center gap-3 text-sm">
      <span className="inline-flex items-center gap-2 text-text-secondary">
        {clusterHealth?.connected ? (
          <CloudCheck className="h-4 w-4 text-success" aria-hidden="true" />
        ) : (
          <CloudX className="h-4 w-4 text-accent-2" aria-hidden="true" />
        )}
        {t.workflowExt.computeStatus.computeAccess}
      </span>
      {clusterHealth?.mode === 'remote_lsf' ? (
        <>
          <span className={clusterHealth.connected ? 'text-success' : 'text-accent-2'}>
            {clusterHealth.connected
              ? t.workflowExt.computeStatus.lsfConnected
              : t.workflowExt.computeStatus.lsfUnreachable}
          </span>
          {clusterHealth.connected && clusterHealth.queues.length > 0 ? (
            <span
              className="max-w-full truncate text-xs text-text-secondary"
              title={clusterHealth.queues.join('\n')}
            >
              {format(t.workflowExt.computeStatus.queues, {
                list: clusterHealth.queues.slice(0, 3).join(' · '),
              })}
            </span>
          ) : null}
          {clusterHealth.connected && clusterHealth.all_queues?.length ? (
            <span
              className="max-w-full truncate text-xs text-text-secondary"
              title={clusterHealth.all_queues.join('\n')}
            >
              {format(t.workflowExt.computeStatus.moreQueues, {
                list: clusterHealth.all_queues.slice(0, 6).join(' · '),
              })}
            </span>
          ) : null}
        </>
      ) : null}
      <Badge variant={gpuAvailable ? 'success-light' : 'warning-light'}>
        {gpuAvailable
          ? t.workflowExt.computeStatus.gpuWorkerAvailable
          : t.workflowExt.computeStatus.gpuWorkerUnavailable}
      </Badge>
      <Badge variant={cpuAvailable ? 'success-light' : 'warning-light'}>
        {cpuAvailable
          ? t.workflowExt.computeStatus.cpuWorkerAvailable
          : t.workflowExt.computeStatus.cpuWorkerUnavailable}
      </Badge>
      {!gpuAvailable && !cpuAvailable && clusterHealth?.mode !== 'remote_lsf' ? (
        <span className="text-xs text-text-secondary">
          {format(t.workflowExt.computeStatus.computeModeHint, { mode: clusterHealth?.mode ?? health?.service ?? 'unavailable' })}
        </span>
      ) : null}
      </FramePanel>
    </Frame>
  )
}
