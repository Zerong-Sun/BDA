import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { CopilotWorkspace } from './CopilotWorkspace'
import { deliveryState, suggestService } from './taskPresentation'
import type { AgentRun } from '../../lib/api/agentRuns'

vi.mock('../../lib/hooks/useProjectContext', () => ({ useProjectContext: () => ({ projectId: 'project-task', activeProject: null }) }))
vi.mock('./CopilotChat', () => ({ CopilotChat: ({ initialQuestion }: { initialQuestion?: string }) => <div>Question: {initialQuestion}</div> }))
const service = { id: 'literature', title: 'Research the evidence', title_zh: '调研与比较证据', deliverable: 'Traced excerpts and evidence gaps', deliverable_zh: '可追溯证据与缺口', capabilities: ['research-read'], write_tools: ['start_literature_search', 'create_knowledge_draft'], steps: [{ id: 'excerpts', title: 'Read traced excerpts', title_zh: '读取来源', tools: ['get_reference_content'] }] }
const run = { id: 'task-1', project_id: 'project-task', goal: 'Research PD1', status: 'succeeded', allowed_tools: [], parent_run_id: null, turn_count: 2, cost_usd_cents: 0, version: 1,
  task_contract: { version: 1, service_kind: 'literature' }, outcome: { status: 'needs_input', summary: 'Target identity is missing.', missing: ['Target identity'], next_action: 'Provide an identifier.', steps: [] } }
function handlers(eligible: string[] = ['literature']) {
  server.use(
    http.get('/api/v2/copilot/task-services', () => HttpResponse.json([service])),
    http.get('/api/v2/copilot/projects/:projectId/task-readiness', () => HttpResponse.json({ model: 'test-model', checks: {}, eligible_services: eligible })),
    http.get('/api/v2/copilot/projects/:projectId/agent-runs', () => HttpResponse.json({ items: [], next_cursor: null })),
    http.get('/api/v2/copilot/agent-runs/:runId', () => HttpResponse.json(run)),
    http.get('/api/v2/copilot/agent-runs/:runId/turns', () => HttpResponse.json({ items: [], next_cursor: null })),
  )
}
beforeEach(() => { useAppStore.setState({ language: 'en', copilotDraft: '', appMode: 'application' }); handlers() })
afterEach(cleanup)

describe('task-centered Copilot', () => {
  it('shows a reviewable task scope and sends only explicitly checked writes', async () => {
    const bodies: unknown[] = []
    server.use(http.post('/api/v2/copilot/agent-runs', async ({ request }) => { bodies.push(await request.json()); return HttpResponse.json({ run, operation_id: 'op' }, { status: 202 }) }))
    renderWithProviders(<CopilotWorkspace />)
    fireEvent.change(screen.getByLabelText('Task goal'), { target: { value: 'Research PD1' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Research the evidence' }))
    expect(screen.getByRole('checkbox', { name: 'Allow external literature search and ingestion' })).not.toBeChecked()
    fireEvent.click(screen.getByRole('checkbox', { name: 'Allow saving research notes for review' }))
    fireEvent.click(screen.getByRole('button', { name: 'Start this plan' }))
    await screen.findByText('Target identity is missing.')
    expect(bodies[0]).toMatchObject({ service_kind: 'literature', authorized_writes: ['create_knowledge_draft'] })
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
  it('never presents legacy execution success as verified goal completion', () => {
    expect(deliveryState({ status: 'succeeded' } as AgentRun)).toBe('review_required')
    expect(suggestService('检查失败的作业')).toBe('execution')
    expect(suggestService('帮我调研文献')).toBe('literature')
  })
})
