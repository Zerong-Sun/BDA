import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/mocks/handlers'
import { exportLearningBatch, exportLearningDecision, exportLearningDelivery } from './learning'

describe('portable learning evidence downloads', () => {
  it.each([
    ['decision', '/api/v2/projects/p/learning/decisions/r/export', exportLearningDecision],
    ['delivery', '/api/v2/projects/p/learning/studies/r/delivery', exportLearningDelivery],
    ['handoff', '/api/v2/projects/p/learning/batches/r', exportLearningBatch],
  ] as const)('preserves the server numeric representation in the %s file', async (_name, path, download) => {
    // Python's canonical digest distinguishes 10.0 from 10 and 1e-07 from 1e-7.
    // The browser must save the original document, including nested manifests.
    const source = '{"checksum":"frozen-digest","content":{"value":10.0,"features":[0.0,1e-07,-0.0]},"manifest":{"value":10.0}}'
    expect(JSON.stringify(JSON.parse(source))).not.toEqual(source)
    server.use(http.get(path, () => new HttpResponse(source, { headers: { 'Content-Type': 'application/json' } })))
    expect(await download('p', 'r')).toBe(source)
  })
})
