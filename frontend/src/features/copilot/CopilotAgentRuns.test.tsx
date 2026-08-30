import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { CopilotAgentRuns } from './CopilotAgentRuns'

/**
 * The panel over the durable substrate.
 *
 * What matters here is that it does not pretend to own the run: it starts one
 * and then reads the transcript back, and it treats a 412 on cancel as "the run
 * moved" rather than as a conflict to force through.
 */

vi.mock('../../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => ({ projectId: 'project-1', activeProject: null }),
}))

const RUN = {
  id: 'run-1',
  project_id: 'project-1',
  conversation_id: null,
  created_by: 'user-1',
  goal: 'Fold the top three candidates.',
  status: 'running',
  parent_run_id: null,
  allowed_tools: ['list_proteins'],
  max_turns: 12,
  turn_count: 2,
  cost_usd_cents: 4,
  subtree_cost_usd_cents: 4,
  max_cost_usd_cents: null,
  error: null,
  version: 3,
  created_at: '2026-08-26T00:00:00Z',
  updated_at: '2026-08-26T00:00:00Z',
}

function listReturns(runs: Record<string, unknown>[]) {
  server.use(
    http.get('/api/v2/copilot/projects/:projectId/agent-runs', () =>
      HttpResponse.json({ items: runs, next_cursor: null }),
    ),
  )
}

function runReturns(run: Record<string, unknown>, turns: Record<string, unknown>[] = []) {
  server.use(
    http.get('/api/v2/copilot/agent-runs/:runId', () => HttpResponse.json(run)),
    http.get('/api/v2/copilot/agent-runs/:runId/turns', () =>
      HttpResponse.json({ items: turns, next_cursor: null }),
    ),
  )
}

afterEach(() => cleanup())

describe('agent run panel', () => {
  it('starts a run and opens it, rather than waiting for an answer', async () => {
    // The run outlives the request that starts it, so there is nothing to await;
    // a panel that blocked on a result would block for hours.
    const bodies: unknown[] = []
    listReturns([])
    runReturns({ ...RUN, turn_count: 0 }, [])
    server.use(
      http.post('/api/v2/copilot/agent-runs', async ({ request }) => {
        bodies.push(await request.json())
        return HttpResponse.json({ run: RUN, operation_id: 'op-1' }, { status: 202 })
      }),
    )

    renderWithProviders(<CopilotAgentRuns />)
    fireEvent.change(screen.getByLabelText('Goal'), {
      target: { value: 'Fold the top three candidates.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Start run' }))

    await waitFor(() => expect(screen.getByText('Transcript')).toBeInTheDocument())
    expect(bodies[0]).toMatchObject({
      project_id: 'project-1',
      goal: 'Fold the top three candidates.',
      max_turns: 12,
    })
  })

  it('will not start a run with no goal', () => {
    listReturns([])
    renderWithProviders(<CopilotAgentRuns />)
    expect(screen.getByRole('button', { name: 'Start run' })).toBeDisabled()
  })

  it('shows the subagent total only when there are subagents', async () => {
    listReturns([
      { ...RUN, id: 'plain', cost_usd_cents: 4, subtree_cost_usd_cents: 4 },
      { ...RUN, id: 'parent', cost_usd_cents: 4, subtree_cost_usd_cents: 19 },
    ])

    renderWithProviders(<CopilotAgentRuns />)

    await waitFor(() => expect(screen.getByText(/19¢ with subagents/)).toBeInTheDocument())
    // The childless run says only its own cost: the longer label on equal
    // numbers would imply subagents that do not exist.
    expect(screen.getByText(/2 turns · 4¢$/)).toBeInTheDocument()
  })

  it('renders a tool-only turn by naming what it called', async () => {
    // An assistant turn that only requested tools has no prose, and an empty
    // bubble would read as a bug rather than as the step it was.
    listReturns([RUN])
    runReturns(RUN, [
      {
        id: 'turn-1',
        run_id: 'run-1',
        sequence: 0,
        role: 'assistant',
        content: '',
        tool_calls: [{ id: 'c1', function: { name: 'list_proteins' } }],
        tokens_in: 0,
        tokens_out: 0,
        cost_usd_cents: 1,
        created_at: '2026-08-26T00:00:00Z',
      },
    ])

    renderWithProviders(<CopilotAgentRuns />)
    fireEvent.click(await screen.findByRole('button', { name: /Fold the top three/ }))

    expect(await screen.findByText('called list_proteins')).toBeInTheDocument()
  })

  it('reports a waiting run as waiting on work that outlives the request', async () => {
    listReturns([{ ...RUN, status: 'awaiting_tasks' }])
    runReturns({ ...RUN, status: 'awaiting_tasks' })

    renderWithProviders(<CopilotAgentRuns />)
    fireEvent.click(await screen.findByRole('button', { name: /Fold the top three/ }))

    expect(
      await screen.findByText('Waiting on work that outlives this request.'),
    ).toBeInTheDocument()
  })

  it('offers cancel only while the run can still be stopped', async () => {
    listReturns([{ ...RUN, status: 'succeeded' }])
    runReturns({ ...RUN, status: 'succeeded' })

    renderWithProviders(<CopilotAgentRuns />)
    fireEvent.click(await screen.findByRole('button', { name: /Fold the top three/ }))

    await waitFor(() => expect(screen.getByText('Transcript')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument()
  })

  it('sends the version when cancelling and reloads on a 412', async () => {
    // 412 here is never an overwrite prompt: the run moved on its own, usually
    // by finishing before the click landed.
    listReturns([RUN])
    runReturns(RUN)
    const headers: (string | null)[] = []
    server.use(
      http.post('/api/v2/copilot/agent-runs/:runId/cancellations', ({ request }) => {
        headers.push(request.headers.get('If-Match'))
        return HttpResponse.json({ detail: 'stale' }, { status: 412 })
      }),
    )

    renderWithProviders(<CopilotAgentRuns />)
    fireEvent.click(await screen.findByRole('button', { name: /Fold the top three/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect(headers).toEqual(['W/"3"']))
  })

  it('goes back to the list without losing it', async () => {
    listReturns([RUN])
    runReturns(RUN)

    renderWithProviders(<CopilotAgentRuns />)
    fireEvent.click(await screen.findByRole('button', { name: /Fold the top three/ }))
    fireEvent.click(await screen.findByRole('button', { name: /Back to runs/ }))

    const list = await screen.findByRole('list')
    expect(within(list).getByText(/Fold the top three/)).toBeInTheDocument()
  })
})
