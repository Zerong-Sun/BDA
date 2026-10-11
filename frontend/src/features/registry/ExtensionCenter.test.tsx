import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { assessExtension, getExtensionCatalog, type ExtensionCatalog, type ExtensionEntry } from '../../lib/api/extensions'
import { currentRole } from '../research/jsonHelpers'
import { ExtensionCenter } from './ExtensionCenter'

vi.mock('../../lib/api/extensions', () => ({ getExtensionCatalog: vi.fn(), assessExtension: vi.fn() }))
vi.mock('../research/jsonHelpers', () => ({ currentRole: vi.fn() }))

const entry = (id: string, title: string, adapter: ExtensionEntry['manifest']['adapter']): ExtensionEntry => ({
  manifest: { id, version: '1.0.0', title, title_zh: title, description: `${title} description`, description_zh: `${title} description`, adapter,
    function_ids: ['F14'], resources: 'Measured resource needs', license_boundary: 'Review exact code and weights', data_boundary: 'Current project boundaries',
    rollout_trigger: 'A named task and measured need', effort: 'Planning estimate only', sources: ['https://github.com/jwohlwend/boltz'], requirements: [] },
  assessment: { id, state: adapter === 'planned' ? 'planned' : 'needs_configuration', ready_for_trial: false, scientific_validation: 'not_assessed',
    checks: [], blockers: [adapter === 'planned' ? 'No execution adapter is shipped' : 'Select exact registered resources'], warnings: ['Declarations only; no probes'], selected_model: null },
})
const catalog: ExtensionCatalog = { version: '1.0', manifest_checksum_sha256: 'a'.repeat(64), assessed_at: '2026-10-11T00:00:00Z', observation_scope: 'registry_declarations_only', inventory_truncated: false,
  extensions: [entry('scientific-models', 'Registered scientific models', 'model_registry'), entry('robotic-assay', 'Robotic assay', 'planned')],
  models: [{ id: 'model-1', plugin_key: 'boltz', plugin_version: '2', name: 'Boltz 2', enabled: true, declaration_valid: true, runtime_proof_current: false,
    manifest_pinned: true, qualification_recorded: false, blockers: [], warnings: ['No checkpoint/use review is recorded'] }],
  compute_nodes: [{ id: 'node-1', name: 'Registered node', enabled: true }], providers: [] }

beforeEach(() => {
  useAppStore.setState({ language: 'en', appMode: 'application' })
  vi.mocked(currentRole).mockReturnValue('admin')
  vi.mocked(getExtensionCatalog).mockResolvedValue(catalog)
  vi.mocked(assessExtension).mockResolvedValue({ ...catalog.extensions[0].assessment, blockers: ['Record current runtime proof'] })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })

describe('Extension center', () => {
  it('shows actual model declarations and separates them from proof and future adapters', async () => {
    renderWithProviders(<ExtensionCenter />)
    expect(await screen.findByRole('heading', { name: 'Boltz 2 · 2' })).toBeInTheDocument()
    expect(screen.getByText(/Runtime unproven or changed/)).toBeInTheDocument()
    expect(screen.getByText('No checkpoint/use review is recorded')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Robotic assay.*Planned/ }))
    expect(await screen.findByText('No execution adapter is shipped')).toBeInTheDocument()
    expect(screen.queryByText('Recorded prerequisites meet controlled-trial preflight')).not.toBeInTheDocument()
    expect(assessExtension).not.toHaveBeenCalled()
  })

  it('sends only chosen records and bounded review references when the admin asks', async () => {
    renderWithProviders(<ExtensionCenter />)
    const choose = async (label: string, name: string) => {
      fireEvent.click(await screen.findByRole('combobox', { name: label }))
      const option = await screen.findByRole('option', { name })
      fireEvent.pointerDown(option, { button: 0 })
      fireEvent.pointerUp(option, { button: 0 })
      fireEvent.click(option)
      await waitFor(() => expect(screen.getByRole('combobox', { name: label })).toHaveTextContent(name))
    }
    await choose('Model plugin', 'Boltz 2 · 2')
    await choose('Compute node', 'Registered node')
    fireEvent.change(screen.getByRole('textbox', { name: 'License review reference' }), { target: { value: 'license-review-7' } })
    expect(assessExtension).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Check readiness' }))
    await waitFor(() => expect(assessExtension).toHaveBeenCalledWith('scientific-models', {
      model_plugin_id: 'model-1', compute_node_id: 'node-1', llm_provider_id: null,
      license_review_ref: 'license-review-7', data_review_ref: '', validation_plan_ref: '', budget_review_ref: '',
    }))
    expect(await screen.findByText('Record current runtime proof')).toBeInTheDocument()
    await choose('Model plugin', 'Choose a registered plugin')
    expect(screen.queryByText('Record current runtime proof')).not.toBeInTheDocument()
  })

  it('keeps inspection accessible but proposed-config assessments disabled for a viewer', async () => {
    vi.mocked(currentRole).mockReturnValue('viewer')
    renderWithProviders(<ExtensionCenter />)
    expect(await screen.findByRole('combobox', { name: 'Model plugin' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Check readiness' })).toBeDisabled()
    expect(screen.getByText(/administrators in application mode/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Check readiness' }))
    expect(assessExtension).not.toHaveBeenCalled()
  })

  it('filters integration choices and reports loading failures honestly', async () => {
    renderWithProviders(<ExtensionCenter />)
    await screen.findByRole('heading', { name: 'Boltz 2 · 2' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Search integrations' }), { target: { value: 'no such integration' } })
    expect(screen.getByText('No matching integrations.')).toBeInTheDocument()
    vi.mocked(getExtensionCatalog).mockRejectedValue(new Error('Registry unavailable'))
    fireEvent.click(screen.getByRole('button', { name: 'Refresh registry state' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Registry unavailable')
  })
})
