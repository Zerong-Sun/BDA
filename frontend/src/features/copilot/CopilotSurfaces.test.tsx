import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactElement } from 'react'
import { HashRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  applyRoutePlan,
  confirmClusterDraft,
  getClusterDraft,
  getCopilotConfig,
  listClusterDrafts,
  planRoute,
  testCopilotConfig,
  updateCopilotConfig,
} from '../../lib/api/copilot'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useAppStore } from '../../lib/store/appStore'
import { ClusterDrafts } from './ClusterDrafts'
import { CopilotActions } from './CopilotActions'
import { CopilotLoadingBubble } from './CopilotLoadingBubble'
import { CopilotSettings } from './CopilotSettings'

vi.mock('../../lib/api/copilot')
vi.mock('../../lib/hooks/useProjectContext', () => ({ useProjectContext: vi.fn() }))

const PROJECT_ID = 'project-one'

function renderSurface(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <HashRouter>{ui}</HashRouter>
      </QueryClientProvider>,
    ),
  }
}

const draft = {
  id: 'draft-one',
  project_id: PROJECT_ID,
  name: 'Run ProteinMPNN',
  backend: 'lsf',
  specification: {
    queue: 'gpu',
    cpu_count: 8,
    gpu_count: 1,
    script: '#!/bin/bash\nbsub proteinmpnn',
    rationale: 'Generate a focused sequence library.',
  },
  status: 'draft',
  confirmed_job_id: null,
  version: 1,
  created_at: '2026-07-29T00:00:00Z',
  updated_at: '2026-07-29T00:00:00Z',
}

beforeEach(() => {
  vi.clearAllMocks()
  useAppStore.setState({ language: 'en', appMode: 'application' })
  vi.mocked(useProjectContext).mockReturnValue({
    projectId: PROJECT_ID,
    activeProject: {
      id: PROJECT_ID,
      name: 'Protein program',
      summary: 'Improve affinity',
      project_type: 'protein_design',
    },
  } as ReturnType<typeof useProjectContext>)
  vi.mocked(planRoute).mockResolvedValue({
    target: 'Improve affinity',
    route_options: [{
      route_id: 'route-one',
      label: 'Affinity route',
      recommended: true,
      modules: [{ module_id: 'proteinmpnn', available: true }],
    }],
  } as never)
  vi.mocked(applyRoutePlan).mockResolvedValue({} as never)
  vi.mocked(listClusterDrafts).mockResolvedValue({ items: [draft] } as never)
  vi.mocked(getClusterDraft).mockResolvedValue(draft as never)
  vi.mocked(confirmClusterDraft).mockResolvedValue({
    ...draft,
    status: 'submitted',
    confirmed_job_id: 'job-one',
  } as never)
  vi.mocked(getCopilotConfig).mockResolvedValue({
    llm_api_base: 'https://api.example.test',
    llm_model: 'model-one',
    api_key_configured: true,
    api_key_preview: 'sk-…1234',
    system_prompt: 'Use reviewed evidence.',
  } as never)
  vi.mocked(updateCopilotConfig).mockResolvedValue({} as never)
  vi.mocked(testCopilotConfig).mockResolvedValue({
    connected: true,
    model: 'model-one',
    sample: 'OK',
    reason: undefined,
  })
})

afterEach(cleanup)

describe('CopilotActions', () => {
  it('keeps navigation enabled while guarding plan/apply inside demo mutations', async () => {
    useAppStore.setState({ appMode: 'demo' })
    renderSurface(<CopilotActions />)

    const planButton = screen.getByRole('button', { name: 'Plan and build a workflow' })
    expect(planButton).toHaveAttribute('data-slot', 'button')
    expect(planButton).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Analyze target' })).toBeEnabled()

    planButton.removeAttribute('disabled')
    fireEvent.click(planButton)
    await Promise.resolve()

    expect(planRoute).not.toHaveBeenCalled()
    expect(applyRoutePlan).not.toHaveBeenCalled()
  })

  it('preserves route planning and apply ordering in application mode', async () => {
    renderSurface(<CopilotActions />)

    fireEvent.click(screen.getByRole('button', { name: 'Plan and build a workflow' }))

    await waitFor(() => expect(applyRoutePlan).toHaveBeenCalledTimes(1))
    expect(planRoute).toHaveBeenCalledTimes(1)
    expect(vi.mocked(planRoute).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(applyRoutePlan).mock.invocationCallOrder[0],
    )
  })
})

