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

afterEach(() => cleanup())
beforeEach(() => { sessionStorage.clear(); useAppStore.setState({ appMode: 'application', language: 'en' }) })

describe('agent run panel', () => {
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

    await waitFor(() => expect(screen.getByText(/19 with subagents/)).toBeInTheDocument())
    // The childless run says only its own cost: the longer label on equal
    // numbers would imply subagents that do not exist.
    expect(screen.getByText(/2 turns · 4 US cents$/)).toBeInTheDocument()
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
