import { cleanup, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { AdministrationSections } from './AdministrationSections'

const api = vi.hoisted(() => ({
  organizations: vi.fn(),
  members: vi.fn(),
  audit: vi.fn(),
  summary: vi.fn(),
}))

vi.mock('../../lib/api/administration', () => ({
  listOrganizations: api.organizations,
  listOrganizationMembers: api.members,
  listAuditLogs: api.audit,
  getOperationsSummary: api.summary,
  createOrganization: vi.fn(),
  addOrganizationMember: vi.fn(),
}))

describe('AdministrationSections', () => {
  beforeEach(() => {
    api.organizations.mockResolvedValue([{ id: 'org-1', name: 'Org One', version: 1 }])
    api.members.mockResolvedValue([
      { user_id: 'user-1', username: 'bench-mate', display_name: 'Bench Mate', role: 'researcher' },
    ])
    api.summary.mockResolvedValue({
      jobs_by_status: { succeeded: 3 },
      operations_by_status: { running: 1, succeeded: 9 },
      outbox_backlog: 2,
      missing_artifacts: 0,
      registry_health: {},
      latest_migration_status: 'succeeded',
    })
    api.audit.mockResolvedValue([
      {
        id: 'audit-1',
        action: 'job.submit',
        entity_type: 'job',
        result: 'allowed',
        trace_id: 'trace-abc',
        created_at: '2026-08-28T00:00:00Z',
      },
    ])
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders nothing for a non-admin rather than controls that would 403', async () => {
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'researcher' }))
    const { container } = renderWithProviders(<AdministrationSections />)
    expect(container).toBeEmptyDOMElement()
    expect(api.organizations).not.toHaveBeenCalled()
  })

  it('shows members by name, and the audit trail with its trace id', async () => {
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'admin' }))
    renderWithProviders(<AdministrationSections />)

    // The point of the new read endpoint: a membership shown as a person, not a UUID.
    expect(await screen.findByText('Bench Mate')).toBeInTheDocument()
    expect(screen.getByText('bench-mate')).toBeInTheDocument()

    expect(await screen.findByText('job.submit')).toBeInTheDocument()
    expect(screen.getByText(/trace-abc/)).toBeInTheDocument()
  })

  it('makes a non-zero backlog visible, since that is the number that means stuck', async () => {
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'admin' }))
    renderWithProviders(<AdministrationSections />)
    expect(await screen.findByText('Undelivered events')).toBeInTheDocument()
    // Awaited, not read synchronously: the label renders before the count arrives.
    expect(await screen.findByText('2')).toBeInTheDocument()
  })
})
