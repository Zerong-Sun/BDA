import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { GateEvidencePanel } from './GateEvidencePanel'
import type { ScientificEvidence, ScientificGate, ScientificSource } from '../../lib/api/scientificGates'

const api = vi.hoisted(() => ({
  gates: vi.fn(), sources: vi.fn(), save: vi.fn(), review: vi.fn(),
  artifacts: vi.fn(), ingest: vi.fn(), retrieval: vi.fn(),
  access: vi.fn(),
}))
vi.mock('../../lib/i18n', () => ({ useI18n: () => ({ language: 'en' }) }))
vi.mock('../../lib/api/scientificGates', () => ({ scientificGates: api.gates,
  scientificSources: api.sources, saveScientificEvidence: api.save, reviewScientificEvidence: api.review }))
vi.mock('../../lib/api/artifacts', () => ({ listProjectArtifacts: api.artifacts }))
vi.mock('../../lib/api/copilot', () => ({ ingestLiterature: api.ingest }))
vi.mock('../../lib/api/evidenceNotes', () => ({ getEvidenceSourceRetrieval: api.retrieval }))
vi.mock('../../lib/hooks/useProjectAccess', async importOriginal => ({
  ...await importOriginal<typeof import('../../lib/hooks/useProjectAccess')>(),
  useProjectAccess: api.access,
}))

const source: ScientificSource = { document_id: 'doc-1', chunk_id: 'chunk-1', title: 'Verified primary paper',
  quote: 'A source passage whose method context must be reviewed.', locator: 'Methods paragraph 4' }
const evidence: ScientificEvidence = { id: 'evidence-1', approved: false, created_at: '2026-10-16T00:00:00Z',
  sources: [source], issues: [], evidence: { workflow_version: 3, sources: [], parameters: [],
    calibration: null, applicability: 'A scoped candidate that is awaiting scientific review.' } }
