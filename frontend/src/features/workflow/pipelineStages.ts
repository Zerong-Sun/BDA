import type { ProjectOverview } from '../../lib/api/projects'

/** Navigation reflects available project records. Execution readiness is enforced
 * by workflow preflight and submission, not by hiding imported evidence. */
export type StageKey = 'research' | 'workflow' | 'candidates' | 'lab' | 'results'
export type StageState = 'done' | 'current' | 'locked' | 'not_started'

export interface PipelineStageMeta {
  key: StageKey
  /** Key into `t.nav` for the stage label. */
  navKey: StageKey
  path: `/${StageKey}`
}

export const PIPELINE_STAGES: readonly PipelineStageMeta[] = [
  { key: 'research', navKey: 'research', path: '/research' },
  { key: 'workflow', navKey: 'workflow', path: '/workflow' },
  { key: 'candidates', navKey: 'candidates', path: '/candidates' },
  { key: 'lab', navKey: 'lab', path: '/lab' },
  { key: 'results', navKey: 'results', path: '/results' },
] as const

export function currentStageIndex(
  hasProject: boolean,
  overview?: ProjectOverview | null,
): number {
  if (!hasProject) return 0
  if ((overview?.experiment_result_count ?? 0) > 0) return 4
  if ((overview?.funnel.ordered ?? 0) > 0) return 3
  if ((overview?.candidate_count ?? overview?.funnel.generated ?? 0) > 0) return 2
  if (overview?.latest_workflow_id || overview?.target_readiness?.ready_for_workflow === true) return 1
  return 0
}

export function pipelineStageState(
  index: number,
  hasProject: boolean,
  overview: ProjectOverview | null | undefined,
  currentIndex: number,
): StageState {
  if (!hasProject) return index === 0 ? 'current' : 'locked'
  const hasCandidates = (overview?.candidate_count ?? overview?.funnel.generated ?? 0) > 0
  const hasResults = (overview?.experiment_result_count ?? 0) > 0
  const hasOrders = (overview?.funnel.ordered ?? 0) > 0
  const hasWorkflow = Boolean(overview?.latest_workflow_id)
  const targetReady = overview?.target_readiness?.ready_for_workflow === true
  const done = [targetReady, hasWorkflow && hasCandidates, hasCandidates && (hasOrders || hasResults), hasResults, hasResults]
  const available = [true, targetReady || hasWorkflow, hasCandidates, hasCandidates || hasResults, hasCandidates || hasResults]
  if (index === currentIndex) return 'current'
  if (done[index] && index < currentIndex) return 'done'
  return available[index] ? 'not_started' : 'locked'

}

export interface DerivedStage extends PipelineStageMeta {
  index: number
  state: StageState
}

export interface DerivedPipeline {
  stages: DerivedStage[]
  currentIndex: number
}

/** Resolve every stage's state for a project in one pass. */
export function derivePipeline(
  hasProject: boolean,
  overview?: ProjectOverview | null,
): DerivedPipeline {
  const currentIndex = currentStageIndex(hasProject, overview)
  const stages = PIPELINE_STAGES.map((meta, index) => ({
    ...meta,
    index,
    state: pipelineStageState(index, hasProject, overview, currentIndex),
  }))
  return { stages, currentIndex }
}

/** The stage the user should act on next, i.e. the current stage. */
export function nextStage(pipeline: DerivedPipeline): DerivedStage {
  return pipeline.stages[pipeline.currentIndex] ?? pipeline.stages[0]
}
