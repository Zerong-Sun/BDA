import { describe, expect, it, vi } from 'vitest'
import { collectLearningPages, reviewLearningModel, reviewLearningDecision } from './learning'
import type { ModelResponse, LearningDecisionResponse } from './learning'
vi.mock('./generatedTransport', () => ({}))
const sdk = vi.hoisted(() => ({ model: vi.fn(), decision: vi.fn() }))
vi.mock('./generated/sdk.gen', () => ({
  reviewLearningModelApiV2ProjectsProjectIdLearningModelsModelIdReviewPost: sdk.model,
  reviewLearningDecisionApiV2ProjectsProjectIdLearningDecisionsDecisionIdReviewPost: sdk.decision,
}))
describe('learning transport', () => {
  it('collects every page before selecting evidence', async () => {
    const read = vi.fn().mockResolvedValueOnce({ items: ['a'], next_cursor: 'b' }).mockResolvedValueOnce({ items: ['b'], next_cursor: null })
    expect(await collectLearningPages(read)).toEqual(['a', 'b'])
    expect(read.mock.calls).toEqual([[undefined], ['b']])
  })
  it('refuses repeated cursors and does not return partial evidence', async () => {
    await expect(collectLearningPages(async () => ({ items: ['a'], next_cursor: 'same' }))).rejects.toThrow('repeated')
  })
  it('submits the version the reviewer actually saw', async () => {
    sdk.model.mockResolvedValue({ data: {} })
    sdk.decision.mockResolvedValue({ data: {} })
    await reviewLearningModel('p', { id: 'm', version: 7 } as ModelResponse, 'promote', 'Evidence reviewed')
    await reviewLearningDecision('p', { id: 'd', version: 3 } as LearningDecisionResponse, false, 'Need data')
    expect(sdk.model).toHaveBeenCalledWith(expect.objectContaining({ headers: { 'If-Match': 'W/"7"' }, body: { action: 'promote', rationale: 'Evidence reviewed' } }))
    expect(sdk.decision).toHaveBeenCalledWith(expect.objectContaining({ headers: { 'If-Match': 'W/"3"' }, body: { approve: false, rationale: 'Need data' } }))
  })
})
