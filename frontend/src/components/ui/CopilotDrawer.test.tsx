import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/mocks/handlers'
import { useAppStore } from '../../lib/store/appStore'
import { Button } from './Button'
import { CopilotDrawer } from './CopilotDrawer'

vi.mock('../../features/copilot/CopilotChat', () => ({ CopilotChat: () => <div>Conversation</div> }))
vi.mock('../../features/copilot/CopilotActions', () => ({ CopilotActions: () => <div>Actions</div> }))
vi.mock('../../features/copilot/CopilotAgentRuns', () => ({ CopilotAgentRuns: () => <div>Agent run list</div> }))

vi.mock('../../features/copilot/CopilotWorkspace', () => ({
  CopilotWorkspace: () => <div data-slot="scroll-area">Task workspace</div>,
}))
vi.mock('../../features/copilot/CopilotSettings', () => ({
  CopilotSettings: () => <div>Model configuration panel</div>,
}))
vi.mock('../../features/copilot/CopilotChain', () => ({
  CopilotChain: ({ onSelectOperator }: { onSelectOperator?: (id: string) => void }) => (
    <div>
      Chain record
      <button type="button" onClick={() => onSelectOperator?.('medic')}>
        Go to Medic
      </button>
    </div>
  ),
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
    // Model settings are shown to people who manage the project.
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'admin' }))
    renderWithProviders(<DrawerHarness />)
    fireEvent.click(screen.getByRole('button', { name: 'Launch Copilot' }))
    await screen.findByRole('dialog', { name: 'Copilot' })
    expect(screen.getByText('Task workspace')).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Agent runs' })).not.toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: 'Settings' }))
    expect(await screen.findByText('Model configuration panel')).toBeInTheDocument()
    expect(screen.getByText('Task workspace')).toBeInTheDocument()
  })

  it('offers the surfaces as tabs rather than as toggle buttons', async () => {
    // They were always mutually exclusive and already announced `aria-pressed`,
    // which is a tab group wearing buttons: the roles were wrong for what it
    // does and arrow keys did not move between them.
    renderWithProviders(<DrawerHarness />)
    fireEvent.click(screen.getByRole('button', { name: 'Launch Copilot' }))
    await screen.findByRole('dialog', { name: 'Copilot' })

    const tabs = screen.getAllByRole('tab')

    expect(tabs.map((tab) => tab.textContent)).toEqual(['Tasks & deliverables', 'Conversation', 'Bot handoffs', 'External access'])
    expect(screen.getByRole('tab', { name: 'Tasks & deliverables' })).toHaveAttribute('aria-selected', 'true')
  })

  it('hands the reader from a handover to the operator it names', async () => {
    // The seam between the two surfaces, which each half's own tests cannot
    // reach: the chain names a successor, and the drawer has to both record the
    // selection where the chat reads it and move the reader there. Tested here
    // because a working list and a working chat with nothing joining them is the
    // shape this whole body of work keeps finding.
    // `useProjectContext` resolves its id against the loaded project list, and
    // the drawer writes the selection under that id. The real `CopilotChain`
    // cannot render a clickable card without one - it early-returns on no
    // project, from the same hook - so this stub restores the precondition the
    // mock above skips rather than papering over a gap.
    server.use(
      http.get('/api/v2/projects', () =>
        HttpResponse.json({
          items: [
            {
              id: 'proj_test',
              organization_id: 'org_test',
              name: 'Test project',
              project_type: 'protein_design',
              status: 'active',
              owner_id: 'user_test',
              summary: 'Drawer test project',
              primary_target_id: null,
              version: 1,
              created_at: '2026-07-01T00:00:00Z',
              updated_at: '2026-07-01T00:00:00Z',
            },
          ],
          next_cursor: null,
        }),
      ),
    )
    useAppStore.setState({ activeProjectId: 'proj_test', copilotSessions: {} })
    renderWithProviders(<DrawerHarness />)
    fireEvent.click(screen.getByRole('button', { name: 'Launch Copilot' }))
    await screen.findByRole('dialog', { name: 'Copilot' })
    fireEvent.click(screen.getByRole('tab', { name: 'Bot handoffs' }))

    fireEvent.click(await screen.findByRole('button', { name: 'Go to Medic' }))

    await waitFor(() => {
      expect(useAppStore.getState().copilotSessions.proj_test?.bot).toBe('medic')
    })
    expect(await screen.findByRole('tab', { name: 'Conversation', selected: true })).toBeInTheDocument()
  })

  it('opens the chain record, which nothing else in the app shows', async () => {
    // The handover table is what makes the roster auditable, and until this tab
    // the only way to read it was to ask the Copilot about its own inbox.
    renderWithProviders(<DrawerHarness />)
    fireEvent.click(screen.getByRole('button', { name: 'Launch Copilot' }))
    await screen.findByRole('dialog', { name: 'Copilot' })

    fireEvent.click(screen.getByRole('tab', { name: 'Bot handoffs' }))

    expect(await screen.findByText('Chain record')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Conversation' })).toHaveAttribute('aria-selected', 'false')
  })
})
