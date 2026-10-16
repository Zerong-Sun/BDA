import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'

import { server } from '../../test/mocks/handlers'
import { getWorkflowGraph, addWorkflowNode, previewWorkflowNodeScript, submitWorkflowRun } from './workflow'

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


it('preserves manual execution mode and optimistic version through the generated API', async () => {
  let body: Record<string, unknown> = {}
  let version: string | null = null
  server.use(
    http.get('/api/v2/workflow-runs/manual-route', () => HttpResponse.json({ id: 'manual-route', project_id: 'project-a', name: 'Review', status: 'draft', graph: {}, version: 4, created_by: 'user', created_at: '', updated_at: '' })),
    http.post('/api/v2/workflow-runs/manual-route/nodes', async ({ request }) => {
      body = await request.json() as Record<string, unknown>
      version = request.headers.get('If-Match')
      return HttpResponse.json({ id: 'review-node', workflow_run_id: 'manual-route', node_key: body.key, node_type: body.node_type, execution_mode: body.execution_mode, model_plugin: 'manual_review', model_plugin_id: null, container_image: null, command: null, queue: null, status: 'draft', parameters: body.parameters, configuration: {}, input_bindings: [], error_message: null, version: 1, created_at: '', updated_at: '' })
    }),
  )
  const node = await addWorkflowNode('manual-route', { key: 'Review evidence', node_type: 'manual_review', execution_mode: 'manual', parameters: { review_status: 'pending_review' } })
  expect(version).toBe('W/"4"')
  expect(body.execution_mode).toBe('manual')
  expect(node.execution_mode).toBe('manual')
  expect(node.status).toBe('draft')
  expect(body).not.toHaveProperty('status')
})


it('keeps imported dependency identities stable across polling without inventing saved gates', async () => {
  let reads = 0
  const legacy = { source: 'input', target: 'fold' }
  const saved = { id: 'saved-gate', source: 'fold', target: 'review', gate: { mode: 'review', configured: true } }
  server.use(http.get('/api/v2/workflow-runs/history/graph', () => HttpResponse.json({
    workflow: { id: 'history', project_id: 'project-a', name: 'History', status: 'succeeded', graph: { edges: [legacy, saved] }, version: 1, created_by: 'user', created_at: '', updated_at: '' },
    nodes: [], edges: [{ ...legacy, id: `generated-${++reads}`, gate: { mode: 'automatic', configured: false } }, saved], layout: {},
  })))
  const first = await getWorkflowGraph('history')
  const second = await getWorkflowGraph('history')
  expect(first.edges).toEqual(second.edges)
  expect(first.edges[0]).toMatchObject({ legacy_connection: true })
  expect(first.edges[0].gate).toBeUndefined()
  expect(first.edges[1]).toEqual(saved)
})
