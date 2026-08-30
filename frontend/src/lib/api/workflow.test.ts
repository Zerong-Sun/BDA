import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'

import { server } from '../../test/mocks/handlers'
import { submitWorkflowNode, submitWorkflowRun } from './workflow'

describe('workflow submission backend selection', () => {
  it('uses the server default unless a node submission explicitly overrides it', async () => {
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
    await submitWorkflowNode('workflow-default')
    await submitWorkflowNode('workflow-default', { compute_backend: 'lsf' })

    expect(requestBodies[0]).not.toHaveProperty('compute_backend')
    expect(requestBodies[1].compute_backend).toBeUndefined()
    expect(requestBodies[2].compute_backend).toBe('lsf')
  })
})
