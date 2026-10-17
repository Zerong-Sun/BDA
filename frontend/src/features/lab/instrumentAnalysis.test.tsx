import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { InstrumentAnalysis } from './InstrumentAnalysis'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/mocks/handlers'
import { useAppStore } from '../../lib/store/appStore'
import { traceStyle } from './traceStyle'
import {
  AktaSummarySchema,
  BliSummarySchema,
  EnzymeSummarySchema,
} from '../../lib/schemas/instrumentAnalysis'

vi.mock('../../lib/api/artifacts', () => ({
  uploadArtifact: vi.fn(async () => ({ id: 'artifact-1' })),
}))

vi.mock('../../lib/api/wetlab', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../../lib/api/wetlab')
  return { ...actual, analyseBli: vi.fn(), analyseAkta: vi.fn(), analyseEnzyme: vi.fn(), previewInstrumentAnalysis: vi.fn(), listSavedInstrumentAnalyses: vi.fn() }
})

const { uploadArtifact } = await import('../../lib/api/artifacts')
const { analyseBli, previewInstrumentAnalysis, listSavedInstrumentAnalyses } = await import('../../lib/api/wetlab')

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <InstrumentAnalysis projectId="project-1" />
    </QueryClientProvider>,
  )
}

function choose(file: File) {
  fireEvent.change(screen.getByLabelText('Export file'), { target: { files: [file] } })
}

beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
  useAppStore.setState({ appMode: 'application', language: 'en' })
  server.use(http.get('/api/v2/projects/:id/access', () => HttpResponse.json({ project_id: 'project-1', role: 'owner', permissions: { read: true, write: true, compute: true, experiment: true, autopilot: true } })))
})
afterEach(() => vi.restoreAllMocks())

