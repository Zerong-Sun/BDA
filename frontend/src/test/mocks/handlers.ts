import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

export const handlers = [
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
