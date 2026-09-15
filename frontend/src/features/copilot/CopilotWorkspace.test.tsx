import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { CopilotWorkspace } from './CopilotWorkspace'
import { deliveryState, suggestService } from './taskPresentation'
import { useIsMutating } from '@tanstack/react-query'
import type { AgentRun } from '../../lib/api/agentRuns'

vi.mock('../../lib/hooks/useProjectContext', () => ({ useProjectContext: () => ({ projectId: 'project-task', activeProject: null }) }))
vi.mock('./CopilotChat', () => ({ CopilotChat: ({ initialQuestion }: { initialQuestion?: string }) => <div>Question: {initialQuestion}</div> }))
const service = { id: 'literature', title: 'Research the evidence', title_zh: '调研与比较证据', deliverable: 'Traced excerpts and evidence gaps', deliverable_zh: '可追溯证据与缺口', capabilities: ['research-read'], write_tools: ['start_literature_search', 'create_knowledge_draft'], steps: [{ id: 'excerpts', title: 'Read traced excerpts', title_zh: '读取来源', tools: ['get_reference_content'] }] }
const planningService = { id: 'planning', title: 'Prepare an experimental plan', title_zh: '制定实验方案', deliverable: 'Routes and a plan for review', deliverable_zh: '待审核方案', capabilities: ['workflow-planning'], write_tools: [], steps: [{ id: 'routes', title: 'Compare registered routes', title_zh: '比较已注册路线', tools: ['plan_workflow_route'] }] }
const bot = (id: string, title: string, stance: string, extra: Record<string, unknown> = {}) => ({ id, title, title_zh: title, phase: 0, stance, summary: `${title} summary`, charter: '', capabilities: [], handoff: [], reviews: [], directs: [], reviewed_by: [], triggers: [], task_services: [], task_write_tools: {}, absorbs: [], ...extra })
// The literature recipe offers note authoring; this fixture's owner is not
// granted it, so the composer must not offer it. `librarian` is a retired id the
// researcher absorbed, and tasks recorded under it are still the researcher's.
const roster = [
  bot('researcher', 'Researcher', 'produce', { phase: 1, reviewed_by: ['auditor'], triggers: ['literature'], task_services: ['literature'], task_write_tools: { literature: ['start_literature_search'] }, absorbs: ['librarian'] }),
  bot('planner', 'Planner', 'produce', { phase: 4, triggers: ['route'], task_services: ['planning'], task_write_tools: { planning: [] } }),
  bot('auditor', 'Auditor', 'review', { phase: 9, reviews: ['researcher'] }),
]
const run = { id: 'task-1', project_id: 'project-task', goal: 'Research PD1', bot: 'librarian', status: 'succeeded', allowed_tools: [], parent_run_id: null, turn_count: 2, cost_usd_cents: 0, version: 1,
  task_contract: { version: 1, service_kind: 'literature' }, outcome: { status: 'needs_input', summary: 'Target identity is missing.', missing: ['Target identity'], next_action: 'Provide an identifier.', steps: [] } }
function handlers(eligible: string[] = ['literature']) {
  server.use(
    http.get('/api/v2/copilot/task-services', () => HttpResponse.json([service, planningService])),
    http.get('/api/v2/copilot/bots', () => HttpResponse.json(roster)),
    http.get('/api/v2/copilot/projects/:projectId/task-readiness', () => HttpResponse.json({ model: 'test-model', checks: {}, eligible_services: eligible })),
    http.get('/api/v2/copilot/projects/:projectId/agent-runs', () => HttpResponse.json({ items: [], next_cursor: null })),
    http.get('/api/v2/copilot/agent-runs/:runId', () => HttpResponse.json(run)),
    http.get('/api/v2/copilot/agent-runs/:runId/turns', () => HttpResponse.json({ items: [], next_cursor: null })),
  )
}
beforeEach(() => { sessionStorage.clear(); useAppStore.setState({ language: 'en', copilotDraft: '', copilotTaskDrafts: {}, appMode: 'application' }); handlers() })
afterEach(cleanup)

