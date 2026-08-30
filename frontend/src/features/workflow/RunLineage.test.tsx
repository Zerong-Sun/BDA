import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RunLineage } from './RunLineage'

describe('RunLineage', () => {
  it('presents a run with no ancestor as the baseline', () => {
    render(<RunLineage run={{ arm_label: 'baseline', varied_parameters: {}, derived_from_id: null }} />)
    expect(screen.getByText('Baseline')).toBeTruthy()
  })

  it('states plainly when exactly one parameter differs', () => {
    render(
      <RunLineage
        run={{
          arm_label: 'variant',
          derived_from_id: 'run-px90',
          varied_parameters: { proteinhunter: { percent_x: { from: 90, to: 50 } } },
        }}
      />,
    )
    expect(screen.getByText('Single-variable control: exactly one parameter differs.')).toBeTruthy()
    expect(screen.getByText('percent_x')).toBeTruthy()
    expect(screen.getByText('90')).toBeTruthy()
    expect(screen.getByText('50')).toBeTruthy()
  })

  it('refuses to let a multi-parameter run read as a controlled comparison', () => {
    render(
      <RunLineage
        run={{
          arm_label: 'variant',
          derived_from_id: 'run-px90',
          varied_parameters: {
            proteinhunter: {
              percent_x: { from: 90, to: 50 },
              num_designs: { from: 5, to: 100 },
              temperature: { from: 0.1, to: 0.5 },
            },
          },
        }}
      />,
    )
    expect(screen.getByText('3 parameters differ — not a single-variable comparison.')).toBeTruthy()
    expect(screen.queryByText(/Single-variable control/)).toBeNull()
  })

  it('marks an identical rerun as a replicate', () => {
    render(
      <RunLineage run={{ arm_label: 'replicate', derived_from_id: 'run-px50', varied_parameters: {} }} />,
    )
    expect(screen.getByText('Replicate')).toBeTruthy()
    expect(screen.getByText('Identical parameters — an independent repeat of the same experiment.')).toBeTruthy()
  })

  it('shows an empty string as such rather than as a blank cell', () => {
    render(
      <RunLineage
        run={{
          arm_label: 'variant',
          derived_from_id: 'run-a',
          varied_parameters: { ph: { contact_residues: { from: '', to: 'O1' } } },
        }}
      />,
    )
    // A parameter going from unset to set is a real change and must be visible.
    expect(screen.getByText('(empty)')).toBeTruthy()
    expect(screen.getByText('O1')).toBeTruthy()
  })
})
