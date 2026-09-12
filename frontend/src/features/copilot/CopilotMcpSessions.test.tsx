import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useToastStore } from '../../components/ui/toastStore'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { CopilotMcpSessions } from './CopilotMcpSessions'

/**
 * The panel that hands out MCP grants.
 *
 * Two behaviours here are the reason it exists rather than being a link to the
 * API: the token is shown once and said to be unrecoverable, and a grant whose
 * bound run has finished is presented as read-only rather than as still holding
 * the writes it was issued with. Both are facts the server decides; the panel's
 * job is not to contradict them.
 */

vi.mock('../../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => ({ projectId: 'project-1', activeProject: null }),
}))

const SESSION = {
  id: 'mcp-1',
  project_id: 'project-1',
  agent_run_id: null,
  issued_by: 'user-1',
  label: 'Claude Desktop',
  granted_capabilities: ['research-read'],
  mandate_live: false,
  tools: ['search_research', 'research_overview'],
  write_tools: [],
  expires_at: '2999-01-01T00:00:00Z',
  revoked_at: null,
  last_used_at: null,
  call_count: 0,
  version: 1,
  created_at: '2026-09-11T00:00:00Z',
  updated_at: '2026-09-11T00:00:00Z',
}

function listReturns(sessions: Record<string, unknown>[]) {
  server.use(
    http.get('/api/v2/copilot/projects/:projectId/mcp-sessions', () =>
      HttpResponse.json({ items: sessions, next_cursor: null }),
    ),
    http.get('/api/v2/copilot/projects/:projectId/agent-runs', () =>
      HttpResponse.json({ items: [], next_cursor: null }),
    ),
    http.get('/api/v2/copilot/skills', () =>
      HttpResponse.json([
        { id: 'research-read', title: 'Research evidence', description: '', execution_mode: 'read' },
      ]),
    ),
  )
}

beforeEach(() => useToastStore.getState().clear())
afterEach(() => cleanup())

describe('MCP session panel', () => {
  it('shows the token once, and says it cannot be shown again', async () => {
    listReturns([])
    server.use(
      http.post('/api/v2/copilot/mcp-sessions', () =>
        HttpResponse.json(
          { session: SESSION, token: 'raw-token-value', endpoint: '/mcp' },
          { status: 201 },
        ),
      ),
    )
    renderWithProviders(<CopilotMcpSessions />)

    fireEvent.change(await screen.findByPlaceholderText(/Claude Desktop/i), {
      target: { value: 'My laptop' },
    })
    fireEvent.click(await screen.findByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: /issue session/i }))

    expect(await screen.findByDisplayValue('raw-token-value')).toBeInTheDocument()
    expect(screen.getByText(/only a hash is stored/i)).toBeInTheDocument()
  })

  it('reports a grant with no live mandate as read-only', async () => {
    listReturns([SESSION])
    renderWithProviders(<CopilotMcpSessions />)

    expect(await screen.findByText('Claude Desktop')).toBeInTheDocument()
    expect(screen.getByText(/read-only/i)).toBeInTheDocument()
    expect(screen.getByText(/2 tool/i)).toBeInTheDocument()
  })

  it('says so when a bound run has spent its mandate', async () => {
    listReturns([{ ...SESSION, agent_run_id: 'run-1', mandate_live: false, write_tools: [] }])
    renderWithProviders(<CopilotMcpSessions />)

    expect(await screen.findByText(/bound run has finished/i)).toBeInTheDocument()
  })

  it('treats a 412 on revoke as the row having moved, not as a failure to force', async () => {
    listReturns([SESSION])
    server.use(
      http.post('/api/v2/copilot/mcp-sessions/:sessionId/revocations', () =>
        HttpResponse.json(
          { type: 'about:blank', title: 'Conflict', status: 412, error_code: 'version_conflict' },
          { status: 412 },
        ),
      ),
    )
    renderWithProviders(<CopilotMcpSessions />)

    fireEvent.click(await screen.findByRole('button', { name: /^revoke$/i }))
    // The panel keeps the row and says it moved. Asserting on the toast store
    // rather than the rendered toast keeps this about the decision, not about
    // where the notification is mounted.
    await waitFor(() =>
      expect(useToastStore.getState().message).toMatch(/changed while you were looking at it/i),
    )
    expect(useToastStore.getState().tone).toBe('info')
  })

  it('offers no revoke control for a grant that is already spent', async () => {
    listReturns([{ ...SESSION, revoked_at: '2026-09-11T01:00:00Z' }])
    renderWithProviders(<CopilotMcpSessions />)

    expect(await screen.findByText('Revoked')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^revoke$/i })).not.toBeInTheDocument()
  })
})
