import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../test/mocks/handlers'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAppStore } from '../lib/store/appStore'
import { BotDetailPage } from './BotDetail'

vi.mock('../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => ({ projectId: 'project-bot', activeProject: { id: 'project-bot', name: 'PD1 binder', status: 'active' }, projectsLoading: false, projectsError: false, projectsQueryError: null, refetchProjects: vi.fn() }),
}))
vi.mock('../features/copilot/CopilotChat', () => ({ CopilotChat: () => <div>Scoped conversation</div> }))

const bot = (id: string, title: string, stance: string, extra: Record<string, unknown> = {}) => ({ id, title, title_zh: title, phase: 0, stance, summary: `${title} summary`, charter: `${title} charter: never invent evidence.`, capabilities: [], handoff: [], reviews: [], directs: [], reviewed_by: [], triggers: [], task_services: [], task_write_tools: {}, absorbs: [], ...extra })
const roster = [
  bot('conductor', 'Conductor', 'direct', { phase: -1, directs: ['researcher', 'planner'] }),
  bot('researcher', 'Researcher', 'produce', { phase: 1, handoff: ['planner'], reviewed_by: ['auditor'], task_services: ['brief', 'literature'], task_write_tools: { brief: [], literature: ['start_literature_search'] }, absorbs: ['librarian'] }),
  bot('planner', 'Planner', 'produce', { phase: 4, task_services: ['planning'] }),
  bot('auditor', 'Auditor', 'review', { phase: 9, reviews: ['researcher'] }),
]
const service = { id: 'literature', title: 'Research the evidence', title_zh: '调研与比较证据', deliverable: 'Traced excerpts and evidence gaps', deliverable_zh: '可追溯证据与缺口', capabilities: [], write_tools: [], steps: [] }
const run = (id: string, goal: string, botId: string | null, extra: Record<string, unknown> = {}) => ({ id, project_id: 'project-bot', goal, bot: botId, status: 'succeeded', allowed_tools: [], parent_run_id: null, turn_count: 1, cost_usd_cents: 0, version: 1, task_contract: { version: 1 }, outcome: { status: 'needs_input', summary: `${goal} delivery`, missing: [], steps: [] }, ...extra })
const runs = [run('task-1', 'Search PD1 literature', 'librarian'), run('task-2', 'Plan the route', 'planner'), run('task-3', 'Delegated search', 'researcher', { parent_run_id: 'task-0' })]
const handoff = (id: string, from: string, to: string, summary: string) => ({ id, project_id: 'project-bot', from_bot: from, to_bot: to, summary, claims: [], open_questions: [], refs: [], produced_by_run: 'task-1', created_at: '2026-09-14T00:00:00Z' })
let posts = 0

function renderAt(path: string) {
  window.location.hash = `#${path}`
  return renderWithProviders(<Routes>
    <Route path="/bots/:botId" element={<BotDetailPage />} />
    <Route path="/bots" element={<div>Research team overview</div>} />
  </Routes>)
}

beforeEach(() => {
  posts = 0
  sessionStorage.clear()
  useAppStore.setState({ language: 'en', appMode: 'application', copilotSessions: {}, copilotTaskDrafts: {} })
  server.use(
    http.get('/api/v2/copilot/bots', () => HttpResponse.json(roster)),
    http.get('/api/v2/copilot/task-services', () => HttpResponse.json([service])),
    http.get('/api/v2/copilot/projects/:projectId/agent-runs', () => HttpResponse.json({ items: runs, next_cursor: null })),
    http.get('/api/v2/copilot/projects/:projectId/handoffs', () => HttpResponse.json({ items: [
      handoff('h1', 'researcher', 'planner', 'Evidence is ready for routing'),
      handoff('h2', 'conductor', 'librarian', 'Find binding evidence'),
      handoff('h3', 'planner', 'auditor', 'Unrelated route review'),
    ], next_cursor: null })),
    http.get('/api/v2/copilot/agent-runs/:runId', ({ params }) => HttpResponse.json(runs.find((entry) => entry.id === params.runId))),
    http.get('/api/v2/copilot/agent-runs/:runId/turns', () => HttpResponse.json({ items: [], next_cursor: null })),
    http.post('/api/v2/copilot/agent-runs', () => { posts++; return HttpResponse.json({}, { status: 500 }) }),
  )
})
afterEach(() => { cleanup(); window.location.hash = '' })

