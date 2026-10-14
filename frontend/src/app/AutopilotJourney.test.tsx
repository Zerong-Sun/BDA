import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAppStore } from '../lib/store/appStore'
import { AutopilotPage } from './Autopilot'

const context = vi.hoisted(() => ({ projectId: 'project-a', canOperate: true, accessLoaded: true }))
const api = vi.hoisted(() => ({ draft: vi.fn(), confirm: vi.fn(), start: vi.fn(), cancel: vi.fn(), refresh: vi.fn(), takeover: vi.fn(), release: vi.fn(), complete: vi.fn() }))
vi.mock('../lib/hooks/useProjectContext', () => ({ useProjectContext: () => ({ projectId: context.projectId }) }))
vi.mock('../lib/hooks/useProjectAccess', () => ({ useProjectAccess: () => ({
  isSuccess: context.accessLoaded, data: context.accessLoaded ? { permissions: { autopilot: context.canOperate } } : undefined,
}) }))
vi.mock('../lib/api/autopilot', () => ({
  createAutopilotDraft: api.draft, confirmAutopilotDraft: api.confirm, startAutopilotCampaign: api.start,
  cancelAutopilotCampaign: api.cancel, getAutopilotCampaign: api.refresh, takeOverAutopilotCampaign: api.takeover,
  releaseAutopilotStage: api.release, completeAutopilotStage: api.complete,
}))

const campaign = { id: 'campaign-a', name: 'Reviewed plan', project_id: 'project-a', status: 'confirmed', version: 1, stages: [] }
const draft = { draft: { id: 'draft-a', project_id: 'project-a', normalized_spec: { stages: ['review'] } }, etag: 'W/"3"' }

beforeEach(() => {
  vi.clearAllMocks()
  context.projectId = 'project-a'
  context.canOperate = true
  context.accessLoaded = true
  useAppStore.setState({ language: 'en', appMode: 'application' })
  api.draft.mockResolvedValue(draft)
  api.confirm.mockResolvedValue(campaign)
  api.start.mockResolvedValue({ campaign_id: 'campaign-a', operation_id: 'op-a', status: 'queued' })
  api.refresh.mockResolvedValue({ ...campaign, status: 'running' })
})
afterEach(cleanup)

async function prepare() {
  fireEvent.change(screen.getByLabelText('Research request'), { target: { value: 'Review binder candidates and prepare the next study' } })
  fireEvent.click(screen.getByRole('button', { name: 'Generate structured preview' }))
  await screen.findByText(/"stages"/)
  fireEvent.change(screen.getByLabelText('Campaign name'), { target: { value: 'Reviewed plan' } })
  fireEvent.change(screen.getByLabelText('GPU-hour hard limit'), { target: { value: '1' } })
}

async function confirm() {
  await prepare()
  fireEvent.click(screen.getByRole('button', { name: 'Confirm plan and budget' }))
  await screen.findByRole('button', { name: 'Start confirmed plan' })
}

