import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { BenchToolForm } from './BenchToolForm'
import { BENCH_TOOLS, calculationPayload, initialToolValues } from './toolCatalog'
import { ToolsPage } from '../../app/Tools'

const api = vi.hoisted(() => ({ calculate: vi.fn() }))
vi.mock('../../lib/api/bench', () => ({ calculateBench: api.calculate }))
vi.mock('../../lib/hooks/useProjectContext', () => ({ useProjectContext: () => ({ visibleProjects: [], projectsError: false, refetchProjects: vi.fn() }) }))
vi.mock('./InstrumentAnalysis', () => ({ InstrumentAnalysis: ({ projectId, instrument }: { projectId: string; instrument: string }) => <p data-testid="instrument-preview">{instrument}:{projectId || 'no-project'}</p> }))
vi.mock('./SerialDilutionPlanner', () => ({ SerialDilutionPlanner: () => <p>Serial dilution</p> }))
const tool = (id: string) => BENCH_TOOLS.find((entry) => entry.id === id)!
const result = { kind: 'protein-properties', calculation_version: 'bench-v1', values: [{ key: 'molecular_weight_g_mol', label: 'Molecular mass', label_zh: '分子量', value: 12000, unit: 'g/mol' }, { key: 'epsilon_reduced', label: 'Reduced epsilon', label_zh: '还原态 ε', value: 10000, unit: 'M^-1 cm^-1' }], formula: 'mass = sum(residues) + water', assumptions: ['Unmodified sequence'], assumptions_zh: ['未修饰序列'], warnings: [], warnings_zh: [], references: [{ title: 'Method', url: 'https://web.expasy.org/protparam/' }], steps: [] }
beforeEach(() => { api.calculate.mockReset(); api.calculate.mockResolvedValue(result); useAppStore.setState({ language: 'en' }); window.location.hash = '#/tools?tool=protein-properties' })
afterEach(cleanup)

describe('bench input contract', () => {
  it('does not interpret blank numeric input as zero', () => {
    const config = tool('nucleic-a260')
    expect(() => calculationPayload(config, initialToolValues(config))).toThrow()
  })
  it('does not double-correct a normalized absorbance using a hidden raw-path draft', () => {
    const config = tool('nucleic-a260')
    const body = calculationPayload(config, { ...initialToolValues(config), sample_absorbance: '1', path_length_cm: '0.1' })
    expect(body).toMatchObject({ kind: 'nucleic-a260', material: 'dsDNA', sample_absorbance: 1, path_length_cm: 1, absorbance_basis: 'normalized-1cm' })
  })
  it('allows low molarity dilutions without an arbitrary unit-dependent floor', () => {
    const config = tool('dilution')
    const values = { ...initialToolValues(config), stock_concentration: '1e-6', target_concentration: '1e-8', concentration_unit: 'M', final_volume_uL: '1000' }
    expect(calculationPayload(config, values)).toMatchObject({ stock_concentration: 1e-6, target_concentration: 1e-8 })
    expect(() => calculationPayload(config, { ...values, stock_concentration: '0' })).toThrow()
    expect(calculationPayload(config, { ...values, target_concentration: '0' })).toHaveProperty('target_concentration', 0)
  })
  it('sends exactly one copy-number mass definition', () => {
    const config = tool('copy-number')
    const base = { ...initialToolValues(config), mass_ng: '1', molecular_weight_g_mol: '660000', length: '1000' }
    expect(calculationPayload(config, base)).toEqual({ kind: 'copy-number', mass_ng: 1, molecular_weight_g_mol: 660000 })
    expect(calculationPayload(config, { ...base, _mass_basis: 'length' })).toEqual({ kind: 'copy-number', mass_ng: 1, material: 'dsDNA', length: 1000 })
  })
  it('requires mass only when crossing concentration families', () => {
    const config = tool('concentration')
    const base = { ...initialToolValues(config), value: '1', from_unit: 'nM', to_unit: 'uM' }
    expect(calculationPayload(config, base)).not.toHaveProperty('molecular_weight_g_mol')
    expect(() => calculationPayload(config, { ...base, to_unit: 'mg/mL' })).toThrow()
  })
  it.each(['Infinity', '-1', 'NaN', '1e-400'])('rejects invalid concentration %s', (value) => {
    const config = tool('concentration')
    expect(() => calculationPayload(config, { ...initialToolValues(config), value, molecular_weight_g_mol: '12000' })).toThrow()
  })
})

