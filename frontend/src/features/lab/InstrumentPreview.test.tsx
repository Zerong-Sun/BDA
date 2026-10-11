import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { uploadArtifact } from '../../lib/api/artifacts'
import { analyseBli, previewInstrumentAnalysis } from '../../lib/api/wetlab'
import { AktaSummarySchema, BliSummarySchema, EnzymeSummarySchema } from '../../lib/schemas/instrumentAnalysis'
import { InstrumentAnalysis } from './InstrumentAnalysis'

vi.mock('../../lib/api/artifacts', () => ({ uploadArtifact: vi.fn() }))
vi.mock('../../lib/api/wetlab', () => ({ previewInstrumentAnalysis: vi.fn(), analyseBli: vi.fn(), analyseAkta: vi.fn(), analyseEnzyme: vi.fn() }))
vi.mock('./SavedInstrumentReviews', () => ({ SavedInstrumentReviews: () => <p>Project history</p> }))
vi.mock('./InstrumentQuality', () => ({ InstrumentQuality: ({ projectId }: { projectId: string }) => <output aria-label="QC project">{projectId}</output> }))

const bli = BliSummarySchema.parse({ sample_id: 'S1', kd_nM: 12.5, methods: { standard: null, split: null, joint: null, steady: null, mixed: null } })
const record = { experiment_result_id: '', source_artifact_id: '', experiment_type: 'bli_affinity', analysis_version: 'bli/2', value: 12.5, unit: 'nM' }
const saved = { ...record, experiment_result_id: 'result-1', source_artifact_id: 'artifact-1', version: 1, summary: bli }

function client() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
}
function choose(filename = 'sample.csv') {
  fireEvent.change(screen.getByLabelText('Export file'), { target: { files: [new File(['export'], filename)] } })
}

beforeEach(() => {
  useAppStore.setState({ language: 'en' })
  vi.mocked(uploadArtifact).mockResolvedValue({ id: 'artifact-1' } as Awaited<ReturnType<typeof uploadArtifact>>)
  vi.mocked(analyseBli).mockResolvedValue(saved)
  vi.mocked(previewInstrumentAnalysis).mockResolvedValue({ instrument: 'bli', record, summary: bli })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })

describe('Single instrument previews', () => {
  it.each([
    ['bli', '.csv,text/csv', 'sample.csv'],
    ['akta', '.zip', 'sample.zip'],
    ['enzyme', '.xlsx', 'sample.xlsx'],
  ] as const)('previews %s without a project or a second instrument picker', async (instrument, accept, filename) => {
    const summary = instrument === 'bli' ? bli : instrument === 'akta' ? AktaSummarySchema.parse({ channel: 'UV1', peak_count: 0 }) : EnzymeSummarySchema.parse({ well_count: 0, fits: {} })
    vi.mocked(previewInstrumentAnalysis).mockResolvedValue({ instrument, record, summary } as never)
    render(<QueryClientProvider client={client()}><InstrumentAnalysis instrument={instrument} previewOnly /></QueryClientProvider>)
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Export file')).toHaveAttribute('accept', accept)
    choose(filename)
    fireEvent.click(screen.getByRole('button', { name: 'Preview without saving' }))
    await waitFor(() => expect(previewInstrumentAnalysis).toHaveBeenCalledWith(expect.any(File), expect.objectContaining({ instrument })))
    expect(await screen.findByRole('button', { name: 'Save to selected project' })).toBeDisabled()
    expect(screen.queryByText('Project history')).not.toBeInTheDocument()
    expect(uploadArtifact).not.toHaveBeenCalled()
    expect(analyseBli).not.toHaveBeenCalled()
  })

  it('requires a separate save action after a project is explicitly selected', async () => {
    const queryClient = client()
    const panel = (projectId?: string) => <QueryClientProvider client={queryClient}><InstrumentAnalysis instrument="bli" projectId={projectId} previewOnly /></QueryClientProvider>
    const view = render(panel())
    choose()
    fireEvent.click(screen.getByRole('button', { name: 'Preview without saving' }))
    expect(await screen.findByRole('button', { name: 'Save to selected project' })).toBeDisabled()
    view.rerender(panel('selected-project'))
    expect(screen.getByRole('button', { name: 'Save to selected project' })).toBeEnabled()
    expect(uploadArtifact).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Save to selected project' }))
    await waitFor(() => expect(analyseBli).toHaveBeenCalledWith('selected-project', expect.objectContaining({ artifact_id: 'artifact-1' })))
    expect(uploadArtifact).toHaveBeenCalledWith(expect.any(File), 'selected-project')
    expect(screen.getByLabelText('QC project')).toHaveTextContent('selected-project')
    view.rerender(panel('other-project'))
    expect(screen.getByLabelText('QC project')).toHaveTextContent('selected-project')
    expect(screen.queryByText('Project history')).not.toBeInTheDocument()
  })

  it('clears files and results when the controlling instrument changes', async () => {
    const queryClient = client()
    const panel = (instrument: 'bli' | 'akta') => <QueryClientProvider client={queryClient}><InstrumentAnalysis instrument={instrument} previewOnly /></QueryClientProvider>
    const view = render(panel('bli'))
    choose()
    fireEvent.click(screen.getByRole('button', { name: 'Preview without saving' }))
    await screen.findByRole('button', { name: 'Save to selected project' })
    view.rerender(panel('akta'))
    expect(screen.getByLabelText('Export file')).toHaveAttribute('accept', '.zip')
    expect(screen.getByRole('button', { name: 'Preview without saving' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Save to selected project' })).not.toBeInTheDocument()
    expect(screen.queryByText('sample.csv')).not.toBeInTheDocument()
  })
})
