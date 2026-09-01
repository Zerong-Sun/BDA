import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { createRef } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useToastStore } from '../../components/ui/toastStore'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import {
  StructureViewer,
  type StructureViewerHandle,
} from './StructureViewer'

interface Deferred<T> {
  promise: Promise<T>
  resolve: (value: T | PromiseLike<T>) => void
  reject: (reason?: unknown) => void
}

function deferred<T>(): Deferred<T> {
  let resolve!: Deferred<T>['resolve']
  let reject!: Deferred<T>['reject']
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

const mocks = vi.hoisted(() => {
  const plugin = {
    initialized: Promise.resolve(),
    handleResize: vi.fn(),
    managers: {
      camera: { focusObject: vi.fn() },
      structure: {
        hierarchy: {
          current: { trajectories: [], structures: [] },
        },
      },
    },
  }
  const viewer = {
    plugin,
    dispose: vi.fn(),
    loadStructureFromData: vi.fn().mockResolvedValue(undefined),
  }
  return {
    plugin,
    viewer,
    create: vi.fn(async () => viewer),
    clearStructures: vi.fn().mockResolvedValue(undefined),
    enumerateChainsFromPlugin: vi.fn(() => []),
    hasLoadedStructure: vi.fn(() => true),
    extractChainSequences: vi.fn(() => [] as { chainId: string; sequence: string; residueCount: number }[]),
    copyTextToClipboard: vi.fn(async () => true),
    loadStructureFromAuthenticatedUrl: vi.fn().mockResolvedValue(undefined),
    applyVisualPreset: vi.fn().mockResolvedValue(undefined),
    applyChainFilter: vi.fn().mockResolvedValue(undefined),
    applyResidueHighlights: vi.fn().mockResolvedValue(undefined),
    resetCamera: vi.fn().mockResolvedValue(undefined),
    applyViewPreset: vi.fn().mockResolvedValue(undefined),
  }
})

vi.mock('./molstarViewerFactory', () => ({
  createMolstarViewer: mocks.create,
}))

vi.mock('molstar/lib/mol-plugin-ui/skin/light.scss', () => ({ default: {} }))
vi.mock('molstar/lib/mol-plugin-ui/skin/dark.scss', () => ({ default: {} }))

vi.mock('./structureLoader', () => ({
  applyChainFilter: mocks.applyChainFilter,
  applyResidueHighlights: mocks.applyResidueHighlights,
  applyVisualPreset: mocks.applyVisualPreset,
  clearStructures: mocks.clearStructures,
  enumerateChainsFromPlugin: mocks.enumerateChainsFromPlugin,
  hasLoadedStructure: mocks.hasLoadedStructure,
  loadStructureFromAuthenticatedUrl: mocks.loadStructureFromAuthenticatedUrl,
  resetCamera: mocks.resetCamera,
  structureFormatFromName: (name: string) => name.endsWith('.cif') ? 'mmcif' : 'pdb',
}))

vi.mock('./viewPresets', () => ({
  applyViewPreset: mocks.applyViewPreset,
}))

vi.mock('./structureSequence', async () => {
  const actual = await vi.importActual<typeof import('./structureSequence')>('./structureSequence')
  return {
    ...actual,
    extractChainSequences: mocks.extractChainSequences,
    copyTextToClipboard: mocks.copyTextToClipboard,
  }
})

class ResizeObserverDouble {
  static instances: ResizeObserverDouble[] = []

  observe = vi.fn()
  disconnect = vi.fn()

  constructor() {
    ResizeObserverDouble.instances.push(this)
  }
}

describe('StructureViewer lifecycle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ResizeObserverDouble.instances = []
    mocks.plugin.initialized = Promise.resolve()
    mocks.viewer.loadStructureFromData.mockResolvedValue(undefined)
    mocks.loadStructureFromAuthenticatedUrl.mockResolvedValue(undefined)
    Object.defineProperty(globalThis, 'ResizeObserver', {
      configurable: true,
      value: ResizeObserverDouble,
    })
    Object.defineProperty(window, 'requestAnimationFrame', {
      configurable: true,
      value: vi.fn((callback: FrameRequestCallback) => {
        callback(1)
        return 1
      }),
    })
    Object.defineProperty(window, 'cancelAnimationFrame', {
      configurable: true,
      value: vi.fn(),
    })
    useAppStore.setState({ language: 'en' })
    document.body.style.overflow = ''
  })

  afterEach(() => {
    cleanup()
    document.body.style.overflow = ''
  })

  it('creates Mol* once across language changes and disposes it exactly once', async () => {
    const { unmount } = renderWithProviders(
      <StructureViewer source={{ url: '/api/v2/structures/a.pdb' }} />,
    )
    await waitFor(() => expect(mocks.create).toHaveBeenCalledOnce())
    await waitFor(() =>
      expect(mocks.loadStructureFromAuthenticatedUrl).toHaveBeenCalledWith(
        mocks.viewer,
        '/api/v2/structures/a.pdb',
      ),
    )

    act(() => useAppStore.setState({ language: 'zh' }))
    await screen.findByRole('button', { name: '放大查看' })
    expect(mocks.create).toHaveBeenCalledOnce()

    unmount()
    expect(mocks.viewer.dispose).toHaveBeenCalledOnce()
  })

  it('clears the active Mol* structure when its source is removed', async () => {
    const { rerender } = renderWithProviders(
      <StructureViewer source={{ url: '/api/v2/structures/a.pdb' }} />,
    )
    await waitFor(() => expect(mocks.loadStructureFromAuthenticatedUrl).toHaveBeenCalledOnce())
    await waitFor(() => expect(mocks.clearStructures).toHaveBeenCalledTimes(1))

    rerender(<StructureViewer source={null} />)
    await waitFor(() => expect(mocks.clearStructures).toHaveBeenCalledTimes(2))
    expect(screen.getByText(/upload a pdb file/i)).toBeInTheDocument()
  })

  it('offers the same retry path when no-source initialization fails', async () => {
    mocks.create.mockRejectedValueOnce(new Error('empty viewer unavailable'))
    renderWithProviders(<StructureViewer source={null} />)

    expect(await screen.findByRole('alert')).toHaveTextContent('empty viewer unavailable')
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(2))
    await waitFor(() =>
      expect(screen.queryByText('empty viewer unavailable')).not.toBeInTheDocument(),
    )
    expect(screen.getByText(/upload a pdb file/i)).toBeInTheDocument()
  })

  it('retries a no-source clear failure', async () => {
    mocks.clearStructures.mockRejectedValueOnce(new Error('clear failed'))
    renderWithProviders(<StructureViewer source={null} />)

    expect(await screen.findByRole('alert')).toHaveTextContent('clear failed')
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(mocks.clearStructures).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByText('clear failed')).not.toBeInTheDocument())
    expect(screen.getByText(/upload a pdb file/i)).toBeInTheDocument()
  })

  it('reports a payload that parsed into no structure instead of showing an empty viewport', async () => {
    mocks.hasLoadedStructure.mockReturnValueOnce(false)
    const onError = vi.fn()
    renderWithProviders(
      <StructureViewer source={{ url: '/api/v2/structures/a.pdb' }} onError={onError} />,
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'File received but contains no atoms',
    )
    expect(onError).toHaveBeenCalledWith(expect.stringContaining('no atoms'))

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() =>
      expect(mocks.loadStructureFromAuthenticatedUrl).toHaveBeenCalledTimes(2),
    )
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })

  it('copies every chain of the loaded structure as FASTA', async () => {
    mocks.extractChainSequences.mockReturnValue([
      { chainId: 'A', sequence: 'ACDEF', residueCount: 5 },
      { chainId: 'B', sequence: 'GHIK', residueCount: 4 },
    ])
    renderWithProviders(
      <StructureViewer source={{ url: '/api/v2/structures/a.pdb', proteinName: 'Reference protein' }} />,
    )

    const copy = await screen.findByRole('button', { name: 'Copy FASTA' })
    await waitFor(() => expect(copy).toBeEnabled())
    fireEvent.click(copy)

    await waitFor(() =>
      expect(mocks.copyTextToClipboard).toHaveBeenCalledWith(
        '>Reference_protein|Chain_A|5aa\nACDEF\n>Reference_protein|Chain_B|4aa\nGHIK',
      ),
    )
    await waitFor(() =>
      expect(useToastStore.getState().message).toBe('Copied 2 chain(s), 9 residues as FASTA'),
    )
  })

  it('keeps the FASTA control disabled until a structure is loaded', async () => {
    const pendingLoad = deferred<void>()
    mocks.loadStructureFromAuthenticatedUrl.mockReturnValueOnce(pendingLoad.promise)
    renderWithProviders(<StructureViewer source={{ url: '/api/v2/structures/a.pdb' }} />)

    const copy = await screen.findByRole('button', { name: 'Copy FASTA' })
    expect(copy).toBeDisabled()

    await act(async () => pendingLoad.resolve())
    await waitFor(() => expect(copy).toBeEnabled())
  })

  it('ignores a stale failed load after a newer source has succeeded', async () => {
    const oldLoad = deferred<void>()
    const newLoad = deferred<void>()
    mocks.loadStructureFromAuthenticatedUrl.mockImplementation((_viewer, url: string) =>
      url.endsWith('old.pdb') ? oldLoad.promise : newLoad.promise,
    )
    const onError = vi.fn()
    const { rerender } = renderWithProviders(
      <StructureViewer source={{ url: '/api/v2/structures/old.pdb' }} onError={onError} />,
    )
    await waitFor(() =>
      expect(mocks.loadStructureFromAuthenticatedUrl).toHaveBeenCalledWith(
        mocks.viewer,
        '/api/v2/structures/old.pdb',
      ),
    )

    rerender(
      <StructureViewer source={{ url: '/api/v2/structures/new.pdb' }} onError={onError} />,
    )
    await act(async () => oldLoad.reject(new Error('stale failure')))
    await waitFor(() =>
      expect(mocks.loadStructureFromAuthenticatedUrl).toHaveBeenCalledWith(
        mocks.viewer,
        '/api/v2/structures/new.pdb',
      ),
    )
    await act(async () => newLoad.resolve())
    await waitFor(() => expect(screen.queryByText('Loading structure...')).not.toBeInTheDocument())

    expect(onError).not.toHaveBeenCalled()
    expect(screen.queryByText('stale failure')).not.toBeInTheDocument()
  })

  it('serializes successful source loads so the current source mutates Mol* last', async () => {
    const oldLoad = deferred<void>()
    const newLoad = deferred<void>()
    const loadOrder: string[] = []
    mocks.loadStructureFromAuthenticatedUrl.mockImplementation(async (_viewer, url: string) => {
      loadOrder.push(`start:${url}`)
      await (url.endsWith('old.pdb') ? oldLoad.promise : newLoad.promise)
      loadOrder.push(`finish:${url}`)
    })
    const { rerender } = renderWithProviders(
      <StructureViewer source={{ url: '/api/v2/structures/old.pdb' }} />,
    )
    await waitFor(() => expect(loadOrder).toEqual(['start:/api/v2/structures/old.pdb']))

    rerender(<StructureViewer source={{ url: '/api/v2/structures/new.pdb' }} />)
    expect(loadOrder).toEqual(['start:/api/v2/structures/old.pdb'])
    await act(async () => oldLoad.resolve())
    await waitFor(() =>
      expect(loadOrder).toEqual([
        'start:/api/v2/structures/old.pdb',
        'finish:/api/v2/structures/old.pdb',
        'start:/api/v2/structures/new.pdb',
      ]),
    )
    await act(async () => newLoad.resolve())
    await waitFor(() =>
      expect(loadOrder.at(-1)).toBe('finish:/api/v2/structures/new.pdb'),
    )
  })

  it('shows an authenticated structure loading state until the request settles', async () => {
    const authenticatedLoad = deferred<void>()
    mocks.loadStructureFromAuthenticatedUrl.mockReturnValueOnce(authenticatedLoad.promise)
    renderWithProviders(
      <StructureViewer source={{ url: '/api/v2/artifacts/authenticated.pdb' }} />,
    )

    expect(await screen.findByText('Loading structure...')).toBeInTheDocument()
    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
    await act(async () => authenticatedLoad.resolve())
    await waitFor(() => expect(screen.queryByText('Loading structure...')).not.toBeInTheDocument())
  })

  it('retries a recoverable Mol* initialization failure', async () => {
    mocks.create.mockRejectedValueOnce(new Error('viewer unavailable'))
    renderWithProviders(
      <StructureViewer source={{ url: '/api/v2/structures/a.pdb' }} />,
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('viewer unavailable')
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByText('viewer unavailable')).not.toBeInTheDocument())
  })

  it('applies representation, color, chain, and camera effects from registry controls', async () => {
    renderWithProviders(
      <StructureViewer
        source={{ url: '/api/v2/structures/a.pdb', chains: ['A', 'B'] }}
      />,
    )
    await waitFor(() => expect(screen.queryByText('Loading structure...')).not.toBeInTheDocument())

    fireEvent.click(screen.getByRole('combobox', { name: 'Style' }))
    const surfaceOption = await screen.findByRole('option', { name: 'Surface' })
    fireEvent.pointerDown(surfaceOption, { button: 0 })
    fireEvent.pointerUp(surfaceOption, { button: 0 })
    fireEvent.click(surfaceOption)
    await waitFor(() =>
      expect(mocks.applyVisualPreset).toHaveBeenCalledWith(
        mocks.plugin,
        'surface',
        'chain-id',
        null,
      ),
    )

    fireEvent.click(screen.getByRole('combobox', { name: 'Color' }))
    const hydrophobicityOption = await screen.findByRole('option', {
      name: 'Hydrophobicity',
    })
    fireEvent.pointerDown(hydrophobicityOption, { button: 0 })
    fireEvent.pointerUp(hydrophobicityOption, { button: 0 })
    fireEvent.click(hydrophobicityOption)
    await waitFor(() =>
      expect(mocks.applyVisualPreset).toHaveBeenCalledWith(
        mocks.plugin,
        'surface',
        'hydrophobicity',
        null,
      ),
    )

    fireEvent.click(screen.getByRole('combobox', { name: 'Chain' }))
    const chainOption = await screen.findByRole('option', { name: 'B' })
    fireEvent.pointerDown(chainOption, { button: 0 })
    fireEvent.pointerUp(chainOption, { button: 0 })
    fireEvent.click(chainOption)
    await waitFor(() =>
      expect(mocks.applyChainFilter).toHaveBeenCalledWith(
        mocks.plugin,
        'surface',
        'hydrophobicity',
        'B',
      ),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Top' }))
    expect(mocks.applyViewPreset).toHaveBeenCalledWith(mocks.plugin, 'top')
  })

  it('carries the Mol* canvas into the body-level fullscreen surface and back on Escape', async () => {
    const { container } = renderWithProviders(
      <StructureViewer source={{ url: '/api/v2/structures/a.pdb' }} />,
    )
    const fullscreen = await screen.findByRole('button', { name: 'Expand viewer' })
    const canvasHost = container.querySelector('[data-molstar-canvas]')
    expect(canvasHost).toBeInstanceOf(HTMLDivElement)

    fireEvent.click(fullscreen)
    const dialog = screen.getByRole('dialog', { name: 'Protein structure viewer' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    // Portalled out of the hosting page so a clipped or transformed ancestor
    // cannot swallow the overlay.
    expect(dialog.parentElement).toBe(document.body)
    expect(container.contains(dialog)).toBe(false)
    // The imperative Mol* container is moved, not recreated: a fresh one would
    // lose the WebGL context and render an empty viewport.
    expect(document.querySelectorAll('[data-molstar-canvas]')).toHaveLength(1)
    expect(dialog.querySelector('[data-molstar-host]')?.firstElementChild).toBe(canvasHost)
    expect(document.body.style.overflow).toBe('hidden')
    expect(screen.getByRole('button', { name: 'Exit fullscreen' })).toHaveFocus()

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(document.querySelectorAll('[data-molstar-canvas]')).toHaveLength(1)
    expect(
      container.querySelector('.molstar-viewer-host > [data-molstar-host]')?.firstElementChild,
    ).toBe(canvasHost)
    expect(document.body.style.overflow).toBe('')
    expect(screen.getByRole('button', { name: 'Expand viewer' })).toHaveFocus()
  })

  it('keeps a persistent fullscreen exit when the current source disappears', async () => {
    const { rerender } = renderWithProviders(
      <StructureViewer source={{ url: '/api/v2/structures/a.pdb' }} />,
    )
    fireEvent.click(await screen.findByRole('button', { name: 'Expand viewer' }))
    expect(screen.getByRole('dialog', { name: 'Protein structure viewer' })).toBeInTheDocument()

    rerender(<StructureViewer source={null} />)

    expect(screen.getByRole('dialog', { name: 'Protein structure viewer' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Exit fullscreen' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText(/upload a pdb file/i)).toBeInTheDocument()
  })

  it('preserves resize and imperative control effects and cancels queued animation frames', async () => {
    let queuedFrame: FrameRequestCallback | null = null
    vi.mocked(window.requestAnimationFrame).mockImplementation((callback) => {
      queuedFrame = callback
      return 42
    })
    const ref = createRef<StructureViewerHandle>()
    const { unmount } = renderWithProviders(
      <StructureViewer
        ref={ref}
        source={{
          url: '/api/v2/structures/a.pdb',
          highlightedResidues: [{ chainId: 'A', seq: 59 }],
        }}
      />,
    )
    await waitFor(() => expect(mocks.create).toHaveBeenCalledOnce())
    await waitFor(() =>
      expect(mocks.applyVisualPreset).toHaveBeenCalledWith(
        mocks.plugin,
        'cartoon',
        'chain-id',
        null,
      ),
    )
    const observer = ResizeObserverDouble.instances.at(-1)
    expect(observer).toBeDefined()
    expect(observer?.observe).toHaveBeenCalledWith(
      document.querySelector('[data-molstar-host]'),
    )
    expect(mocks.plugin.handleResize).toHaveBeenCalled()

    act(() => {
      ref.current?.resetCamera()
      ref.current?.setChainVisibility('A')
      ref.current?.highlightResidues([{ chainId: 'B', seq: 12 }])
    })
    await waitFor(() => expect(mocks.resetCamera).toHaveBeenCalledWith(mocks.plugin))
    await waitFor(() =>
      expect(mocks.applyResidueHighlights).toHaveBeenCalledWith(
        mocks.plugin,
        [{ chainId: 'B', seq: 12 }],
      ),
    )
    await waitFor(() =>
      expect(mocks.applyChainFilter).toHaveBeenCalledWith(
        mocks.plugin,
        'cartoon',
        'chain-id',
        'A',
      ),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Expand viewer' }))
    unmount()
    expect(observer?.disconnect).toHaveBeenCalledOnce()
    expect(window.cancelAnimationFrame).toHaveBeenCalledWith(42)
    expect(queuedFrame).not.toBeNull()
  })

  it('disposes a viewer exactly once when initialization finishes after unmount', async () => {
    const lateViewer = deferred<typeof mocks.viewer>()
    mocks.create.mockImplementationOnce(() => lateViewer.promise)
    const { unmount } = renderWithProviders(<StructureViewer source={null} />)

    await waitFor(() => expect(mocks.create).toHaveBeenCalledOnce())
    unmount()
    await act(async () => lateViewer.resolve(mocks.viewer))
    expect(mocks.viewer.dispose).toHaveBeenCalledOnce()
  })
})
