import { useQuery } from '@tanstack/react-query'
import { listCandidateMetrics } from '../../lib/api/candidates'
import { groupCandidateMetricsByKey, MEASURED } from '../../lib/schemas/candidate'
import { useI18n } from '../../lib/i18n'

interface CandidateConditionMetricsProps {
  candidateId: string
}

export function CandidateConditionMetrics({ candidateId }: CandidateConditionMetricsProps) {
  const { t, format } = useI18n()
  const detail = t.candidatesExt.detail
  const metricsQuery = useQuery({
    queryKey: ['candidate-metrics', candidateId],
    queryFn: () => listCandidateMetrics(candidateId),
    staleTime: 60_000,
  })

  // A metric the bench has spoken on outranks one only a model has spoken on: it is the
  // comparison this panel exists to show, so it must not sit below six predicted rows.
  const groups = groupCandidateMetricsByKey(metricsQuery.data?.items ?? []).sort((a, b) =>
    Number(Boolean(b.predictedVsMeasured)) - Number(Boolean(a.predictedVsMeasured)),
  )

  if (!metricsQuery.isLoading && groups.length === 0) {
    return (
      <section className="mt-4 rounded-lg border border-border-soft bg-bg-app p-3 text-xs text-text-secondary">
        <p className="font-semibold text-text-primary">{detail.conditionMetricsTitle}</p>
        <p className="mt-2">{detail.noConditionMetrics}</p>
      </section>
    )
  }

  return (
    <section className="mt-4 rounded-lg border border-border-soft bg-bg-app p-3 text-xs text-text-secondary">
      <p className="font-semibold text-text-primary">{detail.conditionMetricsTitle}</p>
      <p className="mt-1">{detail.conditionMetricsHelp}</p>
      <div className="mt-3 grid gap-3">
        {groups.map((group) => (
          <div key={group.metricKey} className="rounded-md border border-border-soft/70 p-2">
            <p className="font-mono text-text-primary">{group.metricKey}</p>
            {group.predictedVsMeasured ? (
              <p className="mt-1 rounded bg-surface-2 px-2 py-1 text-text-primary">
                {format(detail.predictedVsMeasured, {
                  predicted: `${group.predictedVsMeasured.predicted.value}${
                    group.predictedVsMeasured.unit ? ` ${group.predictedVsMeasured.unit}` : ''
                  }`,
                  measured: `${group.predictedVsMeasured.measured.value}${
                    group.predictedVsMeasured.unit ? ` ${group.predictedVsMeasured.unit}` : ''
                  }`,
                  delta: `${group.predictedVsMeasured.delta > 0 ? '+' : ''}${group.predictedVsMeasured.delta.toFixed(3)}`,
                })}
              </p>
            ) : null}
            <dl className="mt-1 grid gap-1">
              {group.rows.map((row) => (
                <div
                  key={row.id}
                  className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-2"
                >
                  <dt className="truncate">
                    {row.condition || detail.conditionMetricsUnconditioned}
                    <span
                      className={
                        row.evidence_kind === MEASURED
                          ? 'ml-2 rounded-full border border-accent-border px-1.5 py-0.5 text-[10px] font-semibold text-accent'
                          : 'ml-2 rounded-full border border-border-soft px-1.5 py-0.5 text-[10px] text-text-muted'
                      }
                      title={
                        row.evidence_kind === MEASURED
                          ? detail.evidenceMeasuredHelp
                          : detail.evidencePredictedHelp
                      }
                    >
                      {row.evidence_kind === MEASURED ? detail.evidenceMeasured : detail.evidencePredicted}
                    </span>
                    <span className="ml-2 rounded-full border border-border-soft px-1.5 py-0.5 text-[10px] text-text-muted">
                      {row.assessor}
                    </span>
                  </dt>
                  <dd className="text-right text-text-primary">
                    {row.value}
                    {row.unit ? ` ${row.unit}` : ''}
                  </dd>
                </div>
              ))}
            </dl>
            {group.delta ? (
              <p className="mt-1 border-t border-border-soft/70 pt-1 text-text-primary">
                {format(detail.conditionMetricsDelta, {
                  conditionA: group.delta.conditionA,
                  conditionB: group.delta.conditionB,
                })}
                : {group.delta.value.toFixed(3)}
                {group.delta.unit ? ` ${group.delta.unit}` : ''}
              </p>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  )
}