describe('bench results and navigation', () => {
  it('runs only on submit and marks old results stale after an input change', async () => {
    const onUse = vi.fn()
    renderWithProviders(<BenchToolForm tool={tool('protein-properties')} onUse={onUse} />)
    expect(api.calculate).not.toHaveBeenCalled()
    fireEvent.change(screen.getByLabelText('Sequence'), { target: { value: 'WYCC' } })
    fireEvent.click(screen.getByRole('button', { name: 'Calculate' }))
    await screen.findByRole('region', { name: 'Calculation result' })
    expect(api.calculate.mock.calls[0][0]).toEqual({ kind: 'protein-properties', sequence: 'WYCC' })
    fireEvent.click(screen.getByRole('button', { name: 'Use reduced ε for A280 concentration' }))
    expect(onUse).toHaveBeenCalledWith('protein-a280', { molecular_weight_g_mol: '12000', epsilon_M_inv_cm_inv: '10000' })
    fireEvent.change(screen.getByLabelText('Sequence'), { target: { value: 'WW' } })
    expect(screen.getByRole('status')).toHaveTextContent('Inputs changed')
    expect(screen.getByRole('button', { name: 'Copy result & method' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Use reduced ε for A280 concentration' })).not.toBeInTheDocument()
  })
  it('shows tiny nonzero results without rounding to zero', async () => {
    api.calculate.mockResolvedValue({ ...result, values: [{ key: 'small', label: 'Small result', label_zh: '小结果', value: 1e-12, unit: 'M' }] })
    renderWithProviders(<BenchToolForm tool={tool('protein-properties')} onUse={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Sequence'), { target: { value: 'W' } })
    fireEvent.click(screen.getByRole('button', { name: 'Calculate' }))
    expect(await screen.findByText('1.00000e-12')).toBeVisible()
  })
  it('organizes 14 tools, keeps only one form visible and preserves drafts when switching', async () => {
    renderWithProviders(<ToolsPage />)
    const nav = screen.getByRole('navigation', { name: 'Lab tool categories' })
    expect(within(nav).getAllByRole('button')).toHaveLength(14)
    fireEvent.change(screen.getByLabelText('Sequence'), { target: { value: 'WYCC' } })
    fireEvent.click(within(nav).getByRole('button', { name: 'Nucleic acid A260 → concentration' }))
    expect(screen.getAllByRole('form')).toHaveLength(1)
    await waitFor(() => expect(window.location.hash).toContain('tool=nucleic-a260'))
    fireEvent.click(within(nav).getByRole('button', { name: 'Protein mass & extinction' }))
    expect(screen.getByLabelText('Sequence')).toHaveValue('WYCC')
    expect(api.calculate).not.toHaveBeenCalled()
  })
  it('transfers actual computed values without putting sequence data into the URL', async () => {
    renderWithProviders(<ToolsPage />)
    fireEvent.change(screen.getByLabelText('Sequence'), { target: { value: 'WYCC' } })
    fireEvent.click(screen.getByRole('button', { name: 'Calculate' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Use reduced ε for A280 concentration' }))
    expect(screen.getByLabelText('Molar extinction coefficient ε (M⁻¹·cm⁻¹)')).toHaveValue(10000)
    expect(screen.getByLabelText('Molar mass / molecular weight value (g/mol)')).toHaveValue(12000)
    expect(window.location.hash).not.toContain('WYCC')
  })
  it('supports projectless instrument links and an empty search result without changing selection', () => {
    window.location.hash = '#/tools?tool=bli'
    renderWithProviders(<ToolsPage />)
    expect(screen.getByTestId('instrument-preview')).toHaveTextContent('bli:no-project')
    fireEvent.change(screen.getByRole('textbox', { name: 'Search lab tools' }), { target: { value: 'does-not-exist' } })
    expect(screen.getByText('No matching tools.')).toBeVisible()
    expect(screen.getByTestId('instrument-preview')).toHaveTextContent('bli:no-project')
  })
})
