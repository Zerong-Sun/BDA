import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DrawerShell } from './DrawerShell'

afterEach(cleanup)

describe('DrawerShell accessibility', () => {
  it('uses a concise dialog title without wrapping visual header actions in the heading', () => {
    render(
      <DrawerShell
        open
        onClose={vi.fn()}
        title="Application settings"
        header={
          <div>
            <h2>Configure application settings</h2>
            <button type="button">Close settings</button>
          </div>
        }
      >
        Settings body
      </DrawerShell>,
    )

    expect(screen.getByRole('dialog', { name: 'Application settings' })).toBeInTheDocument()
    const conciseHeading = screen.getByRole('heading', { name: 'Application settings' })
    expect(within(conciseHeading).queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close settings' })).not.toBe(conciseHeading)
  })
})