describe('autopilot review and execution boundaries', () => {
  it.each(['loading', 'viewer', 'demo'])('prevents draft creation when access is %s', (state) => {
    context.accessLoaded = state !== 'loading'
    context.canOperate = state !== 'viewer'
    if (state === 'demo') useAppStore.setState({ appMode: 'demo' })
    renderWithProviders(<AutopilotPage />)
    expect(screen.getByLabelText('Research request')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Generate structured preview' })).toBeDisabled()
    expect(api.draft).not.toHaveBeenCalled()
  })

  it('disables confirmed campaign actions if project access is revoked', async () => {
    const view = renderWithProviders(<AutopilotPage />)
    await confirm()
    context.canOperate = false
    view.rerender(<AutopilotPage />)
    expect(screen.getByRole('button', { name: 'Start confirmed plan' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Cancel campaign' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Take over' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Refresh stages' })).toBeEnabled()
  })

  it.each(['before response', 'after response'])('invalidates a preview when the request changes %s', async (timing) => {
    let resolve!: (value: typeof draft) => void
    api.draft.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
    renderWithProviders(<AutopilotPage />)
    fireEvent.change(screen.getByLabelText('Research request'), { target: { value: 'Original reviewed research request' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate structured preview' }))
    await waitFor(() => expect(resolve).toBeDefined())
    const change = () => fireEvent.change(screen.getByLabelText('Research request'), { target: { value: 'A different research request' } })
    if (timing === 'before response') change()
    await act(async () => resolve(draft))
    if (timing === 'after response') change()
    fireEvent.change(screen.getByLabelText('Campaign name'), { target: { value: 'Plan' } })
    fireEvent.change(screen.getByLabelText('GPU-hour hard limit'), { target: { value: '1' } })
    expect(await screen.findByText('The request changed. Generate a new preview before confirming.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm plan and budget' })).toBeDisabled()
    expect(api.confirm).not.toHaveBeenCalled()
  })

  it.each(['', '0', '-1', 'NaN', '1e309', '1000000000', '0.000001'])('rejects an invalid GPU-hour budget: %s', async (value) => {
    renderWithProviders(<AutopilotPage />)
    await prepare()
    fireEvent.change(screen.getByLabelText('GPU-hour hard limit'), { target: { value } })
    expect(screen.getByRole('button', { name: 'Confirm plan and budget' })).toBeDisabled()
    expect(api.confirm).not.toHaveBeenCalled()
  })

  it('freezes confirmed inputs, starts with the confirmed budget and reads the actual state back', async () => {
    renderWithProviders(<AutopilotPage />)
    await confirm()
    expect(screen.getByLabelText('Research request')).toBeDisabled()
    expect(screen.getByLabelText('Campaign name')).toBeDisabled()
    expect(screen.getByLabelText('GPU-hour hard limit')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Confirm plan and budget' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Start confirmed plan' }))
    await waitFor(() => expect(api.start).toHaveBeenCalledWith('campaign-a', 3600))
    await waitFor(() => expect(api.refresh).toHaveBeenCalledWith('campaign-a'))
    expect(screen.getByRole('button', { name: 'Start confirmed plan' })).toBeDisabled()
    expect(api.start).toHaveBeenCalledTimes(1)
  })

  it('clears the prior project campaign and rejects a late confirmation after switching project', async () => {
    let resolve!: (value: typeof campaign) => void
    api.confirm.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
    const view = renderWithProviders(<AutopilotPage />)
    await prepare()
    fireEvent.click(screen.getByRole('button', { name: 'Confirm plan and budget' }))
    await waitFor(() => expect(resolve).toBeDefined())
    context.projectId = 'project-b'
    view.rerender(<AutopilotPage />)
    await act(async () => resolve(campaign))
    expect(screen.getByLabelText('Research request')).toHaveValue('')
    expect(screen.getByLabelText('Campaign name')).toHaveValue('')
    expect(screen.queryByRole('button', { name: 'Start confirmed plan' })).not.toBeInTheDocument()
  })

  it('keeps campaign refresh and takeover in order so stale reads cannot restore old controls', async () => {
    let refresh!: (value: typeof campaign) => void
    let takeover!: (value: typeof campaign) => void
    api.refresh.mockImplementationOnce(() => new Promise((resolve) => { refresh = resolve }))
    api.takeover.mockImplementationOnce(() => new Promise((resolve) => { takeover = resolve }))
    renderWithProviders(<AutopilotPage />)
    await confirm()
    fireEvent.click(screen.getByRole('button', { name: 'Refresh stages' }))
    await waitFor(() => expect(refresh).toBeDefined())
    expect(screen.getByRole('button', { name: 'Take over' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Cancel campaign' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Start confirmed plan' })).toBeDisabled()
    await act(async () => refresh(campaign))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Take over' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: 'Take over' }))
    await waitFor(() => expect(takeover).toBeDefined())
    expect(screen.getByRole('button', { name: 'Refresh stages' })).toBeDisabled()
    await act(async () => takeover({ ...campaign, status: 'manual_takeover', version: 2 }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Refresh stages' })).toBeEnabled())
    expect(screen.getByRole('button', { name: 'Take over' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Cancel campaign' })).toBeDisabled()
  })

  it('does not offer stage release or completion after manual takeover', async () => {
    api.confirm.mockResolvedValue({ ...campaign, status: 'manual_takeover', stages: [{ id: 'stage-a', stage_key: 'review', status: 'ready', held: false, version: 1 }] })
    renderWithProviders(<AutopilotPage />)
    await confirm()
    expect(screen.getByRole('button', { name: 'Mark this stage done' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Cancel campaign' })).toBeDisabled()
  })
})
