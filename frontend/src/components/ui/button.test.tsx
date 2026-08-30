import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Button, LinkButton } from './Button'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('Button composition', () => {
  it('keeps its default render target as a native button', () => {
    render(<Button>Save</Button>)

    expect(screen.getByRole('button', { name: 'Save' }).tagName).toBe('BUTTON')
  })

  it('supports anchor render targets without a native-button warning', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)

    render(<Button render={<a href="/projects" />}>Projects</Button>)

    expect(screen.getByRole('link', { name: 'Projects' })).toHaveAttribute('href', '/projects')
    expect(consoleError).not.toHaveBeenCalled()
  })
})

describe('LinkButton', () => {
  it('renders a real anchor with the requested destination', () => {
    render(<LinkButton href="/projects">Projects</LinkButton>)

    expect(screen.getByRole('link', { name: 'Projects' })).toHaveAttribute('href', '/projects')
  })
})
