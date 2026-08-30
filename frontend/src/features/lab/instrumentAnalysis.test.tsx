import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { InstrumentAnalysis } from './InstrumentAnalysis'
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
  return { ...actual, analyseBli: vi.fn(), analyseAkta: vi.fn(), analyseEnzyme: vi.fn() }
})

const { uploadArtifact } = await import('../../lib/api/artifacts')
const { analyseBli } = await import('../../lib/api/wetlab')

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

beforeEach(() => vi.clearAllMocks())
afterEach(() => vi.restoreAllMocks())

describe('instrument analysis panel', () => {
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
    fireEvent.click(screen.getByRole('button', { name: 'Analyse' }))

    await waitFor(() => expect(screen.getByLabelText('Sensorgrams')).toBeInTheDocument())
    expect(screen.getAllByText('did not converge')).toHaveLength(4)
  })

  it('reports a failed analysis instead of leaving the panel blank', async () => {
    vi.mocked(analyseBli).mockRejectedValue(new Error('That file contained no usable curves.'))

    renderPanel()
    choose(new File(['x'], 'run.csv', { type: 'text/csv' }))
    fireEvent.click(screen.getByRole('button', { name: 'Analyse' }))

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('no usable curves'),
    )
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
  it('wraps into a dash rather than repeating a colour', () => {
    // Five theme colours, and a BLI run can carry eight concentrations. Two
    // curves that look identical are worse than one drawn dashed.
    expect(traceStyle(0)).toEqual({ stroke: 'var(--color-chart-1)', dash: 'none' })
    expect(traceStyle(5).stroke).toBe(traceStyle(0).stroke)
    expect(traceStyle(5).dash).not.toBe(traceStyle(0).dash)
  })
})
