import { cleanup, fireEvent, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { StructureControls } from './StructureControls'

function renderControls() {
  const callbacks = {
    onRepresentationChange: vi.fn(),
    onColorChange: vi.fn(),
    onViewChange: vi.fn(),
    onChainChange: vi.fn(),
    onResetCamera: vi.fn(),
    onToggleFullscreen: vi.fn(),
  }
  function ControlledStructureControls() {
    const [selectedChain, setSelectedChain] = useState<string | null>(null)
    return (
      <StructureControls
        representation="cartoon"
        color="chain-id"
        chains={['A', 'B']}
        selectedChain={selectedChain}
        {...callbacks}
        onChainChange={(chainId) => {
          callbacks.onChainChange(chainId)
          setSelectedChain(chainId)
        }}
      />
    )
  }
  renderWithProviders(<ControlledStructureControls />)
  return callbacks
}

afterEach(cleanup)

describe('StructureControls registry contract', () => {
  it('uses labeled registry Select controls and a non-empty all-chain sentinel', async () => {
    const callbacks = renderControls()
    const selectors = screen.getAllByRole('combobox')

    expect(selectors).toHaveLength(3)
    expect(selectors.every((selector) => selector.dataset.slot === 'select-trigger')).toBe(true)

    const chainSelector = screen.getByRole('combobox', { name: 'Chain' })
    fireEvent.click(chainSelector)
    const allChains = await screen.findByRole('option', { name: 'All chains' })
    expect(allChains).not.toHaveAttribute('data-value', '')
    const chainB = screen.getByRole('option', { name: 'B' })
    fireEvent.pointerDown(chainB, { button: 0 })
    fireEvent.pointerUp(chainB, { button: 0 })
    fireEvent.click(chainB)
    expect(callbacks.onChainChange).toHaveBeenCalledWith('B')

    fireEvent.click(chainSelector)
    const allChainsAgain = await screen.findByRole('option', { name: 'All chains' })
    fireEvent.pointerDown(allChainsAgain, { button: 0 })
    fireEvent.pointerUp(allChainsAgain, { button: 0 })
    fireEvent.click(allChainsAgain)
    expect(callbacks.onChainChange).toHaveBeenLastCalledWith(null)
  })

  it('uses one accessible ToggleGroup and registry action buttons', async () => {
    const callbacks = renderControls()
    const viewGroup = screen.getByRole('group', { name: 'Camera view' })
    expect(viewGroup).toHaveAttribute('data-slot', 'toggle-group')

    const top = screen.getByRole('button', { name: 'Top' })
    const front = screen.getByRole('button', { name: 'Front' })
    fireEvent.click(top)
    expect(callbacks.onViewChange).toHaveBeenCalledWith('top')
    expect(top).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(top)
    expect(callbacks.onViewChange).toHaveBeenNthCalledWith(2, 'top')
    expect(top).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(front)
    expect(front).toHaveAttribute('aria-pressed', 'true')
    expect(top).toHaveAttribute('aria-pressed', 'false')

    const reset = screen.getByRole('button', { name: 'Reset' })
    const fullscreen = screen.getByRole('button', { name: 'Expand viewer' })
    expect(reset).toHaveAttribute('data-slot', 'button')
    expect(fullscreen).toHaveAttribute('data-slot', 'button')
    fireEvent.click(reset)
    fireEvent.click(fullscreen)
    expect(callbacks.onResetCamera).toHaveBeenCalledOnce()
    expect(callbacks.onToggleFullscreen).toHaveBeenCalledOnce()
  })
})