describe('instrument analysis panel', () => {
  it('previews without a project, then clears the result when the file changes', async () => {
    vi.mocked(previewInstrumentAnalysis).mockResolvedValue({
      instrument: 'bli', record: {
        experiment_result_id: '', source_artifact_id: '', experiment_type: 'bli_affinity',
        analysis_version: 'bli/2', value: 12.5, unit: 'nM',
      },
      summary: BliSummarySchema.parse({
          sample_id: 'S1', samples_available: ['S1'], kd_nM: 12.5,
          methods: { standard: { kd: 12.5, r2: 0.99 }, split: null, joint: null, steady: null, mixed: null },
          phase: { t_assoc: 60, t_dissoc: 180 }, curves: [],
        }),
    } as never)
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    render(<QueryClientProvider client={client}><InstrumentAnalysis projectId="" previewOnly /></QueryClientProvider>)
    choose(new File(['export'], 'preview.csv'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview without saving' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save to selected project' })).toBeDisabled())
    expect(uploadArtifact).not.toHaveBeenCalled()
    expect(analyseBli).not.toHaveBeenCalled()
    choose(new File(['another export'], 'replacement.csv'))
    expect(screen.queryByRole('button', { name: 'Save to selected project' })).not.toBeInTheDocument()
  })

  it('uploads the file first and posts only its artifact id', async () => {
    // The platform's upload contract, not a preference: the API never receives a
    // file body, so a panel that posted one would 422 on every real export.
    vi.mocked(analyseBli).mockResolvedValue({
      experiment_result_id: 'result-1',
      experiment_type: 'bli_affinity',
      analysis_version: 'bli/2',
      value: 12.5,
      unit: 'nM',
      source_artifact_id: 'artifact-1',
      summary: BliSummarySchema.parse({
        sample_id: 'S1',
        samples_available: ['S1'],
        kd_nM: 12.5,
        methods: {
          standard: { kd: 12.5, r2: 0.99 },
          split: null,
          joint: { kd: 12.1, r2: 0.98 },
          steady: null,
          mixed: null,
        },
        phase: { t_assoc: 60, t_dissoc: 180 },
        curves: [{ label: 'A1', conc_nM: 100, points: [[0, 0], [1, 0.4]] }],
      }),
    })

    renderPanel()
    const file = new File(['t,y\n0,0\n'], 'run.csv', { type: 'text/csv' })
    choose(file)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Analyse' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: 'Analyse' }))

    await waitFor(() => expect(analyseBli).toHaveBeenCalled())
    expect(uploadArtifact).toHaveBeenCalledWith(file, 'project-1')
    expect(vi.mocked(analyseBli).mock.calls[0][1]).toMatchObject({ artifact_id: 'artifact-1' })
  })

  it('shows a method that did not converge rather than hiding it', async () => {
    // A KD four methods agree on means something different from one a single
    // method produced. Dropping the empty rows would erase that distinction.
    vi.mocked(analyseBli).mockResolvedValue({
      experiment_result_id: 'result-1',
      experiment_type: 'bli_affinity',
      analysis_version: 'bli/2',
      value: 12.5,
      unit: 'nM',
      source_artifact_id: 'artifact-1',
      summary: BliSummarySchema.parse({
        sample_id: 'S1',
        kd_nM: 12.5,
        methods: { standard: { kd: 12.5, r2: 0.99 }, split: null, joint: null, steady: null, mixed: null },
        phase: null,
        curves: [{ label: 'A1', conc_nM: 100, points: [[0, 0], [1, 0.4]] }],
      }),
    })

    renderPanel()
    choose(new File(['x'], 'run.csv', { type: 'text/csv' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Analyse' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: 'Analyse' }))

    await waitFor(() => expect(screen.getByLabelText('Sensorgrams')).toBeInTheDocument())
    expect(screen.getAllByText('did not converge')).toHaveLength(4)
    expect(screen.getByText('Joint')).toBeInTheDocument()
  })

  it('reports a failed analysis instead of leaving the panel blank', async () => {
    vi.mocked(analyseBli).mockRejectedValue(new Error('That file contained no usable curves.'))

    renderPanel()
    choose(new File(['x'], 'run.csv', { type: 'text/csv' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Analyse' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: 'Analyse' }))

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('no usable curves'),
    )
  })

  it('reanalyses the preserved artifact with lineage and candidate identity without uploading it again', async () => {
    const record = { experiment_result_id: 'previous', source_artifact_id: 'raw-1', candidate_id: 'candidate-1', experiment_type: 'bli_affinity', analysis_version: 'bli/3', value: 4, unit: 'nM', version: 1, qc_review: null }
    const summary = BliSummarySchema.parse({ sample_id: 'S1', methods: { standard: null, split: null, joint: null, steady: null, mixed: null }, phase: { t_assoc: 0, t_dissoc: 60 }, processing: { sample_mapping: { A1: 'S1' }, excluded_labels: ['A2'], baseline_mode: 'fitted_offset' }, selected_method: 'measured_global' })
    vi.mocked(listSavedInstrumentAnalyses).mockResolvedValue({ next_cursor: null, items: [{ label: 'original.csv', record, quality: null, analysis: { instrument: 'bli', record, summary }, summaryError: null }] })
    vi.mocked(analyseBli).mockResolvedValue({ ...record, experiment_result_id: 'next', summary })
    renderPanel()
    fireEvent.click(screen.getByRole('button', { name: 'Load saved results' }))
    fireEvent.click(await screen.findByRole('button', { name: /S1 · KD 4 nM · unreviewed.*original.csv/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Edit parameters and create a new version' }))
    fireEvent.click(screen.getByRole('button', { name: 'Sample mapping, reference subtraction and processing' }))
    fireEvent.change(screen.getByLabelText('Correction and processing note'), { target: { value: 'Review phase boundaries' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save new analysis version' }))
    await waitFor(() => expect(analyseBli).toHaveBeenCalledWith('project-1', expect.objectContaining({ artifact_id: 'raw-1', supersedes_result_id: 'previous', candidate_id: 'candidate-1', correction_note: 'Review phase boundaries', baseline_mode: 'fitted_offset', sample_mapping: { A1: 'S1' }, excluded_labels: ['A2'] })))
    expect(uploadArtifact).not.toHaveBeenCalled()
  })

  it('cannot be submitted without a file', () => {
    renderPanel()
    expect(screen.getByRole('button', { name: 'Analyse' })).toBeDisabled()
  })
})

describe('analysis summary parsing', () => {
  it('rejects a curve that is not a series of pairs', () => {
    // An unvalidated curve arriving as undefined draws an empty chart rather
    // than raising, which is the worst way for a plot of a measurement to fail.
    expect(() =>
      BliSummarySchema.parse({
        sample_id: 'S1',
        methods: { standard: null, split: null, joint: null, steady: null, mixed: null },
        curves: [{ label: 'A1', conc_nM: 1, points: [[0]] }],
      }),
    ).toThrow()
  })

  it('keeps an unknown fit field rather than dropping it', () => {
    // The kernels return more per method than any one screen shows; a strict
    // object would turn added detail into a parse failure.
    const parsed = BliSummarySchema.parse({
      sample_id: 'S1',
      methods: {
        standard: { kd: 1, r2: 0.9, kobs_points: 5 },
        split: null,
        joint: null,
        steady: null,
        mixed: null,
      },
    })
    expect(parsed.methods.standard).toMatchObject({ kobs_points: 5 })
  })

  it('defaults an absent trace to empty so the chart simply does not render', () => {
    const akta = AktaSummarySchema.parse({ channel: 'UV1', peak_count: 0 })
    expect(akta.trace).toEqual([])
    expect(akta.peaks).toEqual([])
  })

  it('accepts a well whose slope could not be fitted', () => {
    const enzyme = EnzymeSummarySchema.parse({
      well_count: 1,
      fits: { A1: { slope: null, intercept: null, r2: null, n: 1 } },
    })
    expect(enzyme.fits.A1.slope).toBeNull()
  })
})

describe('trace styling', () => {
  it('uses solid measured traces and dashed fitted traces with the same series color', () => {
    expect(traceStyle(0)).toEqual({ stroke: 'var(--color-chart-1)', dash: 'none' })
    expect(traceStyle(5).dash).toBe('none')
    expect(traceStyle(0, 'fitted').stroke).toBe(traceStyle(0).stroke)
    expect(traceStyle(0, 'fitted').dash).not.toBe('none')
    expect(traceStyle(0, 'simulated').dash).not.toBe(traceStyle(0, 'fitted').dash)
  })
})

it('keeps saved analyses available but blocks uploads when experiment access is denied', async () => {
  server.use(http.get('/api/v2/projects/:id/access', () => HttpResponse.json({ project_id: 'project-1', role: 'viewer', permissions: { read: true, write: false, experiment: false, compute: false, autopilot: false } })))
  renderPanel()
  expect(await screen.findByText(/You can browse saved analyses/)).toBeVisible()
  expect(screen.getByLabelText('Export file')).toBeDisabled()
  choose(new File(['export'], 'test.csv'))
  fireEvent.click(screen.getByRole('button', { name: 'Analyse' }))
  expect(uploadArtifact).not.toHaveBeenCalled()
  expect(analyseBli).not.toHaveBeenCalled()
})
