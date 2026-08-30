/**
 * Regression cover for two items the manual UI review raised: the script uploader
 * exposed the native file input directly, and the reorder handle announced itself with
 * the workflow canvas's "connect nodes" hint.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ScriptAssetManager } from './ScriptAssetManager'

vi.mock('../../lib/api/registry', () => ({
  listModelPlugins: () => Promise.resolve([]),
  listScriptAssets: () =>
    Promise.resolve([
      {
        id: 'script-1',
        name: 'submit.lsf',
        model_plugin: 'RFdiffusion',
        scheduler: 'lsf',
        warnings: [],
        archive_path: 'rfd/submit.lsf',
      },
    ]),
  uploadScriptAsset: vi.fn(),
}))

vi.mock('../../lib/hooks/useProjectContext', () => ({
  useProjectContext: () => ({ projectId: 'p1', activeProject: null }),
}))

function renderManager() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ScriptAssetManager />
    </QueryClientProvider>,
  )
}

describe('ScriptAssetManager accessibility contract', () => {
  it('keeps the native file input out of the visual layout', async () => {
    const { container } = renderManager()

    const input = container.querySelector('input[type="file"]')
    expect(input).not.toBeNull()
    // Asserting the intent, not the utility class: the browser's own unstyleable,
    // browser-localized control must be out of the visual layout, with a styled trigger
    // standing in for it.
    expect(input?.className).toMatch(/\b(hidden|sr-only)\b/)
    expect(await screen.findByRole('button', { name: /Choose script file/i })).toBeInTheDocument()
  })

  it('names the reorder handle after reordering, not after connecting nodes', async () => {
    renderManager()

    const handle = await screen.findByLabelText(/Reorder script/i)
    expect(handle).toBeInTheDocument()
    expect(screen.queryByLabelText(/connect/i)).toBeNull()
  })
})
