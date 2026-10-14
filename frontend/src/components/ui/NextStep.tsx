import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { ArrowRightIcon, ArrowCounterClockwiseIcon } from '@phosphor-icons/react'
import { getProjectOverview } from '../../lib/api/projects'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { derivePipeline, PIPELINE_STAGES, type StageKey } from '../../features/workflow/pipelineStages'
import { AppFrame } from './AppFrame'
import { Button } from './Button'

/**
 * Consistent "what to do next" affordance rendered at the foot of each working
 * page. It advances the user from the page they are on to the next stage in the
 * design loop, and never dead-ends: a locked next stage shows why, and the final
 * stage points back to Research to start the next round.
 */
export function NextStep({ stage }: { stage: StageKey }) {
  const { t, format, language } = useI18n()
  const { projectId, hasProject } = useProjectContext()

  const { data: overview } = useQuery({
    queryKey: ['project-overview', projectId],
    queryFn: () => getProjectOverview(projectId),
    enabled: Boolean(projectId),
  })

  if (!hasProject || !overview) return null

  const query = projectId ? `?project=${encodeURIComponent(projectId)}` : ''
  const pageIndex = PIPELINE_STAGES.findIndex((item) => item.key === stage)
  const { stages } = derivePipeline(hasProject, overview)

  // Reaching this page does not prove that a research cycle has completed.
  if (pageIndex === PIPELINE_STAGES.length - 1) {
    const hasEvidence = (overview.candidate_count ?? overview.funnel.generated ?? 0) > 0 || overview.experiment_result_count > 0
    return (
      <AppFrame className="mt-6" panelClassName="flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="min-w-0">
          <p className="text-fine font-medium uppercase tracking-wider text-text-muted">
            {t.pipeline.nextStep}
          </p>
          <p className="mt-0.5 text-sm text-text-secondary">{hasEvidence ? language === 'zh' ? '复核证据，记录判断和仍待解决的问题。' : 'Review the evidence and record decisions and open questions.' : language === 'zh' ? '尚无结果。返回项目检查输入和任务进度。' : 'No results are available yet. Review project inputs and task progress.'}</p>
        </div>
        <Button
          variant="outline"
          render={<Link to={hasEvidence ? `/research${query}&tab=timeline` : `/projects${query}`} />}
        >
          <ArrowCounterClockwiseIcon className="h-4 w-4" aria-hidden="true" />
          {hasEvidence ? language === 'zh' ? '查看项目决策' : 'Review project decisions' : language === 'zh' ? '返回项目' : 'Review project'}
        </Button>
      </AppFrame>
    )
  }

  const next = stages[pageIndex + 1]
  if (!next) return null
  const nextLabel = t.nav[next.navKey]
  const locked = next.state === 'locked'

  return (
    <AppFrame className="mt-6" panelClassName="flex flex-wrap items-center justify-between gap-3 p-4">
      <div className="min-w-0">
        <p className="text-fine font-medium uppercase tracking-wider text-text-muted">
          {t.pipeline.nextStep}
        </p>
        <p className="mt-0.5 text-sm text-text-secondary">
          {locked ? t.pipeline.lockedHint : format(t.pipeline.continueTo, { stage: nextLabel })}
        </p>
      </div>
      {locked ? (
        <Button type="button" variant="outline" disabled>
          {nextLabel}
          <ArrowRightIcon className="h-4 w-4" aria-hidden="true" />
        </Button>
      ) : (
        <Button render={<Link to={`${next.path}${query}`} />}>
          {format(t.pipeline.continueTo, { stage: nextLabel })}
          <ArrowRightIcon className="h-4 w-4" aria-hidden="true" />
        </Button>
      )}
    </AppFrame>
  )
}
