import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from '../test/mocks/handlers'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAppStore } from '../lib/store/appStore'
import { InboxPage } from './Inbox'

vi.mock('../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => ({ projectId: 'project-inbox', activeProject: { id: 'project-inbox', name: 'PD1 binder', status: 'active' }, projectsLoading: false, projectsError: false, projectsQueryError: null, refetchProjects: vi.fn() }),
}))

const bot = (id: string, title: string, stance: string, extra: Record<string, unknown> = {}) => ({ id, title, title_zh: title, phase: 0, stance, summary: '', charter: '', capabilities: [], handoff: [], reviews: [], directs: [], reviewed_by: [], triggers: [], task_services: [], task_write_tools: {}, absorbs: [], ...extra })
const roster = [bot('researcher', 'Researcher', 'produce', { absorbs: ['librarian'] }), bot('planner', 'Planner', 'produce'), bot('runner', 'Runner', 'produce')]
const run = (id: string, goal: string, botId: string | null, status: string, outcome: string | null, extra: Record<string, unknown> = {}) => ({
  id, project_id: 'project-inbox', goal, bot: botId, status, parent_run_id: null, allowed_tools: [], turn_count: 1, cost_usd_cents: 0, version: 1,
  task_contract: {}, outcome: outcome ? { status: outcome } : {}, created_at: '2026-09-14T00:00:00Z', updated_at: '2026-09-14T01:00:00Z', ...extra,
})
const claim = (confidence: string) => ({ statement: 's', evidence_ref: confidence === 'unsupported' ? '' : 'job:1', confidence })
const handoff = (id: string, from: string, to: string, summary: string, confidence: string) => ({ id, project_id: 'project-inbox', from_bot: from, to_bot: to, summary, claims: [claim(confidence)], open_questions: [], refs: [], produced_by_run: null, created_at: '2026-09-14T00:00:00Z' })
const question = (id: string, asked: string, text: string) => ({
  id, project_id: 'project-inbox', run_id: null, asked_by: asked, question: text,
  options: [{ key: 'a', label: 'A', rationale: '', evidence_refs: [] }, { key: 'b', label: 'B', rationale: '', evidence_refs: [] }],
  recommended: null, status: 'open', answer: null, answer_note: null, answered_by: null,
  answered_at: null, decision_entry_id: null, version: 1, created_at: '2026-09-14T00:00:00Z',
})
const draft = (id: string, name: string, status: string) => ({ id, project_id: 'project-inbox', name, backend: 'lsf', specification: {}, status, confirmed_job_id: null, version: 1, created_at: '2026-09-14T00:00:00Z', updated_at: '2026-09-14T00:00:00Z' })

function handlers({ runs = [] as unknown[], drafts = [] as unknown[], claims = [] as unknown[], handoffs = [] as unknown[], questions = [] as unknown[] } = {}) {
  server.use(
    http.get('/api/v2/copilot/bots', () => HttpResponse.json(roster)),
    http.get('/api/v2/copilot/projects/:projectId/agent-runs', () => HttpResponse.json({ items: runs, next_cursor: null })),
    http.get('/api/v2/compute-drafts', () => HttpResponse.json({ items: drafts, next_cursor: null })),
    http.get('/api/v2/projects/:projectId/literature/claims', ({ request }) => {
      // Only pending claims are a person's decision; the page must ask for those.
      expect(new URL(request.url).searchParams.get('review_status')).toBe('pending')
      return HttpResponse.json({ items: claims, next_cursor: null })
    }),
    http.get('/api/v2/copilot/projects/:projectId/handoffs', () => HttpResponse.json({ items: handoffs, next_cursor: null })),
    http.get('/api/v2/copilot/projects/:projectId/decision-requests', ({ request }) => {
      // Only open questions are waiting on a person; an answered one belongs to
      // the record, and listing it here would never let the inbox reach zero.
      expect(new URL(request.url).searchParams.get('status')).toBe('open')
      return HttpResponse.json({ items: questions })
    }),
  )
}

beforeEach(() => { sessionStorage.clear(); useAppStore.setState({ language: 'en', appMode: 'application' }) })
afterEach(cleanup)

