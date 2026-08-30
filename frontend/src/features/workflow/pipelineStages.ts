import type { ProjectOverview } from '../../lib/api/projects'

/**
 * Single source of truth for the design loop the whole app navigates through:
 * Research -> Workflow -> Candidates -> Lab -> Results.
 *
 * Lab sits where a design stops being a prediction: candidates are made and
 * measured there, which is where the results in the last stage come from.
 *
 * The stage-gating semantics here are the product contract exercised by
 * WorkflowProgress.test / stage6VerticalSlice.test: a project that is not
 * target-ready must keep the user on Research, and a stage never unlocks from
 * historical artifacts alone. Both the launchpad cards and the persistent
 * pipeline rail derive their state from this module so they can never drift.
 */
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
  if (overview?.target_readiness?.ready_for_workflow !== true) return 0
  if ((overview?.experiment_result_count ?? 0) > 0) return 4
  if ((overview?.funnel.generated ?? 0) > 0) return 2
  if ((overview?.funnel.ordered ?? 0) > 0 || (overview?.funnel.generated ?? 0) > 0) return 1
  return 1
}

export function pipelineStageState(
  index: number,
  hasProject: boolean,
  overview: ProjectOverview | null | undefined,
  currentIndex: number,
): StageState {
  if (!hasProject) return index === 0 ? 'current' : 'locked'
  const hasGeneratedCandidates = (overview?.funnel.generated ?? 0) > 0
  const hasResults = (overview?.experiment_result_count ?? 0) > 0
  const targetReady = overview?.target_readiness?.ready_for_workflow === true
  const done =
    index === 0
      ? targetReady
      : index === 1 || index === 2
        ? hasGeneratedCandidates
        : index === 3
          ? hasResults // the bench is done once it has produced a measurement
          : hasResults
  if (done && index < currentIndex) return 'done'
  if (index === currentIndex) return 'current'
  if (index < currentIndex) return 'done'
  if (index > 0 && !hasProject) return 'locked'
  const prevDone =
    index === 0
      ? true
      : index === 1
        ? targetReady
        : index === 2
          ? hasGeneratedCandidates
          : hasGeneratedCandidates
  return prevDone ? 'not_started' : 'locked'
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
