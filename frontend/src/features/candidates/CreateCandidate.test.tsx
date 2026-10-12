import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CreateCandidate } from './CreateCandidate'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import type { Candidate } from '../../lib/schemas/candidate'

const api = vi.hoisted(() => ({ create: vi.fn(), update: vi.fn(), writable: true }))
vi.mock('../../lib/api/candidates', () => ({ createCandidate: api.create, updateCandidate: api.update }))
vi.mock('../../lib/hooks/useProjectAccess', () => ({ useProjectAccess: () => ({ data: { permissions: { write: api.writable } } }) }))
const proposal = { id: 'candidate-a', project_id: 'project-a', name: 'Proposal', properties: {}, version: 1 } as Candidate
beforeEach(() => { vi.clearAllMocks(); api.writable = true; useAppStore.setState({ language: 'en', appMode: 'application' }); api.create.mockResolvedValue(proposal) })
afterEach(cleanup)

function fill() {
  fireEvent.click(screen.getByRole('button', { name: 'Add candidate manually' }))
  fireEvent.change(screen.getByLabelText('Candidate name'), { target: { value: '  New proposal  ' } })
  fireEvent.change(screen.getByLabelText('Design rationale and open questions'), { target: { value: 'Compare to the published reference; activity untested.' } })
}

describe('manual candidate proposals', () => {
  it('creates a proposal without fabricated sequence, score or experimental success', async () => {
    const done = vi.fn()
    renderWithProviders(<CreateCandidate projectId="project-a" onCreated={done} />)
    fill()
    fireEvent.click(screen.getByRole('button', { name: 'Save candidate proposal' }))
    await waitFor(() => expect(done).toHaveBeenCalledWith(proposal))
    const [project, body] = api.create.mock.calls[0]
    expect(project).toBe('project-a')
    expect(body).toMatchObject({ name: 'New proposal', status: 'proposed', properties: { review_status: 'pending_review', experimental_status: 'not_tested', evidence_links: [] } })
    expect(body.properties).not.toHaveProperty('sequence')
    expect(body).not.toHaveProperty('scores')
  })
  it('validates sequence and source then retains the input after a server error', async () => {
    api.create.mockRejectedValue(new Error('Service unavailable'))
    renderWithProviders(<CreateCandidate projectId="project-a" onCreated={vi.fn()} />)
    fill()
    fireEvent.change(screen.getByLabelText(/Amino-acid sequence/), { target: { value: '>FASTA\nACD*' } })
    expect(screen.getByRole('button', { name: 'Save candidate proposal' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/Amino-acid sequence/), { target: { value: 'ac d\nEF' } })
    fireEvent.change(screen.getByLabelText(/Paper or source URL/), { target: { value: 'javascript:alert(1)' } })
    expect(screen.getByRole('button', { name: 'Save candidate proposal' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/Paper or source URL/), { target: { value: 'https://pubmed.ncbi.nlm.nih.gov/20302879/' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save candidate proposal' }))
    expect(await screen.findByText('Service unavailable')).toBeInTheDocument()
    expect(screen.getByLabelText('Candidate name')).toHaveValue('  New proposal  ')
    expect(api.create.mock.calls[0][1].properties.sequence).toBe('ACDEF')
  })
  it.each(['viewer', 'demo'])('keeps creation unavailable for %s', (mode) => {
    api.writable = mode !== 'viewer'
    if (mode === 'demo') useAppStore.setState({ appMode: 'demo' })
    renderWithProviders(<CreateCandidate projectId="project-a" onCreated={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Add candidate manually' })).toBeDisabled()
    expect(api.create).not.toHaveBeenCalled()
  })
  it('updates only rationale fields with the current version, preserving historical properties and sequence', async () => {
    api.update.mockRejectedValue(new Error('Candidate was modified by another request'))
    const old = { ...proposal, version: 7, properties: { sequence: 'ACDX', origin: 'historical', evidence_links: ['https://example.org/one', 'https://example.org/two'] } }
    renderWithProviders(<CreateCandidate projectId="project-a" candidate={old} onCreated={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Edit candidate rationale' }))
    expect(screen.getByLabelText(/Amino-acid sequence/)).toHaveAttribute('readonly')
    fireEvent.change(screen.getByLabelText('Design rationale and open questions'), { target: { value: 'Additional source interpretation.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save candidate rationale' }))
    expect(await screen.findByText('Candidate was modified by another request')).toBeInTheDocument()
    expect(api.update).toHaveBeenCalledWith('candidate-a', 7, { name: 'Proposal', properties: { ...old.properties, design_rationale: 'Additional source interpretation.' } })
  })
  it('does not navigate a new project when an old project save finishes after unmount', async () => {
    let finish!: (candidate: Candidate) => void
    api.create.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
    const done = vi.fn()
    const view = renderWithProviders(<CreateCandidate projectId="project-a" onCreated={done} />)
    fill(); fireEvent.click(screen.getByRole('button', { name: 'Save candidate proposal' }))
    await waitFor(() => expect(api.create).toHaveBeenCalledTimes(1))
    view.unmount()
    await act(async () => finish(proposal))
    expect(done).not.toHaveBeenCalled()
  })
})