describe('task-centered Copilot', () => {
  it('does not navigate back when task startup completes after leaving the workspace', async () => {
    let release!: () => void
    const responseReady = new Promise<void>((resolve) => { release = resolve })
    server.use(http.post('/api/v2/copilot/agent-runs', async () => {
      await responseReady
      return HttpResponse.json({ run, operation_id: 'op' }, { status: 202 })
    }))
    function Pending() { return <span>Pending mutations: {useIsMutating()}</span> }
    const navigate = vi.fn()
    const ui = renderWithProviders(<><CopilotWorkspace initialGoal="Review sources" initialService="literature" onRunChange={navigate} /><Pending /></>)
    fireEvent.click(await screen.findByRole('button', { name: 'Start this plan' }))
    await screen.findByText('Pending mutations: 1')
    ui.rerender(<Pending />)
    release()
    await screen.findByText('Pending mutations: 0')
    expect(navigate).not.toHaveBeenCalled()
  })
  it.each(['viewer', 'demo'])('blocks task execution and delivery writes in %s mode', async (mode) => {
    if (mode === 'viewer') sessionStorage.setItem('bda_user', JSON.stringify({ role: 'viewer' }))
    else useAppStore.setState({ appMode: 'demo' })
    server.use(http.get('/api/v2/copilot/projects/:projectId/agent-runs', () => HttpResponse.json({ items: [run] })))
    renderWithProviders(<CopilotWorkspace initialGoal="Review sources" initialService="literature" />)
    expect(await screen.findByRole('button', { name: 'Start this plan' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: /Research PD1/ }))
    expect(await screen.findByRole('button', { name: 'Continue this task' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Save as a plan for review' })).toBeDisabled()
    expect(screen.getByLabelText('Add information or revise the request')).toBeDisabled()
  })
  it('retains a reviewed task draft on remount without starting a task', async () => {
    const rendered = renderWithProviders(<CopilotWorkspace rememberDraft />)
    fireEvent.change(screen.getByLabelText('Task goal'), { target: { value: 'Research existing evidence' } })
    fireEvent.click(await screen.findByRole('button', { name: /^Researcher/ }))
    fireEvent.click(await screen.findByRole('checkbox', { name: 'Allow external literature search and ingestion' }))
    rendered.unmount()
    renderWithProviders(<CopilotWorkspace rememberDraft />)
    expect(screen.getByLabelText('Task goal')).toHaveValue('Research existing evidence')
    expect(await screen.findByRole('checkbox', { name: 'Allow external literature search and ingestion' })).toBeChecked()
    expect(screen.getByRole('button', { name: 'Start this plan' })).toBeInTheDocument()
  })
  it('blocks invalid budgets and turn limits with a visible correction', async () => {
    renderWithProviders(<CopilotWorkspace initialGoal="Research PD1" initialService="literature" />)
    const start = await screen.findByRole('button', { name: 'Start this plan' })
    fireEvent.click(screen.getByRole('button', { name: 'Advanced options and direct editing' }))
    const budget = screen.getByLabelText('Estimated model budget (cents, optional)')
    for (const value of ['-1', '1.5', '1000001']) {
      fireEvent.change(budget, { target: { value } })
      expect(start).toBeDisabled()
      expect(screen.getByRole('alert')).toHaveTextContent('Budget must be a whole number')
    }
    fireEvent.change(budget, { target: { value: '0' } })
    expect(start).toBeEnabled()
    fireEvent.change(screen.getByLabelText('Turn limit'), { target: { value: '0' } })
    expect(start).toBeDisabled()
    expect(screen.getByRole('alert')).toHaveTextContent('Turn limit must be a whole number')
  })
  it('recovers the unavailable service list without losing the request', async () => {
    server.use(http.get('/api/v2/copilot/task-services', () => HttpResponse.json({ detail: 'Service unavailable' }, { status: 422 })))
    renderWithProviders(<CopilotWorkspace initialGoal="Research PD1" />)
    const reload = await screen.findByRole('button', { name: 'Reload task workspace' })
    handlers()
    fireEvent.click(reload)
    expect(await screen.findByRole('button', { name: /Researcher.*Research the evidence/ })).toBeEnabled()
    expect(screen.getByLabelText('Task goal')).toHaveValue('Research PD1')
  })
  it('explains an unavailable owner roster once and recovers it without losing the goal', async () => {
    server.use(http.get('/api/v2/copilot/bots', () => HttpResponse.json({ detail: 'Roster unavailable' }, { status: 422 })))
    renderWithProviders(<CopilotWorkspace initialGoal="Research PD1" />)
    expect(await screen.findByText('The task owner roster could not be loaded, so work cannot be assigned yet.')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    handlers()
    fireEvent.click(screen.getByRole('button', { name: 'Reload task workspace' }))
    expect(await screen.findByRole('button', { name: /^Researcher/ })).toBeEnabled()
    expect(screen.getByLabelText('Task goal')).toHaveValue('Research PD1')
  })
  it('shows a reviewable task scope and sends only explicitly checked writes', async () => {
    const bodies: unknown[] = []
    server.use(http.post('/api/v2/copilot/agent-runs', async ({ request }) => { bodies.push(await request.json()); return HttpResponse.json({ run, operation_id: 'op' }, { status: 202 }) }))
    renderWithProviders(<CopilotWorkspace />)
    fireEvent.change(screen.getByLabelText('Task goal'), { target: { value: 'Research PD1' } })
    fireEvent.click(await screen.findByRole('button', { name: /^Researcher/ }))
    expect(screen.getByRole('heading', { name: 'Researcher owns: Research the evidence' })).toBeInTheDocument()
    expect(screen.getByText('Reviewed by Auditor')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: 'Allow saving research notes for review' })).not.toBeInTheDocument()
    const search = screen.getByRole('checkbox', { name: 'Allow external literature search and ingestion' })
    expect(search).not.toBeChecked()
    fireEvent.click(search)
    fireEvent.click(screen.getByRole('button', { name: 'Start this plan' }))
    await screen.findByText('Target identity is missing.')
    expect(bodies[0]).toMatchObject({ bot: 'researcher', service_kind: 'literature', authorized_writes: ['start_literature_search'] })
    expect(screen.getAllByText('Needs your input').length).toBeGreaterThan(0)
    expect(screen.queryByText('Draft ready for review')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Transcript' })).toHaveAttribute('aria-expanded', 'false')
  })
  it('requires current task checks and explains failed checks', async () => {
    handlers([])
    server.use(http.post('/api/v2/copilot/projects/:projectId/config/assessments', () => HttpResponse.json({ model: 'test-model', checks: { tools: false }, checked_at: '2026-09-07', eligible_services: [] })))
    renderWithProviders(<CopilotWorkspace initialGoal="Research PD1" initialService="literature" />)
    expect(await screen.findByRole('button', { name: 'Start this plan' })).toBeDisabled()
    fireEvent.click(await screen.findByRole('button', { name: 'Check model task capabilities' }))
    await screen.findByText('tools: ×')
    expect(screen.getByRole('button', { name: 'Start this plan' })).toBeDisabled()
  })
  it('answers a simple question without asking the user to select an execution engine', async () => {
    renderWithProviders(<CopilotWorkspace />)
    fireEvent.change(screen.getByLabelText('Task goal'), { target: { value: 'What is a workflow?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await screen.findByText('Question: What is a workflow?')
  })
  it('continues a stopped task using its current version and retains its scope', async () => {
    let body: unknown; let match: string | null = null
    server.use(http.get('/api/v2/copilot/projects/:projectId/agent-runs', () => HttpResponse.json({ items: [run] })),
      http.post('/api/v2/copilot/agent-runs/:runId/continuations', async ({ request }) => { body = await request.json(); match = request.headers.get('If-Match'); return HttpResponse.json({ run, operation_id: 'op' }, { status: 202 }) }))
    renderWithProviders(<CopilotWorkspace />)
    fireEvent.click(await screen.findByRole('button', { name: /Research PD1/ }))
    fireEvent.change(await screen.findByLabelText('Add information or revise the request'), { target: { value: 'Use human PD1.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Continue this task' }))
    await waitFor(() => expect(body).toEqual({ message: 'Use human PD1.' }))
    expect(match).toBe('W/"1"')
  })
  it('suggests an owner from the goal and lets the person reassign it', async () => {
    renderWithProviders(<CopilotWorkspace />)
    fireEvent.change(screen.getByLabelText('Task goal'), { target: { value: 'Compare the route options for PD1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(await screen.findByRole('heading', { name: 'Planner owns: Prepare an experimental plan' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^Researcher/ }))
    expect(screen.getByRole('heading', { name: 'Researcher owns: Research the evidence' })).toBeInTheDocument()
    // A reviewer judges delivered work; it is never offered as a task owner.
    expect(within(screen.getByRole('group', { name: 'Task owner' })).queryByRole('button', { name: /^Auditor/ })).not.toBeInTheDocument()
  })
  it('resolves a page request for a kind of work to the operator that owns it', async () => {
    renderWithProviders(<CopilotWorkspace initialGoal="Review sources" initialService="literature" />)
    expect(await screen.findByRole('heading', { name: 'Researcher owns: Research the evidence' })).toBeInTheDocument()
  })
  it('groups tasks under the operator that owns them', async () => {
    server.use(http.get('/api/v2/copilot/projects/:projectId/agent-runs', () => HttpResponse.json({ items: [{ ...run, id: 'task-2', goal: 'Older task', bot: null }, run], next_cursor: null })))
    renderWithProviders(<CopilotWorkspace />)
    const librarian = await screen.findByRole('group', { name: 'Researcher' })
    expect(within(librarian).getByRole('button', { name: /Research PD1/ })).toBeInTheDocument()
    expect(within(screen.getByRole('group', { name: 'No assigned owner' })).getByRole('button', { name: /Older task/ })).toBeInTheDocument()
    const groups = screen.getAllByRole('group').map((group) => group.getAttribute('aria-label'))
    expect(groups.indexOf('Researcher')).toBeLessThan(groups.indexOf('No assigned owner'))
  })
  it('never presents legacy execution success as verified goal completion', () => {
    expect(deliveryState({ status: 'succeeded' } as AgentRun)).toBe('review_required')
    expect(suggestService('检查失败的作业')).toBe('execution')
    expect(suggestService('帮我调研文献')).toBe('literature')
  })
})
