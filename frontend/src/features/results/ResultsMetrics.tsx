import { MetricCard } from '../../components/ui/MetricCard'
import { Skeleton } from '@/components/ui/Skeleton'
import { AppFrame } from '../../components/ui/AppFrame'
import type { ResultsSummary } from '../../lib/api/projects'
import { useI18n } from '../../lib/i18n'

interface ResultsMetricsProps {
  summary: ResultsSummary | null
  loading?: boolean
}

export function ResultsMetrics({ summary, loading }: ResultsMetricsProps) {
  const { t } = useI18n()
  const m = t.resultsExt.metrics

  if (loading) {
    return (
      <div className="mb-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <AppFrame key={index} panelClassName="space-y-3 p-4">
            <Skeleton className="h-3 w-2/3" />
            <Skeleton className="h-7 w-1/2" />
            <Skeleton className="h-3 w-3/4" />
          </AppFrame>
        ))}
      </div>
    )
  }

  if (!summary) {
    return (
      <AppFrame className="mb-5" panelClassName="border border-dashed border-border p-4 text-sm text-text-secondary">
        {m.unavailable}
      </AppFrame>
    )
  }

  return (
    <div className="mb-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        label={m.hitRate}
        value={summary.pass_rate == null ? '—' : `${(summary.pass_rate * 100).toFixed(1)}%`}
        supporting={`${summary.passed_result_count}/${summary.passed_result_count + summary.failed_result_count}`}
      />
      <MetricCard
        label={m.bestKd}
        value={summary.best_result_value == null ? '—' : `${summary.best_result_value} ${summary.best_result_unit ?? ''}`.trim()}
        supporting={
          summary.best_result_id
            ? summary.best_result_id
            : m.noBliYet
        }
      />
      <MetricCard
        label={m.mainFailure}
        value={String(summary.failed_result_count)}
        supporting={`${summary.unknown_result_count} unknown`}
      />
      <MetricCard
        label={m.decision}
        value={String(summary.tested_candidate_count)}
        supporting={`${summary.candidate_count} total candidates`}
      />
    </div>
  )
}
