import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { AppFrame } from './AppFrame'
import { StatusPill } from './StatusPill'

afterEach(cleanup)

describe('shared registry compatibility contracts', () => {
  it('renders status through the ReUI badge contract', () => {
    render(<StatusPill tone="green" label="Ready" />)

    expect(screen.getByText('Ready')).toHaveAttribute('data-slot', 'badge')
  })

  it('renders semantic application frames through the ReUI Frame contract', () => {
    const { container } = render(<AppFrame heading="Details">Frame body</AppFrame>)

    expect(container.querySelector('[data-slot="frame"]')).toBeInTheDocument()
    expect(screen.getByText('Details')).toHaveAttribute('data-slot', 'frame-panel-title')
    expect(screen.getByText('Frame body')).toHaveAttribute('data-slot', 'frame-panel')
  })
})
