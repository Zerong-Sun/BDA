import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import { SavedInstrumentReviews } from './SavedInstrumentReviews'
import { listSavedInstrumentAnalyses } from '../../lib/api/wetlab'

vi.mock('../../lib/api/wetlab', () => ({ listSavedInstrumentAnalyses: vi.fn(), reviewInstrumentAnalysis: vi.fn() }))
afterEach(() => { cleanup(); vi.clearAllMocks() })

it('loads saved analyses on request and explicitly reads further experiment pages', async () => {
  vi.mocked(listSavedInstrumentAnalyses)
    .mockResolvedValueOnce({ next_cursor: 'next', items: [] })
    .mockResolvedValueOnce({ next_cursor: null, items: [{ label: 'historical.csv', quality: null,
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
