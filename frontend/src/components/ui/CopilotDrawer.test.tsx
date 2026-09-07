import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { Button } from './Button'
import { CopilotDrawer } from './CopilotDrawer'

vi.mock('../../features/copilot/CopilotWorkspace', () => ({
  CopilotWorkspace: () => <div data-slot="scroll-area">Task workspace</div>,
}))
vi.mock('../../features/copilot/CopilotSettings', () => ({
  CopilotSettings: () => <div>Model configuration panel</div>,
}))

afterEach(cleanup)

function DrawerHarness() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button type="button" onClick={() => setOpen(true)}>
        Launch Copilot
      </Button>
      <CopilotDrawer open={open} onClose={() => setOpen(false)} />
    </>
  )
}

describe('CopilotDrawer', () => {
  it('uses the Sheet slot, closes with Escape, and returns focus to its trigger', async () => {
    renderWithProviders(<DrawerHarness />)
    const trigger = screen.getByRole('button', { name: 'Launch Copilot' })
    trigger.focus()
    fireEvent.click(trigger)

    const dialog = await screen.findByRole('dialog', { name: 'Copilot' })
    expect(dialog).toHaveAttribute('data-slot', 'sheet-content')
    expect(dialog.querySelectorAll('[data-slot="scroll-area"]')).toHaveLength(1)

    fireEvent.keyDown(document, { key: 'Escape' })

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(trigger).toHaveFocus())
  })

  it('opens a unified task workspace and keeps model settings secondary', async () => {
    renderWithProviders(<DrawerHarness />)
    fireEvent.click(screen.getByRole('button', { name: 'Launch Copilot' }))
    await screen.findByRole('dialog', { name: 'Copilot' })
    expect(screen.getByText('Task workspace')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Agent runs' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    expect(await screen.findByText('Model configuration panel')).toBeInTheDocument()
    expect(screen.getByText('Task workspace')).toBeInTheDocument()
  })
})
