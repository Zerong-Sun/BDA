import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { Button } from './Button'
import { CopilotDrawer } from './CopilotDrawer'

vi.mock('../../features/copilot/CopilotChat', () => ({
  CopilotChat: () => <div data-slot="scroll-area">Conversation</div>,
}))
vi.mock('../../features/copilot/CopilotActions', () => ({
  CopilotActions: () => <div>Actions</div>,
}))
vi.mock('../../features/copilot/CopilotSettings', () => ({
  CopilotSettings: () => <div>Settings</div>,
}))
vi.mock('../../features/copilot/CopilotAgentRuns', () => ({
  CopilotAgentRuns: () => <div>Agent run list</div>,
}))
vi.mock('../../features/copilot/CopilotChain', () => ({
  CopilotChain: () => <div>Chain record</div>,
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

  it('swaps chat for agent runs rather than stacking them', async () => {
    // A transcript and a conversation each want the whole drawer; showing both
    // at once leaves neither readable.
    renderWithProviders(<DrawerHarness />)
    fireEvent.click(screen.getByRole('button', { name: 'Launch Copilot' }))
    await screen.findByRole('dialog', { name: 'Copilot' })
    expect(screen.getByText('Conversation')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'Agent runs' }))

    expect(await screen.findByText('Agent run list')).toBeInTheDocument()
    expect(screen.queryByText('Conversation')).not.toBeInTheDocument()
    expect(screen.queryByText('Actions')).not.toBeInTheDocument()
  })

  it('offers the surfaces as tabs rather than as toggle buttons', async () => {
    // They were always mutually exclusive and already announced `aria-pressed`,
    // which is a tab group wearing buttons: the roles were wrong for what it
    // does and arrow keys did not move between them.
    renderWithProviders(<DrawerHarness />)
    fireEvent.click(screen.getByRole('button', { name: 'Launch Copilot' }))
    await screen.findByRole('dialog', { name: 'Copilot' })

    const tabs = screen.getAllByRole('tab')

    expect(tabs.map((tab) => tab.textContent)).toEqual(['Chat', 'Chain', 'Agent runs', 'MCP'])
    expect(screen.getByRole('tab', { name: 'Chat' })).toHaveAttribute('aria-selected', 'true')
  })

  it('opens the chain record, which nothing else in the app shows', async () => {
    // The handover table is what makes the roster auditable, and until this tab
    // the only way to read it was to ask the Copilot about its own inbox.
    renderWithProviders(<DrawerHarness />)
    fireEvent.click(screen.getByRole('button', { name: 'Launch Copilot' }))
    await screen.findByRole('dialog', { name: 'Copilot' })

    fireEvent.click(screen.getByRole('tab', { name: 'Chain' }))

    expect(await screen.findByText('Chain record')).toBeInTheDocument()
    expect(screen.queryByText('Conversation')).not.toBeInTheDocument()
  })
})
