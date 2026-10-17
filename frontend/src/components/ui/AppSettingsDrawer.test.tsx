import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { AppSettingsDrawer } from './AppSettingsDrawer'
import { getCopilotConfig } from '../../lib/api/copilot'
import { getClusterHealth } from '../../lib/api/registry'

vi.mock('../../lib/auth/account', async (original) => ({
  ...await original<typeof import('../../lib/auth/account')>(),
  useAuthConfig: () => ({ data: { deployment_kind: 'public', private_portal_url: 'http://localhost:5177' } }),
}))

vi.mock('../../features/copilot/CopilotSettings', () => ({
  CopilotSettings: () => <div data-testid="copilot-settings" />,
}))

vi.mock('../../features/tour', () => ({
  findDemoProject: () => undefined,
}))

vi.mock('../../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => ({
    projects: [],
    projectId: '',
    setProjectId: vi.fn(),
  }),
}))

vi.mock('../../lib/api/health', () => ({
  getHealth: vi.fn().mockResolvedValue({
    status: 'ok',
    service: 'bda-api',
    checks: {},
  }),
}))

vi.mock('../../lib/api/registry', () => ({
  getClusterHealth: vi.fn().mockResolvedValue({
    connected: true,
    host: 'test',
    queues: [],
  }),
  // The compute-targets section lives in this drawer, so the drawer's tests need the
  // registry reads it makes. Empty is the interesting default: it is the state where
  // the panel has to offer a way to register one.
  listComputeNodes: vi.fn().mockResolvedValue([]),
  createComputeNode: vi.fn(),
  disableComputeNode: vi.fn(),
  checkComputeNodeHealth: vi.fn(),
}))

vi.mock('../../lib/api/administration', () => ({
  // The administration panels render only for admins and this suite signs in as a
  // researcher, but the module still has to resolve.
  listOrganizations: vi.fn().mockResolvedValue([]),
  listOrganizationMembers: vi.fn().mockResolvedValue([]),
  listAuditLogs: vi.fn().mockResolvedValue([]),
  createOrganization: vi.fn(),
  addOrganizationMember: vi.fn(),
}))

vi.mock('../../lib/api/copilot', () => ({
  getCopilotConfig: vi.fn().mockResolvedValue({
    api_key_configured: false,
    llm_model: 'test-model',
  }),
}))

describe('AppSettingsDrawer', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.clearAllMocks()
    useAppStore.setState({ language: 'en', settingsOpen: true })
  })

  afterEach(() => { cleanup(); sessionStorage.clear() })

  it('does not request model configuration without a project when refreshing connections', async () => {
    renderWithProviders(<AppSettingsDrawer />)
    fireEvent.click(screen.getByRole('button', { name: /revalidate/i }))
    await waitFor(() => expect(getClusterHealth).toHaveBeenCalled())
    expect(getCopilotConfig).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Done' })).toBeVisible()
  })

  it('shows Private access instead of account, infrastructure and model controls for a visitor', async () => {
    sessionStorage.setItem('bda_user', JSON.stringify({ public_visitor: true, role: 'viewer' }))
    renderWithProviders(<AppSettingsDrawer />)
    expect(await screen.findByRole('link', { name: /Create a Private account/ })).toHaveAttribute('href', 'http://localhost:5177/#/register')
    expect(screen.queryByTestId('copilot-settings')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /password, invitations/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /revalidate/i }))
    expect(getClusterHealth).not.toHaveBeenCalled()
    expect(getCopilotConfig).not.toHaveBeenCalled()
  })

  it('closes the settings sheet with Escape', () => {
    renderWithProviders(<AppSettingsDrawer />)

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
