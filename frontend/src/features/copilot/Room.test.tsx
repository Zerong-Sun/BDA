import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { Room } from './Room'

/**
 * The room shows records, and these tests are about the ones that would be
 * easiest to render wrongly:
 *
 * * a message nobody attributed must not acquire a speaker;
 * * a handover must arrive as a handover, with its unsupported claim visible,
 *   rather than flattened into a line of text;
 * * a delegated task must appear under the task that opened it, because a
 *   child listed at the top level reads as work that arrived from nowhere.
 *
 * The feed is server state, so every assertion here is about what the endpoint
 * returned - nothing is read from the chat store.
 */

afterEach(cleanup)

const BOTS = [
  {
    id: 'planner', title: 'Planner', title_zh: '方案设计', phase: 2, stance: 'produce',
    summary: 'Choose the route.', charter: 'Draft, never confirm.', capabilities: ['project-read'],
    handoff: ['runner'], reviews: [], directs: [], reviewed_by: ['auditor'], triggers: [],
    task_services: ['planning'], task_write_tools: {}, absorbs: [],
  },
  {
    id: 'runner', title: 'Runner', title_zh: '执行与排障', phase: 3, stance: 'produce',
    summary: 'Carry a run across its waits.', charter: 'Do not resubmit.', capabilities: ['project-read'],
    handoff: ['analyst'], reviews: [], directs: [], reviewed_by: ['auditor'], triggers: [],
    task_services: ['execution'], task_write_tools: {}, absorbs: [],
  },
  {
    // A reviewer owns no recipe, which is what makes it the right operator to
    // check that the room offers no task for one.
    id: 'auditor', title: 'Auditor', title_zh: '复核', phase: 9, stance: 'review',
    summary: 'Rule on claims against their evidence.', charter: 'Do not repair what you find.',
    capabilities: ['review-audit'], handoff: ['conductor'], reviews: ['planner'], directs: [],
    reviewed_by: [], triggers: [], task_services: [], task_write_tools: {}, absorbs: [],
  },
]

const PROJECT = {
  id: 'proj_test', organization_id: 'org_test', name: 'Test project', project_type: 'protein_design',
  status: 'active', owner_id: 'user_test', summary: 'Room test project', primary_target_id: null,
  version: 1, created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
}

function message(overrides: Record<string, unknown> = {}) {
  return {
    id: 'm1', conversation_id: 'c1', role: 'assistant', bot: 'planner', content: 'Two routes fit.',
    status: 'completed', citations: [], tool_calls: [], context: {}, error: null, version: 1,
    created_at: '2026-09-14T08:00:00Z', updated_at: '2026-09-14T08:00:00Z', ...overrides,
  }
}

function task(overrides: Record<string, unknown> = {}) {
  return {
    id: 'run-1', goal: 'Draft the binder route', bot: 'planner', status: 'completed',
    parent_run_id: null, turn_count: 3, delivery_state: 'completed', decision_record_id: null,
    updated_at: '2026-09-14T08:10:00Z', ...overrides,
  }
}

function stub(items: unknown[]) {
  useAppStore.setState({ activeProjectId: 'proj_test' })
  server.use(
    http.get('/api/v2/projects', () => HttpResponse.json({ items: [PROJECT], next_cursor: null })),
    http.get('/api/v2/copilot/bots', () => HttpResponse.json(BOTS)),
    http.get('/api/v2/copilot/projects/:projectId/room', () =>
      HttpResponse.json({ items, next_cursor: null }),
    ),
  )
}

