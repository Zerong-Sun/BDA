import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'

import { server } from '../../test/mocks/handlers'
import { previewWorkflowNodeScript, submitWorkflowRun } from './workflow'

describe('workflow submission backend selection', () => {
  it('submits the reviewed backend, workflow version and every node fingerprint', async () => {
    let body: unknown
    server.use(http.post('/api/v2/workflow-runs/reviewed/submissions', async ({ request }) => {
      body = await request.json()
      return HttpResponse.json({ id: 'submission', status: 'pending', jobs: [] })
    }))
    await submitWorkflowRun('reviewed', 7, { backend: 'lsf', fingerprints: { node: 'a'.repeat(64) } })
    expect(body).toEqual({ workflow_version: 7, compute_backend: 'lsf', review_fingerprints: { node: 'a'.repeat(64) } })
  })

  it('submits the saved whole workflow using the server backend default', async () => {
    const requestBodies: Array<Record<string, unknown>> = []
    server.use(
      http.post('/api/v2/workflow-runs/workflow-default/submissions', async ({ request }) => {
        requestBodies.push(await request.json() as Record<string, unknown>)
        return HttpResponse.json({
          id: `submission-${requestBodies.length}`,
          status: 'pending',
          compute_backend: requestBodies.at(-1)?.compute_backend ?? 'docker',
          jobs: [],
        }, { status: 202 })
      }),
    )

    await submitWorkflowRun('workflow-default')

    expect(requestBodies[0]).not.toHaveProperty('compute_backend')
    expect(requestBodies).toEqual([{}])
  })
})

describe('script preview overrides', () => {
  it('sends unsaved parameters only to the node preview endpoint', async () => {
    let body: unknown
    server.use(http.post('/api/v2/workflow-nodes/node-test/script-previews', async ({ request }) => {
      body = await request.json()
      return HttpResponse.json({ workflow_node_id: 'node-test', plugin_id: null, script: 'export num_designs=2', input_manifest: {} })
    }))
    await previewWorkflowNodeScript('node-test', { compute_backend: 'lsf', override_params: { num_designs: 2 } })
    expect(body).toEqual({ compute_backend: 'lsf', overrides: { num_designs: 2 } })
  })
})
