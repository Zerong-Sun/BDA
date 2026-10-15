import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import { SavedInstrumentReviews } from './SavedInstrumentReviews'
import { BliSummarySchema } from '../../lib/schemas/instrumentAnalysis'
import { listSavedInstrumentAnalyses } from '../../lib/api/wetlab'

vi.mock('../../lib/api/wetlab', () => ({ listSavedInstrumentAnalyses: vi.fn(), reviewInstrumentAnalysis: vi.fn() }))
afterEach(() => { cleanup(); vi.clearAllMocks() })

it('filters instrument evidence by candidate without hiding pagination or treating unlinked records as matches', async () => {
  const record = { experiment_result_id: 'r', experiment_type: 'bli_affinity', value: 5, unit: 'nM', source_artifact_id: 'a', analysis_version: 'old', version: 1, qc_review: null }
  vi.mocked(listSavedInstrumentAnalyses).mockResolvedValue({ next_cursor: 'next', items: [
    { label: 'linked.csv', quality: null, analysis: null, summaryError: null, record: { ...record, candidate_id: 'a' } },
    { label: 'unlinked.csv', quality: null, analysis: null, summaryError: null, record: { ...record, experiment_result_id: 'unlinked', candidate_id: null } },
  ] })
  const client = new QueryClient()
  const view = render(<QueryClientProvider client={client}><SavedInstrumentReviews projectId="p" candidateId="b" autoLoad /></QueryClientProvider>)
  expect(await screen.findByText('No analyses for this candidate on the loaded pages; continue loading.')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Load more experiment records' })).toBeEnabled()
  expect(screen.queryByText(/unlinked.csv/)).not.toBeInTheDocument()
  view.rerender(<QueryClientProvider client={client}><SavedInstrumentReviews projectId="p" candidateId="a" autoLoad /></QueryClientProvider>)
  expect(await screen.findByRole('button', { name: 'linked.csv · unreviewed · r' })).toBeVisible()
  expect(screen.queryByText(/unlinked.csv/)).not.toBeInTheDocument()
  view.rerender(<QueryClientProvider client={client}><SavedInstrumentReviews projectId="p" autoLoad /></QueryClientProvider>)
  expect(await screen.findByRole('button', { name: 'unlinked.csv · unreviewed · unlinked' })).toBeVisible()
})

it('loads saved analyses on request and explicitly reads further experiment pages', async () => {
  vi.mocked(listSavedInstrumentAnalyses)
    .mockResolvedValueOnce({ next_cursor: 'next', items: [] })
    .mockResolvedValueOnce({ next_cursor: null, items: [{ label: 'historical.csv', quality: null, analysis: null, summaryError: null,
      record: { experiment_result_id: 'r', experiment_type: 'bli_affinity', value: 5, unit: 'nM',
        source_artifact_id: 'a', analysis_version: 'old', version: 1, qc_review: null } }] })
  render(<QueryClientProvider client={new QueryClient()}><SavedInstrumentReviews projectId="p" /></QueryClientProvider>)
  expect(listSavedInstrumentAnalyses).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Load saved results' }))
  await waitFor(() => expect(screen.getByText(/No instrument analyses on the loaded pages/)).toBeInTheDocument())
  fireEvent.click(screen.getByRole('button', { name: 'Load more experiment records' }))
  await waitFor(() => expect(listSavedInstrumentAnalyses).toHaveBeenLastCalledWith('p', 'next'))
  fireEvent.click(await screen.findByRole('button', { name: 'historical.csv · unreviewed · r' }))
  expect(screen.getByText(/missing diagnostics do not mean QC passed/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Refresh results and reviews' })).toBeInTheDocument()
})

it('reopens the persisted plot snapshot with its provenance and offers a new version', async () => {
  const record = { experiment_result_id: 'r', experiment_type: 'bli_affinity', value: 5, unit: 'nM', source_artifact_id: 'raw', analysis_version: 'bli-v3', version: 1, qc_review: null }
  const summary = BliSummarySchema.parse({ sample_id: 'S1', source_checksum_sha256: 'abc123', evidence_kind: 'measured_trace_fit', source_format: 'kinetic_triplets', processing: { analysis_method: 'measured_global', baseline_mode: 'initial_point', reference_label: null }, supersedes_result_id: 'prior',
    methods: { standard: null, split: null, joint: { kd: 5 }, steady: null, mixed: null }, curves: [{ label: 'A1', conc_nM: 10, points: [[0, 0], [1, 2]], analysis_fit_points: [[0, 0], [1, 1.8]] }] })
  const analysis = { instrument: 'bli' as const, record, summary }
  vi.mocked(listSavedInstrumentAnalyses).mockResolvedValue({ next_cursor: null, items: [{ label: 'saved.csv', quality: null, record, analysis, summaryError: null }] })
  const onReanalyse = vi.fn()
  render(<QueryClientProvider client={new QueryClient()}><SavedInstrumentReviews projectId="p" onReanalyse={onReanalyse} /></QueryClientProvider>)
  fireEvent.click(screen.getByRole('button', { name: 'Load saved results' }))
  fireEvent.click(await screen.findByRole('button', { name: 'S1 · KD 5 nM · unreviewed Measured global fit · Baseline: initial point · No reference subtraction saved.csv · bli-v3 · r' }))
  expect(screen.getByText('Global kinetics (shared kon/koff; per-sensor Rmax)')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Sensorgrams' })).toBeInTheDocument()
  expect(screen.getByText('SHA-256: abc123')).toBeInTheDocument()
  expect(screen.getByText('Supersedes analysis: prior')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Edit parameters and create a new version' }))
  expect(onReanalyse).toHaveBeenCalledWith(analysis, 'saved.csv')
})

it('distinguishes same-source samples and processing versions without implying instrument trace correction', async () => {
  const record = { experiment_result_id: 'first', experiment_type: 'bli_affinity', value: 0.012345, unit: 'nM', source_artifact_id: 'raw', analysis_version: 'bli-v3', version: 1, qc_review: { status: 'pending' } }
  const summary = BliSummarySchema.parse({ sample_id: 'S1', methods: {}, processing: { analysis_method: 'measured_global', baseline_mode: 'fitted_offset', reference_label: 'A1', reference_applied: true } })
  vi.mocked(listSavedInstrumentAnalyses).mockResolvedValue({ next_cursor: null, items: [
    { label: 'same.csv', quality: null, record, analysis: { instrument: 'bli', record, summary }, summaryError: null },
    { label: 'same.csv', quality: null, record: { ...record, experiment_result_id: 'second', analysis_version: 'bli-v4' }, analysis: { instrument: 'bli', record, summary: { ...summary, sample_id: 'S2', processing: { ...summary.processing, analysis_method: 'instrument_kobs', reference_applied: false } } }, summaryError: null },
  ] })
  render(<QueryClientProvider client={new QueryClient()}><SavedInstrumentReviews projectId="p" autoLoad /></QueryClientProvider>)
  expect(await screen.findByRole('button', { name: 'S1 · KD 0.0123 nM · pending Measured global fit · Baseline: fitted offset · Reference-subtracted: A1 same.csv · bli-v3 · first' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'S2 · KD 0.0123 nM · pending Instrument Kobs regression · Baseline: not applied · No reference subtraction same.csv · bli-v4 · second' })).toBeInTheDocument()
})