describe('Room', () => {
  it('shows real background discussion and opens its evidence', async () => {
    stub([{ kind: 'discussion', id: 'turn-1', occurred_at: '2026-09-14T08:20:00Z', bot: 'planner',
      discussion: { run_id: 'run-1', content: 'PD-L1 route comparison is ready for review.' } }])
    const onOpenRun = vi.fn()
    renderWithProviders(<Room onOpenRun={onOpenRun} />)
    expect(await screen.findByText('PD-L1 route comparison is ready for review.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Open task and evidence' }))
    expect(onOpenRun).toHaveBeenCalledWith('run-1')
  })

  it('keeps a delegated task visible when its parent is on an older page', async () => {
    stub([{ kind: 'task', id: 'child-1', occurred_at: '2026-09-14T08:20:00Z', bot: 'planner',
      task: task({ id: 'child-1', parent_run_id: 'older-parent', goal: 'Check PD-L1 geometry' }) }])
    renderWithProviders(<Room />)
    expect(await screen.findByText('Check PD-L1 geometry')).toBeInTheDocument()
  })

  it('recovers a pending server reply after a reload without a local chat stream', async () => {
    stub([])
    useAppStore.setState({ copilotSessions: {}, copilotMessages: [] })
    let reads = 0
    server.use(http.get('/api/v2/copilot/projects/:projectId/room', () => {
      reads += 1
      const user = { kind: 'message', id: 'm1', occurred_at: '2026-09-14T08:00:00Z', bot: null,
        message: message({ id: 'm1', role: 'user', content: 'Reloaded question', status: reads === 1 ? 'pending' : 'completed' }) }
      const answer = { kind: 'message', id: 'm2', occurred_at: '2026-09-14T08:01:00Z', bot: 'planner',
        message: message({ id: 'm2', content: 'Reply recovered from the server.' }) }
      return HttpResponse.json({ items: reads === 1 ? [user] : [answer, user], next_cursor: null })
    }))
    renderWithProviders(<Room />)
    expect(await screen.findByText('Reloaded question')).toBeInTheDocument()
    expect(await screen.findByText('Reply recovered from the server.', {}, { timeout: 6000 })).toBeInTheDocument()
    expect(reads).toBe(2)
  }, 10_000)

  it('replaces the accepted echo by id while keeping the reply placeholder and repeated messages', async () => {
    stub(['m1', 'm2'].map((id) => ({
      kind: 'message', id, occurred_at: '2026-09-14T08:00:00Z', bot: null,
      message: message({ id, role: 'user', content: 'hi', status: 'pending' }),
    })))
    useAppStore.setState({ copilotSessions: { proj_test: {
      conversationId: 'c1', bot: null, pending: { id: 'turn-1', stage: 'thinking', detail: null },
      messages: [
        { role: 'assistant', content: 'Old reply must not be echoed.' },
        { id: 'm2', role: 'user', content: 'hi' },
        { role: 'assistant', content: '' },
      ],
    } } })
    renderWithProviders(<Room />)
    await waitFor(() => expect(screen.getAllByText('hi')).toHaveLength(2))
    expect(screen.getByText('Replying')).toBeInTheDocument()
    expect(screen.getByRole('status')).not.toBeEmptyDOMElement()
    expect(screen.queryByText('Old reply must not be echoed.')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Say something in the room')).toBeDisabled()
    useAppStore.setState({ copilotSessions: {} })
  })

  it('receives a project question as an unsent editable draft and consumes it once', async () => {
    stub([])
    useAppStore.setState({ copilotDraft: 'Compare the selected structures using their evidence.' })
    const first = renderWithProviders(<Room />)
    const input = await screen.findByRole('textbox', { name: 'Say something in the room' })
    await waitFor(() => expect(input).toHaveValue('Compare the selected structures using their evidence.'))
    expect(useAppStore.getState().copilotDraft).toBe('')
    fireEvent.change(input, { target: { value: 'My revised question, still unsent.' } })
    first.unmount()
    renderWithProviders(<Room />)
    await waitFor(() => expect(screen.getByRole('textbox', { name: 'Say something in the room' })).toHaveValue('My revised question, still unsent.'))
  })

  it.each([
    ['en', 'This turn reached its call limit'],
    ['zh', '本轮已达到调用限制'],
  ] as const)('explains a stored allowance failure in %s and allows a new question', async (language, explanation) => {
    useAppStore.setState({ language })
    stub([{ kind: 'message', id: 'failure', occurred_at: '2026-09-14T08:00:00Z', bot: 'planner', message: message({
      status: 'failed', content: 'Copilot provider failed; no scientific conclusion was generated.',
      error: 'The task allowance cannot cover another request.',
    }) }])
    renderWithProviders(<Room />)
    expect(await screen.findByText(new RegExp(explanation))).toBeInTheDocument()
    expect(screen.queryByText(/Copilot provider failed/)).not.toBeInTheDocument()
    expect(screen.queryByText('The task allowance cannot cover another request.')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /retry|重试/i })).not.toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: language === 'zh' ? '在研究室里发言' : 'Say something in the room' })).toBeEnabled()
    useAppStore.setState({ language: 'en' })
  })

  it('uses stored error codes while keeping raw exceptions out of the room', async () => {
    stub([{ kind: 'message', id: 'failure', occurred_at: '2026-09-14T08:00:00Z', bot: 'planner', message: message({
      status: 'failed', content: 'Raw exception at https://private.invalid',
      error: 'Authentication failed: token=private-token at https://private.invalid', context: { error_code: 'llm_budget_exhausted' },
    }) }])
    renderWithProviders(<Room />)
    expect(await screen.findByText(/This turn reached its call limit/)).toBeInTheDocument()
    expect(screen.queryByText(/private-token|private.invalid|Raw exception/)).not.toBeInTheDocument()
  })

  it('retains a partial draft and distinguishes its incomplete review from a failed reply', async () => {
    stub([{ kind: 'message', id: 'partial', occurred_at: '2026-09-14T08:00:00Z', bot: 'planner', message: message({
      content: 'Saved draft with evidence; final review is incomplete.',
      context: { delivery_status: 'partial', review_status: 'not_completed', stop_reason: 'llm_budget_exhausted' },
    }) }])
    renderWithProviders(<Room />)
    expect(await screen.findByText('Saved draft with evidence; final review is incomplete.')).toBeVisible()
    expect(screen.getByText(/partially completed · review incomplete/)).toBeVisible()
    expect(screen.queryByText(/could not answer/)).not.toBeInTheDocument()
  })

  it('prepares a fresh conversation without resending or removing server history', async () => {
    stub([{ kind: 'message', id: 'm1', occurred_at: '2026-09-14T08:00:00Z', bot: 'planner', message: message() }])
    useAppStore.setState({ copilotSessions: { proj_test: { conversationId: 'old-conversation', messages: [], bot: 'planner', input: 'A narrower question', mode: 'bench' } } })
    renderWithProviders(<Room />)
    await screen.findByText('Two routes fit.')
    fireEvent.click(screen.getByRole('button', { name: 'New conversation' }))
    expect(useAppStore.getState().copilotSessions.proj_test.conversationId).toBeNull()
    expect(useAppStore.getState().copilotSessions.proj_test.pending).toBeUndefined()
    expect(useAppStore.getState().copilotSessions.proj_test.mode).toBe('bench')
    expect(screen.getByRole('textbox', { name: 'Say something in the room' })).toHaveValue('A narrower question')
    expect(screen.getByText('Two routes fit.')).toBeVisible()
    expect(screen.getByText(/Earlier records remain in this room/)).toBeVisible()
    useAppStore.setState({ copilotSessions: {} })
  })

  it('names the operator that produced a message', async () => {
    stub([{ kind: 'message', id: 'm1', occurred_at: '2026-09-14T08:00:00Z', bot: 'planner', message: message() }])
    renderWithProviders(<Room />)

    expect(await screen.findByText('Planner')).toBeInTheDocument()
    expect(screen.getByText('Two routes fit.')).toBeInTheDocument()
  })

  it('shows persisted canonical selections and highlighted views as exact residue links after loading the room', async () => {
    const residues = [{ chain: 'B', seq: 46, insertion_code: null, name: 'LYS' }, { chain: 'B', seq: 54, insertion_code: 'A', name: 'ARG' }]
    stub([{ kind: 'message', id: 'm1', occurred_at: '2026-09-14T08:00:00Z', bot: 'planner', message: message({
      content: 'Geometric contacts from predicted coordinates.',
      tool_calls: [
        { name: 'list_structure_residues', status: 'completed', result: { artifact_id: 'artifact-one', filename: 'model.pdb', viewer_selection: { artifact_id: 'artifact-one', residues } } },
        { name: 'render_structure_view', status: 'completed', result: { artifact_id: 'artifact-one', filename: 'model.pdb', highlighted: residues } },
      ],
    }) }])
    renderWithProviders(<Room />)
    expect(await screen.findByText('Geometric contacts from predicted coordinates.')).toBeInTheDocument()
    const selections = await screen.findAllByRole('link', { name: 'Open structure and residues in Results' })
    expect(selections).toHaveLength(2)
    for (const selection of selections) {
      const query = new URLSearchParams(selection.getAttribute('href')!.split('?')[1])
      expect(query.get('project')).toBe('proj_test')
      expect(query.get('artifact')).toBe('artifact-one')
      expect(JSON.parse(query.get('residues')!)).toEqual(residues)
    }
  })

  it('leaves an unattributed turn unattributed rather than defaulting it to a bot', async () => {
    stub([
      { kind: 'message', id: 'm1', occurred_at: '2026-09-14T08:00:00Z', bot: null, message: message({ bot: null }) },
    ])
    renderWithProviders(<Room />)

    expect(await screen.findByText('Assistant')).toBeInTheDocument()
    expect(screen.queryByText('Planner')).not.toBeInTheDocument()
  })

  it('shows a handover as a handover, with the claim that cites nothing', async () => {
    stub([
      {
        kind: 'handoff', id: 'h1', occurred_at: '2026-09-14T08:05:00Z', bot: 'planner',
        handoff: {
          id: 'h1', from_bot: 'planner', to_bot: 'runner', summary: 'Draft is ready.',
          claims: [{ statement: 'The queue forces a GPU', evidence_ref: '', confidence: 'unsupported' }],
          open_questions: [], refs: [], produced_by_run: null, created_at: '2026-09-14T08:05:00Z',
        },
      },
    ])
    renderWithProviders(<Room />)

    expect(await screen.findByText('Draft is ready.')).toBeInTheDocument()
    expect(screen.getByText('The queue forces a GPU')).toBeInTheDocument()
  })

  it('nests a delegated task under the task that opened it', async () => {
    stub([
      { kind: 'task', id: 'run-1', occurred_at: '2026-09-14T08:10:00Z', bot: 'planner', task: task() },
      {
        kind: 'task', id: 'run-2', occurred_at: '2026-09-14T08:12:00Z', bot: 'runner',
        task: task({ id: 'run-2', bot: 'runner', goal: 'Carry the run', parent_run_id: 'run-1', status: 'running', delivery_state: 'running' }),
      },
    ])
    renderWithProviders(<Room />)

    const child = await screen.findByText('Carry the run')
    expect(child.closest('.room-children')).not.toBeNull()
    expect(screen.getByText('Draft the binder route')).toBeInTheDocument()
  })

  it('explains an empty room instead of showing nothing', async () => {
    stub([])
    renderWithProviders(<Room />)

    expect(await screen.findByRole('status')).toHaveTextContent(/Tell the project lead/i)
  })

  it('offers a retry when the feed cannot be read', async () => {
    useAppStore.setState({ activeProjectId: 'proj_test' })
    server.use(
      http.get('/api/v2/projects', () => HttpResponse.json({ items: [PROJECT], next_cursor: null })),
      http.get('/api/v2/copilot/bots', () => HttpResponse.json(BOTS)),
      http.get('/api/v2/copilot/projects/:projectId/room', () =>
        HttpResponse.json({ detail: 'nope' }, { status: 500 }),
      ),
    )
    renderWithProviders(<Room />)

    expect(await screen.findByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})

/**
 * Addressing a member is routing, so the assertions are about what happens to a
 * message the person believes they addressed.
 */
describe('Room addressing', () => {
  async function typed(text: string) {
    stub([])
    const onAssign = vi.fn()
    renderWithProviders(<Room onAssign={onAssign} />)
    // The composer renders before the project resolves, and the draft is kept
    // per project - typing first would write it under the empty project key and
    // lose it as soon as the real one arrives. Waiting for the loaded room is
    // how a person reaches the composer too.
    await screen.findByText(/Tell the project lead/i)
    const input = await screen.findByLabelText('Say something in the room')
    fireEvent.change(input, { target: { value: text } })
    return { onAssign }
  }

  it('names the addressee before the message is sent', async () => {
    await typed('@planner draft the route')

    expect(await screen.findByText('Planner')).toBeInTheDocument()
  })

  it('refuses a handle that names nobody rather than sending it to somebody else', async () => {
    await typed('@nobody draft the route')

    expect(await screen.findByText(/No member is called/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
  })

  it('prepares a task for the operator that was addressed, carrying the work and not the address', async () => {
    const { onAssign } = await typed('@planner draft the route')

    fireEvent.click(await screen.findByRole('button', { name: 'Hand it to them' }))

    expect(onAssign).toHaveBeenCalledWith('draft the route', 'planner', 'planning')
  })

  it('offers no task for an operator that owns no recipe', async () => {
    await typed('@auditor check that claim')

    expect(screen.queryByRole('button', { name: 'Hand it to them' })).not.toBeInTheDocument()
  })
})

/**
 * A question put to a person is the one entry the room can act on, so these
 * assertions are about the substance a reader needs before acting: what each
 * option costs, which one the operator would pick, and - the case that is easy
 * to render away - an option offered with no reason at all.
 */
describe('Room decisions', () => {
  const DECISION = {
    id: 'd1', project_id: 'proj_test', run_id: null, asked_by: 'planner',
    question: 'Which hotspot set should the binder target?',
    options: [
      { key: 'loop', label: "Target the CC' loop", rationale: 'Covers the native interface', evidence_refs: ['artifact:1'] },
      { key: 'hot3', label: 'Target I126/L128/A132', rationale: '', evidence_refs: [] },
    ],
    recommended: 'loop', status: 'open', answer: null, answer_note: null,
    answered_by: null, answered_at: null, decision_entry_id: null, version: 1,
    created_at: '2026-09-14T08:20:00Z',
  }

  function decisionEntry(overrides: Record<string, unknown> = {}) {
    return {
      kind: 'decision', id: 'd1', occurred_at: '2026-09-14T08:20:00Z', bot: 'planner',
      decision: { ...DECISION, ...overrides },
    }
  }

  it('shows each option with what it rests on, and says when one rests on nothing', async () => {
    stub([decisionEntry()])
    renderWithProviders(<Room />)

    expect(await screen.findByText('Which hotspot set should the binder target?')).toBeInTheDocument()
    expect(screen.getByText('Covers the native interface')).toBeInTheDocument()
    expect(screen.getByText('No reason given')).toBeInTheDocument()
    expect(screen.getByText('artifact:1')).toBeInTheDocument()
    expect(screen.getByText('Suggested')).toBeInTheDocument()
  })

  it('sends the chosen option with the version it was read at', async () => {
    stub([decisionEntry()])
    let sent: { choice?: string; version?: string | null } = {}
    server.use(
      http.post('/api/v2/copilot/decision-requests/:id/answers', async ({ request }) => {
        const body = (await request.json()) as { choice: string }
        sent = { choice: body.choice, version: request.headers.get('If-Match') }
        return HttpResponse.json({ ...DECISION, status: 'answered', answer: body.choice, version: 2 })
      }),
    )
    renderWithProviders(<Room />)

    fireEvent.click(await screen.findByRole('button', { name: "Choose: Target the CC' loop" }))

    await vi.waitFor(() => expect(sent.choice).toBe('loop'))
    expect(sent.version).toBe('W/"1"')
  })

  it('shows what was decided and offers no further choice once it is settled', async () => {
    stub([decisionEntry({ status: 'answered', answer: 'hot3', version: 2 })])
    renderWithProviders(<Room />)

    expect(await screen.findByText('Decided: Target I126/L128/A132')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Choose:/ })).not.toBeInTheDocument()
  })

  it('explains a question settled by someone else rather than overwriting their call', async () => {
    stub([decisionEntry()])
    server.use(
      http.post('/api/v2/copilot/decision-requests/:id/answers', () =>
        HttpResponse.json({ detail: 'version_conflict' }, { status: 412 }),
      ),
    )
    renderWithProviders(<Room />)

    fireEvent.click(await screen.findByRole('button', { name: "Choose: Target the CC' loop" }))

    expect(await screen.findByText(/settled by someone else/i)).toBeInTheDocument()
  })
})

describe('Room attachments', () => {
  afterEach(() => {
    useAppStore.setState({ copilotSessions: {}, copilotSelectedEntityIds: [] })
  })

  it('shows what the next message carries, by name, and lets it be taken out', async () => {
    stub([])
    useAppStore.getState().setCopilotSelectedEntityIds(['art-1', 'art-2'], 'proj_test', { 'art-1': '4ZQK · PD-1/PD-L1' })

    renderWithProviders(<Room />)

    const group = await screen.findByRole('group', { name: 'Attached to your next message' })
    expect(group).toHaveTextContent('4ZQK · PD-1/PD-L1')
    // No label was known for this one; it is shown as its id rather than hidden.
    expect(group).toHaveTextContent('art-2')

    fireEvent.click(screen.getByRole('button', { name: 'Remove 4ZQK · PD-1/PD-L1' }))

    expect(useAppStore.getState().copilotSessions.proj_test?.selectedEntityIds).toEqual(['art-2'])
    expect(useAppStore.getState().copilotSelectedEntityIds).toEqual(['art-2'])
    expect(screen.queryByText('4ZQK · PD-1/PD-L1')).not.toBeInTheDocument()
  })

  it('drops a removed item’s label so it cannot reappear against a later selection', () => {
    useAppStore.setState({ activeProjectId: 'proj_test' })
    const store = useAppStore.getState()
    store.setCopilotSelectedEntityIds(['art-1'], 'proj_test', { 'art-1': 'Old name' })
    store.setCopilotSelectedEntityIds([], 'proj_test', { 'art-1': 'Old name' })

    expect(useAppStore.getState().copilotSessions.proj_test?.selectedEntityLabels).toEqual({})
  })

  it('shows no attachment row when nothing is attached', async () => {
    stub([])

    renderWithProviders(<Room />)

    expect(await screen.findByLabelText('Say something in the room')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Attached to your next message' })).not.toBeInTheDocument()
  })
})


it('keeps cleaned messages out by default and provides a labelled audit view', async () => {
  stub([])
  const requests: string[] = []
  server.use(http.get('/api/v2/copilot/projects/:projectId/room', ({ request }) => {
    const includeArchived = new URL(request.url).searchParams.get('include_archived')
    requests.push(includeArchived ?? '')
    return HttpResponse.json({ items: includeArchived === 'true' ? [{
      kind: 'message', id: 'old-launch', occurred_at: '2026-09-14T08:00:00Z', bot: 'planner',
      message: message({ id: 'old-launch', content: 'Old launch notice', context: { chat_archive: { archived: true } } }),
    }] : [], next_cursor: null })
  }))
  renderWithProviders(<Room />)
  await waitFor(() => expect(requests).toContain('false'))
  expect(screen.queryByText('Old launch notice')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Show archived messages' }))
  expect(await screen.findByText('Old launch notice')).toBeInTheDocument()
  expect(screen.getByText(/archived history/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Hide archived messages' }))
  await waitFor(() => expect(screen.queryByText('Old launch notice')).not.toBeInTheDocument())
})
