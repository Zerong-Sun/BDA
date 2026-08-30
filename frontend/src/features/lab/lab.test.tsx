import { describe, expect, it } from 'vitest'
import { PIPELINE_STAGES, derivePipeline } from '../workflow/pipelineStages'
import { en } from '../../lib/i18n/en'
import { zh } from '../../lib/i18n/zh'

describe('Lab stage in the design loop', () => {
  it('sits between candidates and results', () => {
    const keys = PIPELINE_STAGES.map((stage) => stage.key)
    expect(keys).toEqual(['research', 'workflow', 'candidates', 'lab', 'results'])
    expect(PIPELINE_STAGES[3]).toMatchObject({ key: 'lab', path: '/lab' })
  })

  it('unlocks once there are candidates to make, and completes on a measurement', () => {
    const withCandidates = derivePipeline(true, {
      target_readiness: { ready_for_workflow: true },
      funnel: { generated: 4, ordered: 4 },
      experiment_result_count: 0,
    } as never)
    expect(withCandidates.stages[3].state).not.toBe('locked')

    const withResults = derivePipeline(true, {
      target_readiness: { ready_for_workflow: true },
      funnel: { generated: 4, ordered: 4 },
      experiment_result_count: 2,
    } as never)
    expect(withResults.currentIndex).toBe(4)
    expect(withResults.stages[3].state).toBe('done')
  })

  it('stays locked until a project is chosen, like every other stage', () => {
    const pipeline = derivePipeline(false, null)
    expect(pipeline.stages[3].state).toBe('locked')
  })
})

describe('Lab copy', () => {
  it('is translated in both locales', () => {
    expect(en.nav.lab).toBeTruthy()
    expect(zh.nav.lab).toBeTruthy()
    expect(en.lab.library.title).toBeTruthy()
    expect(zh.lab.library.title).toBeTruthy()
  })

  it('tells the reader that sequences are withheld on purpose', () => {
    // Without this line the missing sequence column reads as a bug rather than
    // as the IP boundary it is.
    expect(en.lab.library.sequenceNotice).toMatch(/fingerprint/i)
    expect(zh.lab.library.sequenceNotice).toMatch(/指纹/)
  })
})
