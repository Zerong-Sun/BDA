import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { AgentRunDetail, CopilotAgentRuns } from './CopilotAgentRuns'
import { useAppStore } from '../../lib/store/appStore'

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

afterEach(() => { cleanup(); vi.unstubAllGlobals() })
beforeEach(() => { sessionStorage.clear(); window.location.hash = '#/'; useAppStore.setState({ appMode: 'application', language: 'en', copilotTaskDrafts: {} }) })

describe('agent run panel', () => {
  it('copies collapsed sections with remaining work and incomplete review, and reports clipboard failure', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const section = 'Evidence requiring verification. '.repeat(50)
    runReturns({ ...RUN, status: 'succeeded', outcome: { summary: 'Draft', status: 'partial', sections: { limitations: section }, missing: ['Sample mapping absent'], next_action: 'Find original records', scientific_review: 'unavailable' } })
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Copy full report' }))
    await screen.findByText('Full report copied, including remaining work and review notes.')
    const copied = writeText.mock.calls[0][0]
    for (const expected of [section, 'Delivery status: Partially delivered (partial)', 'Sample mapping absent', 'Find original records', 'Automated factual review: Incomplete', 'does not constitute scientific validation or human approval']) expect(copied).toContain(expected)
    writeText.mockRejectedValueOnce(new Error('denied'))
    fireEvent.click(screen.getByRole('button', { name: 'Copy full report' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Clipboard unavailable')
  })

  it('refreshes saved records without submitting or discarding the follow-up draft', async () => {
    let reads = 0
    let writes = 0
    runReturns({ ...RUN, status: 'failed' })
    server.use(http.get('/api/v2/copilot/agent-runs/:runId', () => { reads++; return HttpResponse.json({ ...RUN, status: 'failed' }) }), http.post('/api/v2/copilot/agent-runs/:runId/continuations', () => { writes++; return HttpResponse.json({}) }))
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    const field = await screen.findByLabelText('Add information or revise the request')
    fireEvent.change(field, { target: { value: 'Keep this draft' } })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Refresh records' })).toBeEnabled())
    const before = reads
    fireEvent.click(screen.getByRole('button', { name: 'Refresh records' }))
    await waitFor(() => expect(reads).toBeGreaterThan(before))
    expect(field).toHaveValue('Keep this draft')
    expect(writes).toBe(0)
  })

  it('separates execution, review and report count without hiding a short report', async () => {
    useAppStore.setState({ language: 'zh' })
    runReturns({ ...RUN, status: 'succeeded', outcome: {
      status: 'partial', summary: '摘要🧬', sections: { '证据': '待核验' }, missing: ['映射缺失'],
      next_action: '查原记录', scientific_review: 'automated_review_completed',
    } })
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    const delivery = await screen.findByRole('region', { name: '任务交付' })
    expect(within(delivery).getByText('执行结束')).toBeVisible()
    expect(within(delivery).getByText('已完成', { exact: true })).toBeVisible()
    expect(within(delivery).getByText('16', { exact: true })).toBeVisible()
    expect(within(delivery).getByText('待核验')).toBeVisible()
    expect(within(delivery).getByText('映射缺失')).toBeVisible()
  })

  it('localizes a failed generation without presenting the error as a report or completed review', async () => {
    useAppStore.setState({ language: 'zh' })
    const error = 'Model completion exceeded the 180-second total deadline; no response was accepted.'
    runReturns({ ...RUN, status: 'failed', error, outcome: {
      status: 'blocked', summary: '', missing: [error], next_action: 'Review the failure and continue after correcting the cause.',
    } })
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    expect(await screen.findByText('执行失败')).toBeVisible()
    expect(screen.getByText('未记录完成')).toBeVisible()
    expect(screen.getByText('尚无报告')).toBeVisible()
    expect(screen.getByRole('alert')).toHaveTextContent('模型在 180 秒内未完成回复，本次未生成可接受的报告。')
    expect(screen.getByText('先排查失败原因，修正后再继续任务。')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: '查看原始错误' }))
    expect(screen.getByText(error)).toBeVisible()
  })

  it('keeps a long request accessible without placing it ahead of the report', async () => {
    const goal = 'Read the existing evidence and keep uncertainty explicit. '.repeat(10)
    runReturns({ ...RUN, goal, status: 'succeeded', outcome: { summary: 'Final report', status: 'partial' } })
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    expect(await screen.findByText('Final report')).toBeVisible()
    const request = screen.getByRole('button', { name: 'Full task request' })
    expect(request).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(request)
    expect(screen.getByText(goal.trim())).toBeVisible()
  })

  it('keeps the execution failure visible when a historical outcome is malformed', async () => {
    runReturns({ ...RUN, status: 'failed', error: 'Provider unavailable', outcome: { sections: [] } })
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    expect(await screen.findByText('Invalid task result. Reload the task.')).toBeVisible()
    expect(screen.getByText('Provider unavailable')).toBeVisible()
  })

  it.each([
    ['en', 'The review result failed delivery validation. The saved draft still needs review.'],
    ['zh', '复核结果未通过交付校验，已保存的草稿仍需审核。'],
  ] as const)('describes rejected review delivery without assuming a format or citation error in %s', async (language, label) => {
    useAppStore.setState({ language })
    runReturns({ ...RUN, status: 'succeeded', outcome: {
      status: 'review_required', summary: 'Saved draft', scientific_review: 'unavailable',
      scientific_review_error: 'invalid_review_delivery', missing: ['scientific_review_unavailable'],
    } })
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    expect(await screen.findByText(label)).toBeInTheDocument()
    expect(screen.getByText('Saved draft')).toBeInTheDocument()
    expect(screen.queryByText(/Automated factual review completed|自动事实复核已完成/)).not.toBeInTheDocument()
  })

  it.each([
    ['en', 'Automated factual review completed. This does not constitute scientific validation or human approval.'],
    ['zh', '自动事实复核已完成；这不代表科研验证或人工批准。'],
  ] as const)('shows the completed factual pass without claiming approval in %s', async (language, label) => {
    useAppStore.setState({ language })
    runReturns({ ...RUN, status: 'succeeded', outcome: {
      status: 'review_required', summary: 'Saved draft', scientific_review: 'automated_review_completed',
    } })
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    expect(await screen.findByText(label)).toBeInTheDocument()
    expect(screen.getAllByText(language === 'zh' ? '需要审核' : 'Needs review').length).toBeGreaterThan(0)
  })

  it.each([undefined, 'unavailable', 'unknown'])('does not claim a completed factual pass for %s', async (scientific_review) => {
    runReturns({ ...RUN, status: 'succeeded', outcome: {
      status: 'review_required', summary: 'Saved draft', scientific_review,
    } })
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    expect(await screen.findByText('Saved draft')).toBeInTheDocument()
    expect(screen.queryByText(/Automated factual review completed/)).not.toBeInTheDocument()
  })

  it('shows actionable output-limit and delivery-length failures without claiming scientific approval', async () => {
    runReturns({ ...RUN, status: 'succeeded', outcome: {
      status: 'review_required', summary: 'Saved draft', scientific_review_error: 'llm_output_truncated',
      missing: ['scientific_review_unavailable', 'delivery_length_exceeded'],
    } })
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    expect(await screen.findByText('Saved draft')).toBeInTheDocument()
    expect(screen.getByText('Review exceeded the model output limit. Shorten the scope or adjust the model limit and retry.')).toBeInTheDocument()
    expect(screen.getByText('The delivery exceeds the requested character limit and needs shortening.')).toBeInTheDocument()
  })

  it.each(['viewer', 'demo'])('keeps live runs inspectable but prevents cancellation in %s mode', async (mode) => {
    if (mode === 'viewer') sessionStorage.setItem('bda_user', JSON.stringify({ role: 'viewer' }))
    else useAppStore.setState({ appMode: 'demo' })
    runReturns(RUN)
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    expect(await screen.findByText(RUN.goal)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled()
  })
  it('rejects a task from another project before loading its transcript or actions', async () => {
    runReturns({ ...RUN, project_id: 'another-project' })
    let transcriptReads = 0
    server.use(http.get('/api/v2/copilot/agent-runs/:runId/turns', () => { transcriptReads++; return HttpResponse.json({ items: [] }) }))
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('This task belongs to another project')
    expect(screen.queryByText(RUN.goal)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument()
    expect(transcriptReads).toBe(0)
  })
  it('retries a failed task detail in place', async () => {
    server.use(http.get('/api/v2/copilot/agent-runs/:runId', () => HttpResponse.json({ detail: 'Temporarily unavailable' }, { status: 422 })))
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    const reload = await screen.findByRole('button', { name: 'Reload task records' })
    runReturns(RUN)
    fireEvent.click(reload)
    expect(await screen.findByText(RUN.goal)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
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
    expect(bodies[0]).not.toHaveProperty('max_cost_usd_cents')
    expect(bodies[0]).toMatchObject({
      project_id: 'project-1',
      goal: 'Fold the top three candidates.',
      max_turns: 6,
    })
  })

  it('will not start a run with no goal', () => {
    listReturns([])
    renderWithProviders(<CopilotAgentRuns />)
    expect(screen.getByRole('button', { name: 'Start run' })).toBeDisabled()
  })

  it('keeps progress and blockers visible without exposing model billing', async () => {
    listReturns([
      { ...RUN, id: 'plain', cost_usd_cents: 4, subtree_cost_usd_cents: 4 },
      { ...RUN, id: 'parent', cost_usd_cents: 4, subtree_cost_usd_cents: 19, task_contract: { cost_mode: 'unavailable' } },
    ])
    renderWithProviders(<CopilotAgentRuns />)
    await waitFor(() => expect(screen.getAllByText('2 transcript records')).toHaveLength(2))
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument()
    expect(screen.queryByText(/US cents|Cost not measured|cost ceiling|Estimated reserve/)).not.toBeInTheDocument()
  })

  it('does not mistake transcript rows for model calls when continuing an old task', async () => {
    runReturns({ ...RUN, status: 'failed', turn_count: 20, task_contract: { cost_mode: 'conservative_estimate' }, error: 'copilot_turn_limit_reached: The task model-call limit has been reached.' })
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    const followup = await screen.findByLabelText('Add information or revise the request')
    fireEvent.change(followup, { target: { value: 'Review saved work' } })
    expect(screen.getByRole('button', { name: 'Continue this task' })).toBeEnabled()
    expect(screen.getByText('20 transcript records')).toBeVisible()
    expect(screen.getByText('Uses this task’s remaining model calls and stops at its limit.')).toBeVisible()
    expect(screen.queryByText(/US cents|Cost not measured|Estimated reserve/)).not.toBeInTheDocument()
  })

  it('retains a stopped task while hiding monetary failure details and translating continuation errors', async () => {
    const error = 'budget: cost limit reached (100 cents across the run tree)'
    runReturns({ ...RUN, status: 'failed', error })
    server.use(http.post('/api/v2/copilot/agent-runs/:runId/continuations', () => HttpResponse.json({ error_code: 'copilot_task_budget_exhausted', detail: 'The approved budget is exhausted. Start a new task with a new budget.' }, { status: 409 })))
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('This task’s model-call allowance is exhausted.')
    expect(screen.queryByRole('button', { name: 'Original error' })).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Add information or revise the request'), { target: { value: 'Inspect the saved result' } })
    fireEvent.click(screen.getByRole('button', { name: 'Continue this task' }))
    await waitFor(() => expect(screen.getAllByRole('alert')).toHaveLength(2))
    for (const alert of screen.getAllByRole('alert')) expect(alert).toHaveTextContent('This task’s model-call allowance is exhausted.')
    expect(screen.queryByText(/100 cents|new budget/)).not.toBeInTheDocument()
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

    fireEvent.click(await screen.findByRole('button', { name: 'Transcript' }))
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

  it('waits for cancellation confirmation and reloads a task that finished during the request', async () => {
    runReturns(RUN)
    let release!: () => void
    const pending = new Promise<void>((resolve) => { release = resolve })
    server.use(http.post('/api/v2/copilot/agent-runs/:runId/cancellations', async () => {
      await pending
      const completed = { ...RUN, status: 'succeeded', version: 4 }
      runReturns(completed)
      return HttpResponse.json({ run: completed, cancelled_runs: 0 })
    }))
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
    await screen.findByText(/Cancellation requested. The current call may need to finish/)
    expect(screen.getByRole('button', { name: /Cancelling/ })).toBeDisabled()
    release()
    await screen.findByRole('button', { name: 'Continue this task' })
    expect(screen.queryByRole('button', { name: /Cancelling/ })).not.toBeInTheDocument()
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

  it('locks continuation inputs while sending and preserves them after an exhausted-budget response', async () => {
    runReturns({ ...RUN, status: 'failed', task_contract: { service_kind: 'brief', authorized_writes: ['create_knowledge_draft'] } })
    let release!: () => void
    const pending = new Promise<void>((resolve) => { release = resolve })
    const bodies: unknown[] = []
    server.use(http.post('/api/v2/copilot/agent-runs/:runId/continuations', async ({ request }) => {
      bodies.push(await request.json())
      await pending
      return HttpResponse.json({ detail: 'Start a new task after reviewing the results.' }, { status: 409 })
    }))
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    const input = await screen.findByRole('textbox', { name: 'Add information or revise the request' })
    fireEvent.change(input, { target: { value: 'Keep the UI checklist concise.' } })
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'Continue this task' }))
    await waitFor(() => expect(bodies).toEqual([{ message: 'Keep the UI checklist concise.', authorized_writes: [] }]))
    expect(input).toBeDisabled()
    expect(screen.getByRole('checkbox')).toHaveAttribute('aria-disabled', 'true')
    expect(screen.getByRole('button', { name: 'Prepare a new attempt' })).toBeDisabled()
    fireEvent.submit(input.closest('form')!)
    release()
    expect(await screen.findByText('Start a new task after reviewing the results.')).toBeInTheDocument()
    expect(bodies).toHaveLength(1)
    expect(input).toBeEnabled()
    expect(input).toHaveValue('Keep the UI checklist concise.')
    expect(screen.getByRole('checkbox')).not.toBeChecked()
    expect(screen.queryByText(/12 more turns/)).not.toBeInTheDocument()
  })

  it.each(['failed', 'cancelled'])('prepares a %s task as a reviewed draft without starting or carrying write grants', async (status) => {
    runReturns({ ...RUN, status, bot: 'researcher', max_cost_usd_cents: 0, task_contract: { service_kind: 'brief', authorized_writes: ['create_knowledge_draft'], procedural_skills: [{ id: 'method-1' }] } })
    let writes = 0
    server.use(http.post('/api/v2/copilot/agent-runs', () => { writes++; return HttpResponse.json({}) }))
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    const prepare = await screen.findByRole('button', { name: 'Prepare a new attempt' })
    if (status === 'failed') fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Use only saved UI notes.' } })
    else expect(screen.queryByRole('button', { name: 'Continue this task' })).not.toBeInTheDocument()
    fireEvent.click(prepare)
    expect(useAppStore.getState().copilotTaskDrafts['project-1']).toEqual({
      goal: status === 'failed' ? `${RUN.goal}\n\nAdditional requirements:\nUse only saved UI notes.` : RUN.goal,
      bot: 'researcher', service: 'brief', preview: true, writes: [], maxTurns: 12,
      maxCost: '0', proceduralSkills: ['method-1'], retrySource: 'run-1',
    })
    expect(window.location.hash).toBe('#/bots?project=project-1&view=tasks')
    expect(writes).toBe(0)
  })

  it('keeps existing drafts until replacement is chosen and isolates other projects', async () => {
    const existing = { goal: 'Unsent UI review', bot: null, service: null, preview: false, writes: [], maxTurns: 4, maxCost: '' }
    useAppStore.setState({ copilotTaskDrafts: { 'project-1': existing, 'project-2': existing } })
    runReturns({ ...RUN, status: 'failed', task_contract: { service_kind: 'brief' } })
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Prepare a new attempt' }))
    expect(useAppStore.getState().copilotTaskDrafts['project-1']).toEqual(existing)
    fireEvent.click(screen.getByRole('button', { name: 'Keep existing draft' }))
    expect(screen.queryByRole('button', { name: 'Replace draft and review' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Prepare a new attempt' }))
    fireEvent.click(screen.getByRole('button', { name: 'Replace draft and review' }))
    expect(useAppStore.getState().copilotTaskDrafts['project-1'].goal).toBe(RUN.goal)
    expect(useAppStore.getState().copilotTaskDrafts['project-1'].proceduralSkills).toEqual([])
    expect(useAppStore.getState().copilotTaskDrafts['project-2']).toEqual(existing)
  })

  it('prevents a read-only user from changing continuation grants or preparing a retry', async () => {
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'viewer' }))
    runReturns({ ...RUN, status: 'failed', task_contract: { service_kind: 'brief', authorized_writes: ['create_knowledge_draft'] } })
    renderWithProviders(<AgentRunDetail runId="run-1" projectId="project-1" onBack={() => {}} />)
    expect(await screen.findByRole('button', { name: 'Prepare a new attempt' })).toBeDisabled()
    expect(screen.getByRole('checkbox')).toHaveAttribute('aria-disabled', 'true')
  })
})
