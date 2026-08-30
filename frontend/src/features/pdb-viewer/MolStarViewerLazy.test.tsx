import { cleanup, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { MolStarViewerLazy } from './MolStarViewerLazy'

vi.mock('./MolStarViewer', () => ({
  MolStarViewer: () => <div data-testid="mock-molstar-viewer">Mol* ready</div>,
}))

afterEach(cleanup)

describe('MolStarViewerLazy', () => {
  it('uses the shared registry Frame and Skeleton fallback', async () => {
    renderWithProviders(
      <MolStarViewerLazy sourceUrl="/api/v2/structures/a.pdb" height={240} />,
    )

    expect(screen.getByText('Initializing 3D viewer...')).toBeInTheDocument()
    expect(document.querySelector('[data-slot="frame"]')).toBeInTheDocument()
    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
    expect(await screen.findByTestId('mock-molstar-viewer')).toBeInTheDocument()
  })
})
