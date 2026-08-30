import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { AppSettingsDrawer } from './AppSettingsDrawer'

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
    useAppStore.setState({ language: 'en', settingsOpen: true })
  })

  afterEach(cleanup)

  it('closes the settings sheet with Escape', () => {
    renderWithProviders(<AppSettingsDrawer />)

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
