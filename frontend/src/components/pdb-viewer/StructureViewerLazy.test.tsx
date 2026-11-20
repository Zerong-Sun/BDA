import { cleanup, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { StructureViewerLazy } from './StructureViewerLazy'

vi.mock('./StructureViewer', () => ({
  StructureViewer: ({ source }: { source?: { url?: string | null } | null }) => (
    <div data-testid="mock-structure-viewer">Loaded lazy viewer: {source?.url ?? 'empty'}</div>
  ),
}))

afterEach(cleanup)

describe('StructureViewerLazy', () => {
  it('keeps the Mol* viewer behind a Suspense import boundary', async () => {
    renderWithProviders(
      <StructureViewerLazy
        source={{ url: '/api/v2/artifacts/target.pdb', file: null }}
        height={240}
      />,
    )

    expect(screen.getByText('Initializing 3D viewer...')).toBeInTheDocument()
    expect(document.querySelector('[data-slot="frame"]')).toBeInTheDocument()
    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
    expect(await screen.findByTestId('mock-structure-viewer')).toHaveTextContent(
      'Loaded lazy viewer: /api/v2/artifacts/target.pdb',
    )
  })
})
