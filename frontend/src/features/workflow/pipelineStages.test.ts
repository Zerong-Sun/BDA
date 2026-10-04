import { describe, expect, it } from 'vitest'
import { derivePipeline } from './pipelineStages'

describe('record-aware navigation', () => {
  it.each([
    [{ candidate_count: 3, experiment_result_count: 0, latest_workflow_id: null }, 'candidates'],
    [{ candidate_count: 0, experiment_result_count: 2, latest_workflow_id: null }, 'results'],
    [{ candidate_count: 0, experiment_result_count: 0, latest_workflow_id: 'existing-run' }, 'workflow'],
  ])('keeps existing %s accessible with missing target preparation', (records, current) => {
    const pipeline = derivePipeline(true, { ...records, target_readiness: { ready_for_workflow: false }, funnel: { generated: 0, ordered: 0 } } as never)
    expect(pipeline.stages[pipeline.currentIndex].key).toBe(current)
    expect(pipeline.stages[0].state).toBe('not_started')
    expect(pipeline.stages.find((stage) => stage.key === current)?.state).toBe('current')
  })

  it('keeps new computation behind target readiness when no prior records exist', () => {
    const pipeline = derivePipeline(true, { candidate_count: 0, experiment_result_count: 0, latest_workflow_id: null, target_readiness: { ready_for_workflow: false }, funnel: { generated: 0, ordered: 0 } } as never)
    expect(pipeline.currentIndex).toBe(0)
    expect(pipeline.stages[1].state).toBe('locked')
  })
})
