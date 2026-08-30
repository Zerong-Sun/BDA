import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ExperimentUpload } from './ExperimentUpload'

const uploadExperimentResults = vi.fn()
const awaitImportReport = vi.fn()

vi.mock('../../lib/api/experiments', async () => {
  const actual = await vi.importActual<typeof import('../../lib/api/experiments')>(
    '../../lib/api/experiments',
  )
  return {
    ...actual,
    uploadExperimentResults: (...args: unknown[]) => uploadExperimentResults(...args),
    awaitImportReport: (...args: unknown[]) => awaitImportReport(...args),
  }
})

function upload() {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  const file = new File(['candidate_ref,experiment_type,value\n'], 'results.csv', { type: 'text/csv' })
  fireEvent.change(input, { target: { files: [file] } })
}

describe('ExperimentUpload', () => {
  beforeEach(() => {
    uploadExperimentResults.mockReset().mockResolvedValue({ imported: 0, batch_id: 'op-1' })
    awaitImportReport.mockReset()
  })

  it('surfaces row-level errors instead of only saying the import was queued', async () => {
    awaitImportReport.mockResolvedValue({
      status: 'succeeded',
      error: null,
      report: {
        imported: 8,
        skipped: 2,
        unlinked: 1,
        ignored_columns: ['notes'],
        errors: [
          { row: 3, column: 'value', message: "'N/A' is not a number" },
          { row: 9, column: 'experiment_type', message: 'experiment_type is required' },
        ],
      },
    })
    render(<ExperimentUpload projectId="p1" />)
    upload()

    await waitFor(() => expect(screen.getByTestId('import-report')).toBeTruthy())
    // Counts, so a partially-successful import is not mistaken for a clean one.
    expect(screen.getByText('8')).toBeTruthy()
    expect(screen.getByText("'N/A' is not a number")).toBeTruthy()
    expect(screen.getByText('experiment_type is required')).toBeTruthy()
    // Unrecognised columns are reported rather than silently dropped.
    expect(screen.getByText(/notes/)).toBeTruthy()
  })

  it('reports unlinked candidate references', async () => {
    awaitImportReport.mockResolvedValue({
      status: 'succeeded',
      error: null,
      report: { imported: 5, skipped: 0, unlinked: 3, ignored_columns: [], errors: [] },
    })
    render(<ExperimentUpload projectId="p1" />)
    upload()

    await waitFor(() => expect(screen.getByTestId('import-report')).toBeTruthy())
    expect(screen.getByText('3')).toBeTruthy()
  })

  it('does not render a report panel before an import has run', () => {
    render(<ExperimentUpload projectId="p1" />)
    expect(screen.queryByTestId('import-report')).toBeNull()
  })
})
