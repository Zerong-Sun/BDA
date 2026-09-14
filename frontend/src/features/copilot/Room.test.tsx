import { cleanup, fireEvent, screen } from '@testing-library/react'
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
  it('names the operator that produced a message', async () => {
    stub([{ kind: 'message', id: 'm1', occurred_at: '2026-09-14T08:00:00Z', bot: 'planner', message: message() }])
    renderWithProviders(<Room />)

    expect(await screen.findByText('Planner')).toBeInTheDocument()
    expect(screen.getByText('Two routes fit.')).toBeInTheDocument()
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

    expect(await screen.findByRole('status')).toHaveTextContent(/appears here/i)
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
    await screen.findByText(/appears here/i)
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
