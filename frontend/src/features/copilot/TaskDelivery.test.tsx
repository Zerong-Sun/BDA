import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { HashRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { saveTaskDecisionRecord, type AgentRun } from '../../lib/api/agentRuns'
import { TaskDelivery } from './TaskDelivery'

vi.mock('../../lib/api/agentRuns', () => ({ saveTaskDecisionRecord: vi.fn() }))
vi.mock('./commandAccess', () => ({ requireCopilotWrite: vi.fn(), useCopilotReadOnly: () => false }))
afterEach(cleanup)

describe('saved task plans', () => {
  it('refreshes the actual timeline cache and links to the saved entry', async () => {
    useAppStore.setState({ language: 'en' })
    const run: AgentRun = {
      id: 'run', project_id: 'project', status: 'succeeded', version: 3,
      task_contract: { service_kind: 'brief' }, outcome: { summary: 'Review these notes.' },
      conversation_id: null, created_by: 'user', bot: 'researcher', goal: 'Review notes',
      parent_run_id: null, allowed_tools: [], max_turns: 6, turn_count: 4,
      cost_usd_cents: 0, subtree_cost_usd_cents: 0, max_cost_usd_cents: null, error: null,
      created_at: '2026-10-20T00:00:00Z', updated_at: '2026-10-20T00:00:00Z',
    }
    const saved = { ...run, version: 4, outcome: { ...run.outcome, decision_record_id: 'plan-record' } }
    vi.mocked(saveTaskDecisionRecord).mockResolvedValue(saved)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    client.setQueryData(['project-timeline', 'project'], [])
    const ui = render(<QueryClientProvider client={client}><HashRouter><TaskDelivery run={run} /></HashRouter></QueryClientProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Save as a plan for review' }))
    await waitFor(() => expect(client.getQueryState(['project-timeline', 'project'])?.isInvalidated).toBe(true))
    expect(saveTaskDecisionRecord).toHaveBeenCalledWith('run', 3)
    expect(client.getQueryData(['agent-run', 'project', 'run'])).toEqual(saved)
    ui.rerender(<QueryClientProvider client={client}><HashRouter><TaskDelivery run={saved} /></HashRouter></QueryClientProvider>)
    expect(screen.getByRole('link', { name: 'Open saved plan record' })).toHaveAttribute('href', '#/research?project=project&tab=timeline&timeline_view=timeline&timeline_entry=plan-record')
    expect(screen.queryByRole('button', { name: 'Save as a plan for review' })).not.toBeInTheDocument()
  })
})