describe('ClusterDrafts', () => {
  it('uses Frame, Badge, Accordion, and registry controls while preserving polling', async () => {
    const { client } = renderSurface(<ClusterDrafts projectId={PROJECT_ID} />)

    expect(await screen.findByText('Run ProteinMPNN')).toBeInTheDocument()
    expect(document.querySelector('[data-slot="frame"]')).toBeInTheDocument()
    expect(document.querySelector('[data-slot="badge"]')).toBeInTheDocument()
    expect(document.querySelector('[data-slot="accordion"]')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Cluster job drafts/ }))
      .toHaveAttribute('data-slot', 'accordion-trigger')
    expect(screen.getByRole('button', { name: 'Review LSF script' }))
      .toHaveAttribute('data-slot', 'accordion-trigger')
    expect(screen.getByRole('button', { name: 'Confirm and submit' }))
      .toHaveAttribute('data-slot', 'button')

    const pollingQuery = client.getQueryCache().find({ queryKey: ['cluster-drafts', PROJECT_ID] })
    const pollingOptions = pollingQuery?.options as { refetchInterval?: unknown }
    const polling = pollingOptions.refetchInterval
    expect(polling).toBeTypeOf('function')
    expect(
      (polling as (query: { state: { data: { items: Array<{ status: string }> } } }) => number | false)({
        state: { data: { items: [{ status: 'running' }] } },
      }),
    ).toBe(5000)
    expect(
      (polling as (query: { state: { data: { items: Array<{ status: string }> } } }) => number | false)({
        state: { data: { items: [{ status: 'completed' }] } },
      }),
    ).toBe(false)
  })

  it('auto-opens a pending draft once and preserves the user’s manual collapse', async () => {
    renderSurface(<ClusterDrafts projectId={PROJECT_ID} />)

    const disclosure = await screen.findByRole('button', { name: /Cluster job drafts/ })
    await waitFor(() => expect(disclosure).toHaveAttribute('aria-expanded', 'true'))
    expect(screen.getByText('Run ProteinMPNN')).toBeInTheDocument()

    fireEvent.click(disclosure)
    await waitFor(() => expect(disclosure).toHaveAttribute('aria-expanded', 'false'))
    await waitFor(() => expect(screen.queryByText('Run ProteinMPNN')).not.toBeInTheDocument())
  })

  it('guards confirmation in read-only mode but keeps refresh reads enabled', async () => {
    vi.mocked(listClusterDrafts).mockResolvedValue({
      items: [draft, { ...draft, id: 'submitted-one', name: 'Submitted run', status: 'submitted' }],
    } as never)
    renderSurface(<ClusterDrafts projectId={PROJECT_ID} readOnly />)

    const confirmButton = await screen.findByRole('button', { name: 'Confirm and submit' })
    expect(confirmButton).toBeDisabled()
    confirmButton.removeAttribute('disabled')
    fireEvent.click(confirmButton)
    await Promise.resolve()
    expect(confirmClusterDraft).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(getClusterDraft).toHaveBeenCalledWith('submitted-one'))
  })

  it('invalidates the draft list after a confirmed submission', async () => {
    const { client } = renderSurface(<ClusterDrafts projectId={PROJECT_ID} />)
    const invalidate = vi.spyOn(client, 'invalidateQueries')

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm and submit' }))

    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['cluster-drafts'] }),
    )
  })
})

describe('CopilotSettings', () => {
  it('uses registry form controls and preserves masked save/test outcomes', async () => {
    renderSurface(<CopilotSettings />)

    const baseUrl = await screen.findByRole('textbox', { name: 'API base URL' })
    const prompt = screen.getByRole('textbox', { name: 'Project prompt preferences (cannot override evidence or safety policy)' })
    const model = screen.getByRole('textbox', { name: 'Model' })
    expect(baseUrl).toHaveAttribute('data-slot', 'input')
    expect(model).toHaveAttribute('data-slot', 'input')
    expect(prompt).toHaveAttribute('data-slot', 'textarea')
    expect(screen.getByDisplayValue('')).toHaveAttribute('type', 'password')

    fireEvent.change(prompt, { target: { value: 'Prefer reviewed structures.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save configuration' }))

    await waitFor(() =>
      expect(updateCopilotConfig).toHaveBeenCalledWith(PROJECT_ID, {
        llm_api_base: 'https://api.example.test',
        llm_model: 'model-one',
        system_prompt: 'Prefer reviewed structures.',
      }),
    )
    expect(await screen.findByText('Configuration saved.')).toBeInTheDocument()
    expect(screen.getByText('Configuration saved.').closest('[data-slot="alert"]')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Test API' }))
    expect(await screen.findByText('Connected to model-one: OK')).toBeInTheDocument()
  })

  it('publishes stable external actions for the settings drawer footer', async () => {
    const onActionsReady = vi.fn()
    renderSurface(<CopilotSettings hideActions onActionsReady={onActionsReady} />)

    await screen.findByRole('textbox', { name: 'API base URL' })
    await waitFor(() =>
      expect(onActionsReady.mock.calls.at(-1)?.[0]).toMatchObject({
        savePending: false,
        testPending: false,
        canSave: true,
        canTest: true,
      }),
    )

    const actions = onActionsReady.mock.calls.at(-1)?.[0]
    actions.save()
    await waitFor(() => expect(updateCopilotConfig).toHaveBeenCalledTimes(1))
  })
})

describe('CopilotLoadingBubble', () => {
  it('matches the final Frame shape with registry Skeleton and reduced-motion animation guards', () => {
    renderSurface(<CopilotLoadingBubble stage="thinking" />)

    expect(screen.getByRole('status')).toHaveAttribute('data-slot', 'frame-panel')
    expect(document.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(3)
    expect(document.querySelector('[data-slot="skeleton"]')).toHaveClass('motion-reduce:animate-none')
  })

  it('localizes the unnamed tool fallback in both supported languages', () => {
    renderSurface(<CopilotLoadingBubble stage="tool" />)
    expect(screen.getByText('Using tool…')).toBeInTheDocument()

    cleanup()
    useAppStore.setState({ language: 'zh' })
    renderSurface(<CopilotLoadingBubble stage="tool" />)
    expect(screen.getByText('正在使用 工具…')).toBeInTheDocument()
  })
})
