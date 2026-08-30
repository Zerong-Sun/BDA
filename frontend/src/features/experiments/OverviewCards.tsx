import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AppFrame } from '@/components/ui/AppFrame'
import { StatusBadge } from '@/components/ui/statusBadge'
import type { ProjectOverview } from '../../lib/api/projects'
import { useI18n } from '../../lib/i18n'
import { projectText } from '../../lib/i18n/projectText'
import { getClusterHealth } from '../../lib/api/registry'

interface OverviewCardsProps {
  overview: ProjectOverview
}

function OverviewMetric({
  label,
  value,
  supporting,
  status,
}: {
  label: string
  value: ReactNode
  supporting: string
  status?: 'success' | 'warning' | 'info' | 'neutral'
}) {
  return (
    <div className="min-w-0 p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        {status ? <StatusBadge status={status} label={supporting} /> : null}
      </div>
      <p className="mt-2 truncate text-lg font-semibold text-foreground">{value}</p>
      {!status ? <p className="mt-1 text-xs text-muted-foreground">{supporting}</p> : null}
    </div>
  )
}

export function OverviewCards({ overview }: OverviewCardsProps) {
  const { t, format, language } = useI18n()
  const { data: clusterHealth } = useQuery({
    queryKey: ['cluster-health'],
    queryFn: getClusterHealth,
    refetchInterval: 30_000,
  })

  const hitLabel = `${overview.experiment_result_count}/${overview.candidate_count}`
  const computeLabel = `${overview.active_job_count} active jobs`
  const remoteConnected = clusterHealth?.mode === 'remote_lsf' && clusterHealth.connected
  const computeOffline = !remoteConnected && overview.active_job_count === 0
  const computeSupporting =
    remoteConnected && clusterHealth
      ? format(t.experimentsExt.overview.queuesLabel, { count: clusterHealth.queues.length })
      : computeLabel

  return (
    <AppFrame className="mb-6" panelClassName="p-0">
      <div className="grid divide-y divide-border md:grid-cols-2 md:divide-x md:divide-y-0 xl:grid-cols-4">
        <OverviewMetric
          label={t.experiments.overview.activeProject}
          value={projectText(overview.project, 'name', language)}
          supporting={overview.project.status}
          status="info"
        />
        <OverviewMetric
          label={t.experiments.overview.bindingPositives}
          value={hitLabel}
          supporting={t.experimentsExt.overview.bliReadout}
        />
        <OverviewMetric
          label={t.experiments.overview.computeAccess}
          value={computeOffline ? t.experimentsExt.overview.offline : t.experimentsExt.overview.connected}
          supporting={computeSupporting}
          status={computeOffline ? 'warning' : 'success'}
        />
        <OverviewMetric
          label={t.experiments.overview.nextAction}
          value={overview.next_action || t.experimentsExt.overview.noRecommendedAction}
          supporting={t.experimentsExt.overview.recommendedSupporting}
        />
      </div>
    </AppFrame>
  )
}