describe('Decision inbox', () => {
  it('gathers what only a person can settle and links to where each is decided', async () => {
    handlers({
      runs: [
        run('r1', 'Search PD1 literature', 'librarian', 'succeeded', 'needs_input'),
        run('r2', 'Plan the route', 'planner', 'succeeded', 'completed'),
        run('r3', 'Still thinking', 'runner', 'running', null),
        run('r4', 'Delegated child', 'researcher', 'succeeded', 'needs_input', { parent_run_id: 'r2' }),
        run('r5', 'Already recorded', 'analyst', 'succeeded', 'completed', { outcome: { status: 'completed', decision_record_id: 'entry-1' } }),
      ],
      drafts: [draft('d1', 'AF3 MSA stage', 'draft'), draft('d2', 'Old submission', 'confirmed')],
      claims: [{ id: 'c1' }, { id: 'c2' }],
      handoffs: [handoff('h1', 'researcher', 'planner', 'Evidence for routing', 'unsupported'), handoff('h2', 'planner', 'runner', 'Draft ready', 'stated')],
      questions: [question('q1', 'planner', 'Which hotspot set should the binder target?')],
    })
    renderWithProviders(<InboxPage />)

    const input = screen.getByRole('region', { name: 'Needs your input' })
    // Recorded under a retired id, owned now by the operator that absorbed it.
    expect(await within(input).findByRole('link', { name: /Search PD1 literature/ })).toHaveAttribute('href', '#/bots/researcher?project=project-inbox&run=r1')
    expect(within(input).queryByText(/Delegated child/)).not.toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Ready for your review' })).getByRole('link', { name: /Plan the route/ })).toHaveAttribute('href', '#/bots/planner?project=project-inbox&run=r2')
    expect(screen.queryByText(/Still thinking/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Already recorded/)).not.toBeInTheDocument()

    const drafts = screen.getByRole('region', { name: 'Compute drafts to confirm' })
    expect(await within(drafts).findByRole('link', { name: /AF3 MSA stage/ })).toHaveAttribute('href', '#/workflow?project=project-inbox')
    expect(within(drafts).queryByText(/Old submission/)).not.toBeInTheDocument()

    expect(await within(screen.getByRole('region', { name: 'Literature claims to review' })).findByRole('link', { name: /2 extracted claims are waiting/ })).toHaveAttribute('href', '#/research?project=project-inbox&tab=evidence')

    // The only source that is a question rather than an inference: it links to
    // the room, because that is where the operator asked it.
    const waiting = screen.getByRole('region', { name: 'A Bot is waiting on your call' })
    expect(await within(waiting).findByRole('link', { name: /Which hotspot set/ })).toHaveAttribute('href', '#/bots?project=project-inbox&view=room')
    expect(within(waiting).getByText(/2 options/)).toBeInTheDocument()

    const evidence = screen.getByRole('region', { name: 'Claims without evidence' })
    expect(await within(evidence).findByRole('link', { name: /Evidence for routing/ })).toHaveAttribute('href', '#/bots/planner?project=project-inbox')
    expect(within(evidence).queryByText(/Draft ready/)).not.toBeInTheDocument()
    expect(screen.queryByText('Nothing needs your decision right now.')).not.toBeInTheDocument()
  })

  it('says plainly when nothing is waiting', async () => {
    handlers()
    renderWithProviders(<InboxPage />)
    expect(await screen.findByText('Nothing needs your decision right now.')).toBeInTheDocument()
  })

  it('keeps the other sources visible when one cannot be read, and recovers it', async () => {
    handlers({ runs: [run('r1', 'Search PD1 literature', 'researcher', 'succeeded', 'needs_input')] })
    server.use(http.get('/api/v2/compute-drafts', () => HttpResponse.json({ detail: 'Drafts unavailable' }, { status: 422 })))
    renderWithProviders(<InboxPage />)

    expect(await screen.findByRole('link', { name: /Search PD1 literature/ })).toBeInTheDocument()
    const drafts = screen.getByRole('region', { name: 'Compute drafts to confirm' })
    const retry = await within(drafts).findByRole('button', { name: 'Retry' })
    expect(screen.queryByText('Nothing needs your decision right now.')).not.toBeInTheDocument()
    server.use(http.get('/api/v2/compute-drafts', () => HttpResponse.json({ items: [draft('d1', 'AF3 MSA stage', 'draft')], next_cursor: null })))
    fireEvent.click(retry)
    expect(await within(drafts).findByRole('link', { name: /AF3 MSA stage/ })).toBeInTheDocument()
  })
})
