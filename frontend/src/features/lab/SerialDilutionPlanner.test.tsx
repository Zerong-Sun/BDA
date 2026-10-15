import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { planDilutionSeries } from '../../lib/api/wetlab'
import { SerialDilutionPlanner } from './SerialDilutionPlanner'

vi.mock('../../lib/api/wetlab', () => ({ planDilutionSeries: vi.fn() }))
beforeEach(() => {
  useAppStore.setState({ language: 'en' })
  vi.mocked(planDilutionSeries).mockResolvedValue({ steps: [
    { step: 1, conc_uM: 50, stock_vol_uL: 165, buffer_vol_uL: 165, total_vol_uL: 330 },
    { step: 2, conc_uM: 25, stock_vol_uL: 110, buffer_vol_uL: 110, total_vol_uL: 220 },
  ] })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })

describe('Serial dilution planner', () => {
  it('shows source and onward transfer separately with retained volume and dead reserve', async () => {
    renderWithProviders(<SerialDilutionPlanner />)
    fireEvent.change(screen.getByLabelText('Tube count (1–24)'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Plan dilution' }))
    expect(await screen.findByRole('region', { name: 'Serial dilution steps' })).toBeInTheDocument()
    expect(planDilutionSeries).toHaveBeenCalledWith({ stock_conc_uM: 100, start_conc_uM: 50, dilution_factor: 2, n_steps: 2, vol_per_well_uL: 200, extra_dead_vol_uL: 20 })
    const rows = screen.getAllByRole('row')
    expect(within(rows[1]).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['1', '50', 'Stock solution', '165', '165', '330', '110', '220', '20'])
    expect(within(rows[2]).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['2', '25', 'Tube 1', '110', '110', '220', '0', '220', '20'])
    expect(screen.getByText(/Retained volume includes that reserve/)).toHaveTextContent('200 µL for use + 20 µL dead reserve')
    expect(screen.getByText(/Prepared volumes can differ/)).toBeInTheDocument()
  })

  it('does not display an old plan under edited parameters and reports server validation', async () => {
    renderWithProviders(<SerialDilutionPlanner />)
    fireEvent.click(screen.getByRole('button', { name: 'Plan dilution' }))
    await screen.findByRole('region', { name: 'Serial dilution steps' })
    fireEvent.change(screen.getByLabelText('First tube concentration (µM)'), { target: { value: '200' } })
    expect(screen.queryByRole('region', { name: 'Serial dilution steps' })).not.toBeInTheDocument()
    vi.mocked(planDilutionSeries).mockRejectedValue(new Error('Start concentration exceeds stock'))
    fireEvent.click(screen.getByRole('button', { name: 'Plan dilution' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Start concentration exceeds stock')
  })

  it('rejects underflowed dead-volume input instead of silently removing the reserve', async () => {
    renderWithProviders(<SerialDilutionPlanner />)
    fireEvent.change(screen.getByLabelText('Dead reserve per tube (µL)'), { target: { value: '1e-400' } })
    fireEvent.click(screen.getByRole('button', { name: 'Plan dilution' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('outside numeric range')
    expect(planDilutionSeries).not.toHaveBeenCalled()
  })

  it('preserves small transfer magnitudes instead of displaying them as zero', async () => {
    vi.mocked(planDilutionSeries).mockResolvedValue({ steps: [{ step: 1, conc_uM: 0.0000001, stock_vol_uL: 0.0000002, buffer_vol_uL: 219.9999998, total_vol_uL: 220 }] })
    renderWithProviders(<SerialDilutionPlanner />)
    fireEvent.click(screen.getByRole('button', { name: 'Plan dilution' }))
    await waitFor(() => expect(screen.getByText('2e-7')).toBeInTheDocument())
    expect(screen.getByText(/Display precision does not imply pipette precision/)).toBeInTheDocument()
  })
})
