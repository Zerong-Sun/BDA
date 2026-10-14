import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { ResultsMetrics } from './ResultsMetrics'
import type { ResultsSummary } from '../../lib/api/projects'

it('distinguishes the absence of a reviewed KD from the absence of measurements', () => {
  const summary: ResultsSummary = {
    project_id: 'project', candidate_count: 2, experiment_result_count: 10,
    available_artifact_count: 1, tested_candidate_count: 2, passed_result_count: 0,
    failed_result_count: 0, unknown_result_count: 10, pass_rate: null,
    top_candidate_ids: [], best_result_id: null, best_result_value: null, best_result_unit: null,
  }
  const view = render(<ResultsMetrics summary={summary} />)
  expect(screen.getByText('Best reviewed KD')).toBeInTheDocument()
  expect(screen.getByText('No reviewed BLI value yet')).toBeInTheDocument()
  expect(screen.queryByText('No BLI measurement yet')).not.toBeInTheDocument()
  view.rerender(<ResultsMetrics summary={{ ...summary, best_result_id: 'reviewed-result', best_result_value: 2.3, best_result_unit: 'nM' }} />)
  expect(screen.getByText('2.3 nM')).toBeInTheDocument()
  expect(screen.getByText('reviewed-result')).toBeInTheDocument()
  expect(screen.queryByText('No reviewed BLI value yet')).not.toBeInTheDocument()
})
