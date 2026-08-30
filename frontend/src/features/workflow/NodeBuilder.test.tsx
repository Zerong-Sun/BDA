import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { NodeBuilder } from './NodeBuilder'

const api = vi.hoisted(() => ({
  listMethodPlugins: vi.fn(),
  listModelPlugins: vi.fn(),
}))

vi.mock('../../lib/api/registry', () => ({
  createMethodPlugin: vi.fn(),
  listMethodPlugins: api.listMethodPlugins,
  listModelPlugins: api.listModelPlugins,
}))

function modelPlugin(id: string, name: string, version: string) {
  return {
    id,
    name,
    plugin_key: `plugin_${name.toLowerCase()}`,
    plugin_version: version,
    enabled: true,
    validation_status: 'validated',
    parameter_schema: { fields: [], metadata: {} },
  }
}

/** The registry-backed cards replace the built-in fallback list once the query settles. */
function findPluginCard(name: string) {
  return screen.findByRole('button', { name: new RegExp(`^${name}`) })
}

afterEach(cleanup)

beforeEach(() => {
  useAppStore.setState({ language: 'en' })
  api.listMethodPlugins.mockResolvedValue([])
  api.listModelPlugins.mockResolvedValue([
    modelPlugin('plugin_a', 'RFdiffusion', '1.2.0'),
    modelPlugin('plugin_b', 'ProteinMPNN', '2.0.0'),
  ])
})

describe('node builder card display', () => {
  it('describes the sheet with its subtitle instead of repeating the model column label', async () => {
    renderWithProviders(<NodeBuilder open onClose={vi.fn()} onAdd={vi.fn()} />)

    await findPluginCard('RFdiffusion')
    expect(
      screen.getByText('Select a model plugin and configure its parameters'),
    ).toHaveAttribute('data-slot', 'sheet-description')
    // "Model plugins" labels the column only — it is no longer the sheet description.
    expect(screen.getAllByText('Model plugins')).toHaveLength(1)
  })

  it('marks the previewed plugin as the pressed card even before the user picks one', async () => {
    renderWithProviders(<NodeBuilder open onClose={vi.fn()} onAdd={vi.fn()} />)

    const first = await findPluginCard('RFdiffusion')
    const second = await findPluginCard('ProteinMPNN')
    expect(first).toHaveAttribute('aria-pressed', 'true')
    expect(second).toHaveAttribute('aria-pressed', 'false')

    fireEvent.click(second)
    expect(second).toHaveAttribute('aria-pressed', 'true')
    expect(first).toHaveAttribute('aria-pressed', 'false')
  })

  it('shows the plugin version on each card and keeps the custom-method form collapsed', async () => {
    renderWithProviders(<NodeBuilder open onClose={vi.fn()} onAdd={vi.fn()} />)

    const card = await findPluginCard('RFdiffusion')
    expect(within(card).getByText('v1.2.0')).toBeInTheDocument()

    const disclosure = screen.getByRole('button', { name: /Custom method/ })
    expect(disclosure).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByLabelText('New method name')).not.toBeInTheDocument()

    fireEvent.click(disclosure)
    expect(disclosure).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByLabelText('New method name')).toBeInTheDocument()
  })

  it('does not offer disabled registry plugins as addable cards', async () => {
    api.listModelPlugins.mockResolvedValue([
      modelPlugin('plugin_a', 'RFdiffusion', '1.2.0'),
      { ...modelPlugin('plugin_disabled', 'Chai-1', '0.6.1'), enabled: false },
    ])

    renderWithProviders(<NodeBuilder open onClose={vi.fn()} onAdd={vi.fn()} />)

    await findPluginCard('RFdiffusion')
    expect(screen.queryByRole('button', { name: /^Chai-1/ })).not.toBeInTheDocument()
  })

  it('does not fall back to static addable models when every registry plugin is disabled', async () => {
    api.listModelPlugins.mockResolvedValue([
      { ...modelPlugin('plugin_disabled', 'Chai-1', '0.6.1'), enabled: false },
    ])

    renderWithProviders(<NodeBuilder open onClose={vi.fn()} onAdd={vi.fn()} />)

    expect(await screen.findByText('No model plugins are registered yet.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Chai-1/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add card to workflow' })).toBeDisabled()
  })

  it('re-seeds method defaults when registry methods replace the built-in fallback list', async () => {
    api.listMethodPlugins.mockResolvedValue([
      { id: 'method_a', name: 'Affinity score', plugin_key: 'affinity', specification: {} },
      { id: 'method_b', name: 'Diversity cap', plugin_key: 'diversity', specification: {} },
    ])

    renderWithProviders(<NodeBuilder open onClose={vi.fn()} onAdd={vi.fn()} />)

    // Without re-seeding the panel opens with nothing selected and an unusable submit.
    expect(await screen.findByText('2 selected')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add card to workflow' })).toBeEnabled()

    fireEvent.click(screen.getByRole('checkbox', { name: /Affinity score/ }))
    expect(screen.getByText('1 selected')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('checkbox', { name: /Diversity cap/ }))
    expect(screen.getByText('0 selected')).toBeInTheDocument()
    expect(screen.getByText('Select at least one method')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add card to workflow' })).toBeDisabled()
  })
})