describe('Bot responsibility page', () => {
  it('shows what an operator owns, holds and hands over, and scopes the conversation to it', async () => {
    renderAt('/bots/researcher?project=project-bot')
    expect(await screen.findByRole('heading', { level: 1, name: 'Researcher' })).toBeInTheDocument()
    expect(screen.getByText('Researcher charter: never invent evidence.')).toBeInTheDocument()
    expect(await screen.findByText('Owns “Research the evidence”: Traced excerpts and evidence gaps')).toBeInTheDocument()

    const tasks = screen.getByRole('region', { name: 'Tasks it holds' })
    expect(await within(tasks).findByRole('button', { name: /Search PD1 literature/ })).toBeInTheDocument()
    expect(within(tasks).getByRole('button', { name: /Delegated search/ })).toHaveTextContent('Delegated')
    expect(within(tasks).queryByRole('button', { name: /Plan the route/ })).not.toBeInTheDocument()

    expect(await within(screen.getByRole('region', { name: 'Handoffs' })).findByRole('group', { name: 'Received' })).toHaveTextContent('Find binding evidence')
    expect(screen.getByRole('group', { name: 'Sent' })).toHaveTextContent('Evidence is ready for routing')
    expect(screen.queryByText('Unrelated route review')).not.toBeInTheDocument()

    const relations = screen.getByRole('navigation', { name: 'Works with' })
    expect(within(relations).getByRole('link', { name: /Hands off to.*Planner/ })).toHaveAttribute('href', '#/bots/planner?project=project-bot')
    expect(within(relations).getByRole('link', { name: /Reviewed by.*Auditor/ })).toHaveAttribute('href', '#/bots/auditor?project=project-bot')
    expect(screen.getByRole('link', { name: 'Literature & evidence' })).toHaveAttribute('href', '#/research?project=project-bot&tab=evidence')
    expect(useAppStore.getState().copilotSessions['project-bot']?.bot).toBe('researcher')
  })

  it('assigns a task by preparing the composer, never by starting one', async () => {
    renderAt('/bots/researcher?project=project-bot')
    fireEvent.click(await screen.findByRole('button', { name: 'Assign “Research the evidence” to Researcher' }))
    expect(await screen.findByText('Research team overview')).toBeInTheDocument()
    expect(window.location.hash).toBe('#/bots?project=project-bot&view=tasks')
    expect(useAppStore.getState().copilotTaskDrafts['project-bot']).toMatchObject({ bot: 'researcher', service: 'literature', preview: true, writes: [] })
    expect(posts).toBe(0)
  })

  it('offers a conversation instead of assignment to an operator that owns no task', async () => {
    renderAt('/bots/auditor?project=project-bot')
    expect(await screen.findByText('Takes no guided tasks; works through conversation, handoffs and delegation.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Assign a task/ })).not.toBeInTheDocument()
    expect(within(screen.getByRole('navigation', { name: 'Works with' })).getByRole('link', { name: /Reviews.*Researcher/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Talk to Auditor' }))
    expect(await screen.findByText('Scoped conversation')).toBeInTheDocument()
    expect(window.location.hash).toContain('view=chat')
  })

  it('keeps assignment unavailable to a read-only viewer', async () => {
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'viewer' }))
    renderAt('/bots/researcher?project=project-bot')
    expect(await screen.findByRole('button', { name: 'Assign “Research the evidence” to Researcher' })).toBeDisabled()
  })

  it('opens a held task at a durable URL on the operator page', async () => {
    renderAt('/bots/researcher?project=project-bot')
    fireEvent.click(await screen.findByRole('button', { name: /Search PD1 literature/ }))
    expect(await screen.findByText('Search PD1 literature delivery')).toBeInTheDocument()
    expect(window.location.hash).toBe('#/bots/researcher?project=project-bot&run=task-1')
  })

  it('opens the operator that absorbed a retired id, keeping the task it was linked to', async () => {
    renderAt('/bots/librarian?project=project-bot&run=task-1')
    expect(await screen.findByText('Search PD1 literature delivery')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Researcher' })).toBeInTheDocument()
    expect(window.location.hash).toBe('#/bots/researcher?project=project-bot&run=task-1')
  })

  it('offers one assignment per recipe an operator owns', async () => {
    renderAt('/bots/researcher?project=project-bot')
    expect(await screen.findByRole('button', { name: 'Assign “Research the evidence” to Researcher' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Assign “brief” to Researcher' })).toBeInTheDocument()
  })

  it('says an operator is not in the roster rather than rendering an empty desk', async () => {
    renderAt('/bots/ghost?project=project-bot')
    expect(await screen.findByText('This Bot is not in the roster')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to the research team' })).toHaveAttribute('href', '#/bots?project=project-bot')
  })
})