function gate(overrides: Partial<ScientificGate> = {}): ScientificGate {
  return { edge_id: 'edge-1', mode: 'automatic', required: true, allowed: false,
    blockers: ['scientific_evidence_approval_required'],
    binding: { project_id: 'project-1', workflow_version: 3, parameter_hash: 'hash-1',
      required_parameters: { 'node.filter.pae': 10 },
      required_methods: { 'node.filter.pae': { method_key: 'af2', method_version: 'multimer-v3' } } },
    items: [], ...overrides }
}
function setup(props: Partial<Parameters<typeof GateEvidencePanel>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const renderPanel = (next = props) => <QueryClientProvider client={client}><GateEvidencePanel
    workflowId="workflow-1" edgeId="edge-1" canWrite readOnly={false} {...next} /></QueryClientProvider>
  const result = render(renderPanel())
  return { client, rerender: (next: Parameters<typeof renderPanel>[0]) => result.rerender(renderPanel(next)) }
}
async function chooseSource() {
  fireEvent.click(await screen.findByRole('button', { name: 'Search imported sources' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Select candidate source' }))
}
async function fillCandidate() {
  await chooseSource()
  fireEvent.change(screen.getByLabelText('Methods supported by the paper (comma separated)'), { target: { value: 'af2' } })
  fireEvent.change(screen.getByLabelText('node.filter.pae unit'), { target: { value: 'angstrom' } })
  fireEvent.change(screen.getByLabelText('node.filter.pae scientific rationale'), { target: { value: 'Cross-chain error, using the declared method definition.' } })
  fireEvent.change(screen.getByLabelText('Applicability and limitations'), { target: { value: 'Applies only to the frozen method and requires local calibration.' } })
}

beforeEach(() => {
  vi.resetAllMocks()
  api.gates.mockResolvedValue({ workflow_version: 3, items: [gate()] })
  api.sources.mockResolvedValue({ items: [source] })
  api.artifacts.mockResolvedValue([])
  api.save.mockResolvedValue(evidence)
  api.review.mockResolvedValue(gate())
  api.ingest.mockResolvedValue({ id: 'search-1' })
  api.retrieval.mockResolvedValue({ search: { id: 'search-1', status: 'completed', result_count: 1 } })
  api.access.mockReturnValue({ data: { role: 'owner' }, error: null })
})

describe('GateEvidencePanel scientific evidence workflow', () => {
  it.each(['editor', undefined])('requires effective project management access, not just write permission (%s)', async role => {
    api.access.mockReturnValue({ data: role ? { role } : undefined, error: null })
    api.gates.mockResolvedValue({ workflow_version: 3, items: [gate({ items: [evidence] })] })
    setup()
    await fillCandidate()
    expect(screen.getByRole('button', { name: 'Save candidate evidence' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Administrator approval' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Administrator rejection' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Review rationale (at least 20 characters)')).not.toBeInTheDocument()
    expect(api.access).toHaveBeenCalledWith('project-1')
  })

  it.each([{ canWrite: false }, { readOnly: true }])('keeps $canWrite/$readOnly users read-only while permitting imported-source lookup', async props => {
    api.gates.mockResolvedValue({ workflow_version: 3, items: [gate({ items: [evidence] })] })
    setup(props)
    fireEvent.click(await screen.findByRole('button', { name: 'Search imported sources' }))
    expect(await screen.findByText(source.title)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Select candidate source' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Find papers and retrieve text' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Save candidate evidence' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Administrator approval' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Administrator rejection' })).not.toBeInTheDocument()
    expect(api.artifacts).not.toHaveBeenCalled()
    expect(api.save).not.toHaveBeenCalled()
    expect(api.review).not.toHaveBeenCalled()
  })

  it('saves an explicitly pending candidate without inventing missing calibration or approving it', async () => {
    setup()
    await fillCandidate()
    expect(screen.getByRole('combobox', { name: 'Local calibration report' })).toHaveTextContent('No calibration; keep pending')
    fireEvent.click(screen.getByRole('button', { name: 'Save candidate evidence' }))
    await waitFor(() => expect(api.save).toHaveBeenCalledTimes(1))
    expect(api.save).toHaveBeenCalledWith('workflow-1', 'edge-1', expect.objectContaining({
      workflow_version: 3, calibration: null,
      sources: [{ document_id: 'doc-1', chunk_id: 'chunk-1', quote: source.quote,
        locator: source.locator, supported_methods: ['af2'] }],
      parameters: [expect.objectContaining({ path: 'node.filter.pae', value: 10,
        method_key: 'af2', method_version: 'multimer-v3', source_indexes: [0] })],
    }))
    expect(await screen.findByRole('status')).toHaveTextContent('automatic release is not authorized')
    expect(api.review).not.toHaveBeenCalled()
  })

  it.each(['scientific_evidence_stale', 'scientific_calibration_required'])('does not approve an evidence record with %s', async issue => {
    api.gates.mockResolvedValue({ workflow_version: 3, items: [gate({ items: [{ ...evidence, issues: [issue] }] })] })
    setup()
    fireEvent.change(await screen.findByLabelText('Review rationale (at least 20 characters)'), { target: { value: 'This lengthy rationale cannot remove a scientific prerequisite.' } })
    expect(screen.getByRole('button', { name: 'Administrator approval' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Administrator approval' }))
    expect(api.review).not.toHaveBeenCalled()
  })

  it('reports loading failures and offers a retry instead of showing approval', async () => {
    api.gates.mockRejectedValueOnce(new Error('gate unavailable'))
    setup()
    expect(await screen.findByRole('alert')).toHaveTextContent('approval cannot be assumed')
    fireEvent.click(screen.getByRole('button', { name: 'Reload evidence' }))
    expect(await screen.findByText('Automatic gate is held at execution')).toBeInTheDocument()
  })

  it('hides cached approval and review controls when a background refresh fails', async () => {
    api.gates.mockResolvedValueOnce({ workflow_version: 3, items: [gate({ allowed: true,
      blockers: [], items: [{ ...evidence, approved: true }] })] })
    const { client } = setup()
    expect(await screen.findByText('Automatic gate has a current approval')).toBeInTheDocument()
    api.gates.mockRejectedValueOnce(new Error('Current gate state unavailable'))
    await act(async () => { await client.invalidateQueries({ queryKey: ['scientific-gates', 'workflow-1'] }) })
    expect(await screen.findByRole('alert')).toHaveTextContent('approval cannot be assumed')
    expect(screen.queryByText('Automatic gate has a current approval')).not.toBeInTheDocument()
    expect(screen.queryByText('Current approval')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Administrator approval' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save candidate evidence' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Reload evidence' }))
    expect(await screen.findByText('Automatic gate is held at execution')).toBeInTheDocument()
  })

  it('retries the same imported-source query after a transient failure', async () => {
    api.sources.mockRejectedValueOnce(new Error('Source service unavailable'))
    setup()
    fireEvent.change(await screen.findByLabelText('Paper search query'), { target: { value: 'same query' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search imported sources' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Source service unavailable')
    fireEvent.click(screen.getByRole('button', { name: 'Search imported sources' }))
    expect(await screen.findByText(source.title)).toBeInTheDocument()
    expect(api.sources).toHaveBeenCalledTimes(2)
    expect(api.sources).toHaveBeenLastCalledWith('workflow-1', 'edge-1', 'same query')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows source and save API errors explicitly without claiming a successful save', async () => {
    api.sources.mockRejectedValueOnce(new Error('Source service unavailable'))
    setup()
    fireEvent.click(await screen.findByRole('button', { name: 'Search imported sources' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Source service unavailable')
    fireEvent.change(screen.getByLabelText('Paper search query'), { target: { value: 'new source query' } })
    await fillCandidate()
    api.save.mockRejectedValueOnce(new Error('Evidence is stale; refresh workflow'))
    fireEvent.click(screen.getByRole('button', { name: 'Save candidate evidence' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Evidence is stale; refresh workflow')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('refreshes imported source text after external literature retrieval completes', async () => {
    api.sources.mockResolvedValueOnce({ items: [] })
    setup()
    fireEvent.click(await screen.findByRole('button', { name: 'Search imported sources' }))
    expect(await screen.findByText('No source match; revise the query or retrieve papers.')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Paper search query'), { target: { value: 'verified method publication' } })
    fireEvent.click(screen.getByRole('button', { name: 'Find papers and retrieve text' }))
    expect(await screen.findByText(source.title)).toBeInTheDocument()
    expect(api.ingest).toHaveBeenCalledWith('project-1', 'verified method publication', 5)
    expect(api.sources).toHaveBeenCalledTimes(2)
    expect(api.sources).toHaveBeenLastCalledWith('workflow-1', 'edge-1', '')
  })

  it.each(['workflow', 'edge', 'version'])('resets candidate selections when the %s context changes', async dimension => {
    const { client, rerender } = setup()
    await fillCandidate()
    expect(screen.getByLabelText('Source quote 1')).toBeInTheDocument()
    if (dimension === 'workflow') {
      // Deliberately identical edge IDs/hash: neither globally identifies the workflow.
      client.setQueryData(['scientific-gates', 'workflow-2'], { workflow_version: 3, items: [gate()] })
      rerender({ workflowId: 'workflow-2' })
    } else if (dimension === 'edge') {
      act(() => client.setQueryData(['scientific-gates', 'workflow-1'], { workflow_version: 3,
        items: [gate(), gate({ edge_id: 'edge-2' })] }))
      rerender({ edgeId: 'edge-2' })
    } else {
      const current = gate()
      act(() => client.setQueryData(['scientific-gates', 'workflow-1'], { workflow_version: 4,
        items: [{ ...current, binding: { ...current.binding, workflow_version: 4 } }] }))
    }
    await waitFor(() => expect(screen.queryByLabelText('Source quote 1')).not.toBeInTheDocument())
    expect(screen.getByLabelText('Applicability and limitations')).toHaveValue('')
    expect(screen.getByRole('button', { name: 'Save candidate evidence' })).toBeDisabled()
    expect(api.save).not.toHaveBeenCalled()
  })
})
