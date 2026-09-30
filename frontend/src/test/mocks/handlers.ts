import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

// Shared read-only empty states use the same paginated contract as the API.
// Tests that need populated data or failures override these exact routes with server.use.
const emptyPageRoutes = [
  '/api/v2/projects/library',
  '/api/v2/registry/compute-nodes',
  '/api/v2/registry/model-plugins',
  '/api/v2/registry/method-plugins',
  '/api/v2/projects/:projectId/candidates',
  '/api/v2/artifacts',
  '/api/v2/projects/:projectId/workflow-runs',
  '/api/v2/projects/:projectId/research-findings',
  '/api/v2/projects/:projectId/experiment-results',
  '/api/v2/projects/:projectId/proteins',
  '/api/v2/jobs',
  '/api/v2/operations',
]

export const handlers = [
  ...emptyPageRoutes.map((route) => http.get(route, () => HttpResponse.json({ items: [], next_cursor: null }))),
  http.get('/api/v2/research-packages', () => HttpResponse.json([])),
  http.get('/api/v2/health/ready', () => HttpResponse.json({ status: 'ok', checks: {} })),
  http.get('/api/v2/projects/:projectId/primary-target', () => HttpResponse.json({ error_code: 'target_not_found', title: 'Project has no primary target', status: 404 }, { status: 404 })),
  http.get('/api/v2/projects/:projectId/hotspot-sets', () => HttpResponse.json({ items: [] })),
  http.get('/api/v2/workflow-runs/:workflowId/gates', () => HttpResponse.json({ items: [] })),
  http.get('/api/v2/jobs/:jobId/events', () => new HttpResponse('', { headers: { 'Content-Type': 'text/event-stream' } })),
  http.get('/api/v2/operations/:operationId/events', () => new HttpResponse('', { headers: { 'Content-Type': 'text/event-stream' } })),
  http.get('/api/v2/copilot/projects/:projectId/events', () => new HttpResponse('', { headers: { 'Content-Type': 'text/event-stream' } })),
  http.get('/api/v2/health/live', () =>
    HttpResponse.json({ status: 'ok' }),
  ),
  http.get('/api/v2/projects', () =>
    HttpResponse.json({ items: [], next_cursor: null }),
  ),
  http.post('/api/v2/auth/token', async ({ request }) => {
    const body = (await request.json()) as { username?: string; password?: string }
    if (body.username && body.password) {
      return HttpResponse.json({
          access_token: 'test-token',
          token_type: 'bearer',
          user: { id: 'user_test', username: body.username, role: 'admin', display_name: 'Test User' },
        },
      )
    }
    return HttpResponse.json({ message: 'invalid_credentials' }, { status: 401 })
  }),
  http.delete('/api/v2/projects/proj_delete_test', () =>
    HttpResponse.json({
        id: 'proj_delete_test',
        deleted: true,
        retention_days: 30,
      }),
  ),
  http.get('/api/v2/copilot/bots', () => HttpResponse.json([])),
  http.get('/api/v2/projects/:projectId/access', ({ params }) => HttpResponse.json({ project_id: params.projectId, role: 'owner', permissions: { read: true, write: true, compute: true, autopilot: true } })),
  http.get('/api/v2/copilot/projects/:projectId/config', () =>
    HttpResponse.json({
        settings: {
          llm_api_base: 'https://api.openai.com/v1',
          llm_model: 'gpt-4o-mini',
          system_prompt: 'test prompt',
        },
        api_key_configured: true,
        version: 1,
        llm_provider_id: null,
      }),
  ),
]

export const server = setupServer(...handlers)
