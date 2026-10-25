import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { CopilotReview } from './CopilotReview'

const context = vi.hoisted(() => ({ projectId: 'project-review' }))
vi.mock('../../lib/hooks/useProjectContext', () => ({ useProjectContext: () => context }))
const run = {
  id: 'run-review', project_id: 'project-review', goal: 'Review saved notes', bot: 'researcher',
  status: 'succeeded', max_turns: 24, turn_count: 2, max_cost_usd_cents: 0, cost_usd_cents: 0,
  allowed_tools: ['list_projects'], version: 3, task_contract: { version: 1, authorized_writes: [], service_kind: 'brief' },
  outcome: { summary: 'Review existing notes before proceeding.' },
}
beforeEach(() => {
  context.projectId = 'project-review'
  sessionStorage.clear()
  useAppStore.setState({ language: 'en', appMode: 'application' })
  server.use(
    http.get('/api/v2/copilot/projects/:projectId/agent-runs', () => HttpResponse.json({ items: [run], next_cursor: null })),
    http.get('/api/v2/copilot/agent-runs/:runId', () => HttpResponse.json(run)),
    http.get('/api/v2/copilot/agent-runs/:runId/turns', ({ request }) => {
      const later = new URL(request.url).searchParams.get('cursor')
      return HttpResponse.json({ items: later ? [{ id: 't2', role: 'assistant', content: 'Later recorded explanation.', sequence: 201 }] : [{
        id: 't1', role: 'assistant', content: 'Check existing records.', sequence: 1,
        tool_calls: [{ id: 'call-1', function: { name: 'list_projects', arguments: '{"limit":10}' } }],
      }], next_cursor: later ? null : 'page-2' })
    }),
  )
})
afterEach(cleanup)

describe('execution review', () => {
  it('exposes recorded limits, raw call parameters and later transcript pages without writing', async () => {
    let writes = 0
    server.use(http.post('/api/v2/copilot/*', () => { writes++; return new HttpResponse(null, { status: 500 }) }))
    renderWithProviders(<CopilotReview />)
    expect(screen.getByRole('link', { name: 'Open the project decision tree' })).toHaveAttribute('href', '#/research?project=project-review&tab=timeline')
    fireEvent.click(await screen.findByRole('button', { name: /Review saved notes/ }))
    const details = await screen.findByRole('button', { name: 'Technical details' })
    expect(details).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Record version')).not.toBeInTheDocument()
    fireEvent.click(details)
    const parameters = screen.getByRole('region', { name: 'Technical details' })
    expect(screen.getByRole('link', { name: 'Open workspace' })).toHaveAttribute('href', '#/bots?project=project-review&view=tasks&run=run-review')
    expect(within(parameters).getByText('0 US cents')).toBeInTheDocument()
    expect(within(parameters).getByText('Recorded messages').nextElementSibling).toHaveTextContent('2')
    expect(within(parameters).getByText('Configured turn limit').nextElementSibling).toHaveTextContent('24')
    expect(within(parameters).getByText('None')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Transcript' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Inspect call parameters' }))
    expect(screen.getByText(/"arguments":/)).toHaveTextContent('limit')
    fireEvent.click(screen.getByRole('button', { name: 'Load later records' }))
    expect(await screen.findByText('Later recorded explanation.')).toBeInTheDocument()
    expect(screen.getByText('Check existing records.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Load later records' })).not.toBeInTheDocument()
    expect(writes).toBe(0)
  })

  it('offers all run pages including delegated tasks and preserves loaded rows on failure', async () => {
    let fail = true
    server.use(http.get('/api/v2/copilot/projects/:projectId/agent-runs', ({ request }) => {
      if (!new URL(request.url).searchParams.has('cursor')) return HttpResponse.json({ items: [run], next_cursor: 'older' })
      if (fail) return HttpResponse.json({ detail: 'Try again' }, { status: 422 })
      return HttpResponse.json({ items: [{ ...run, id: 'child', goal: 'Delegated record', parent_run_id: run.id }], next_cursor: null })
    }))
    renderWithProviders(<CopilotReview />)
    fireEvent.click(await screen.findByRole('button', { name: 'Load more executions' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Loaded records are retained')
    expect(screen.getByRole('button', { name: /Review saved notes/ })).toBeInTheDocument()
    fail = false
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('button', { name: /Subtask.*Delegated record/ })).toBeInTheDocument()
  })

  it('requires a project instead of treating absent context as empty history', () => {
    context.projectId = ''
    renderWithProviders(<CopilotReview />)
    expect(screen.getByRole('link', { name: 'Choose a project' })).toHaveAttribute('href', '#/projects')
    expect(screen.queryByText(/No executions yet/)).not.toBeInTheDocument()
  })

  it('resets the selected execution when switching projects', async () => {
    const ui = renderWithProviders(<CopilotReview />)
    fireEvent.click(await screen.findByRole('button', { name: /Review saved notes/ }))
    await screen.findByRole('button', { name: 'Technical details' })
    context.projectId = 'empty-project'
    server.use(http.get('/api/v2/copilot/projects/empty-project/agent-runs', () => HttpResponse.json({ items: [], next_cursor: null })))
    ui.rerender(<CopilotReview />)
    expect(await screen.findByText(/No executions yet/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Technical details' })).not.toBeInTheDocument()
  })
})
