import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'
import { createPortal } from 'react-dom'
import { Button } from '@/components/ui/Button'
import { useToastStore } from '../../components/ui/toastStore'
import {
  type ColorPreset,
  type RepresentationPreset,
  type ViewPreset,
} from './ColorPresets'
import { StructureControls } from './StructureControls'
import { StructureEmptyState } from './StructureEmptyState'
import { StructureErrorState } from './StructureErrorState'
import { StructureLoadingState } from './StructureLoadingState'
import { StructureMetadataPanel } from './StructureMetadataPanel'
import {
  applyChainFilter,
  applyResidueHighlights,
  applyVisualPreset,
  clearStructures,
  enumerateChainsFromPlugin,
  hasLoadedStructure,
  loadStructureFromAuthenticatedUrl,
  resetCamera,
  structureFormatFromName,
} from './structureLoader'
import { applyViewPreset } from './viewPresets'
import { hasStructureData, type HighlightedResidue, type StructureSource } from './types'
import {
  createMolstarViewer,
  type MolstarViewer,
} from './molstarViewerFactory'
import {
  copyTextToClipboard,
  extractChainSequences,
  formatFasta,
} from './structureSequence'
import { useI18n } from '../../lib/i18n'

export interface StructureViewerHandle {
  resetCamera: () => void
  setChainVisibility: (chainId: string | null) => void
  highlightResidues: (residues: HighlightedResidue[]) => void
}

export interface StructureViewerProps {
  source?: StructureSource | null
  height?: number | string
  className?: string
  defaultRepresentation?: RepresentationPreset
  defaultColor?: ColorPreset
  showMetadata?: boolean
  onReady?: () => void
  onError?: (message: string) => void
  allowFullscreen?: boolean
}

function structureSourceKey(source?: StructureSource | null): string {
  if (!source) return 'empty'
  if (source.file) return `file:${source.file.name}:${source.file.size}:${source.file.lastModified}`
  if (source.url) return `url:${source.url}`
  return 'empty'
}

function isCurrentLoad(
  generation: number,
  generationRef: React.RefObject<number>,
  viewer: MolstarViewer,
  viewerRef: React.RefObject<MolstarViewer | null>,
) {
  return generation === generationRef.current && viewerRef.current === viewer
}

export const StructureViewer = forwardRef<StructureViewerHandle, StructureViewerProps>(
  function StructureViewer(
    {
      source,
      height = 360,
      className,
      defaultRepresentation = 'cartoon',
      defaultColor = 'chain-id',
      showMetadata = true,
      onReady,
      onError,
      allowFullscreen = true,
    },
    ref,
  ) {
    const { t, format } = useI18n()
    const v = t.viewer
    const showToast = useToastStore((state) => state.show)
    const sourceKey = structureSourceKey(source)
    const hasSource = hasStructureData(source)
    const hostRef = useRef<HTMLDivElement>(null)
    const fullscreenButtonRef = useRef<HTMLButtonElement>(null)
    const viewerRef = useRef<MolstarViewer | null>(null)
    const viewerContainerRef = useRef<HTMLDivElement | null>(null)
    const disposedViewerRef = useRef<MolstarViewer | null>(null)
    const mountedRef = useRef(true)
    const loadGenerationRef = useRef(0)
    const loadQueueRef = useRef<Promise<void>>(Promise.resolve())
    const animationFramesRef = useRef(new Set<number>())
    const [viewerReadyVersion, setViewerReadyVersion] = useState(0)
    const [viewerInitToken, setViewerInitToken] = useState(0)
    const [viewerInitFailed, setViewerInitFailed] = useState(false)
    const [representation, setRepresentation] = useState<RepresentationPreset>(defaultRepresentation)
    const [color, setColor] = useState<ColorPreset>(defaultColor)
    const [loading, setLoading] = useState(true)
    const [structureLoading, setStructureLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [structureLoaded, setStructureLoaded] = useState(false)
    const [isFullscreen, setIsFullscreen] = useState(false)
    const [chains, setChains] = useState<string[]>(source?.chains ?? [])
    const [selectedChain, setSelectedChain] = useState<string | null>(null)
    const [reloadToken, setReloadToken] = useState(0)

    const onReadyRef = useRef(onReady)
    const onErrorRef = useRef(onError)
    const translationsRef = useRef(v)
    const representationRef = useRef(representation)
    const colorRef = useRef(color)
    const selectedChainRef = useRef(selectedChain)
    const structureLoadedRef = useRef(structureLoaded)
    const sourceRef = useRef(source)
    sourceRef.current = source

    useEffect(() => {
      onReadyRef.current = onReady
      onErrorRef.current = onError
      translationsRef.current = v
    }, [onReady, onError, v])

    useEffect(() => {
      representationRef.current = representation
    }, [representation])

    useEffect(() => {
      colorRef.current = color
    }, [color])

    useEffect(() => {
      selectedChainRef.current = selectedChain
    }, [selectedChain])

    const scheduleAnimationFrame = (callback: FrameRequestCallback) => {
      let id = 0
      id = window.requestAnimationFrame((time) => {
        animationFramesRef.current.delete(id)
        callback(time)
      })
      animationFramesRef.current.add(id)
      return id
    }

    useImperativeHandle(ref, () => ({
      resetCamera: () => {
        const viewer = viewerRef.current
        if (!viewer) return
        void resetCamera(viewer.plugin)
      },
      setChainVisibility: (chainId: string | null) => {
        setSelectedChain(chainId)
        selectedChainRef.current = chainId
        const viewer = viewerRef.current
        if (!viewer || !structureLoadedRef.current) return
        void applyChainFilter(
          viewer.plugin,
          representationRef.current,
          colorRef.current,
          chainId,
        )
      },
      highlightResidues: (residues: HighlightedResidue[]) => {
        const viewer = viewerRef.current
        if (!viewer) return
        void applyResidueHighlights(viewer.plugin, residues)
      },
    }), [])

    useEffect(() => {
      let cancelled = false
      mountedRef.current = true
      const animationFrames = animationFramesRef.current
      let activeViewer: MolstarViewer | null = null
      const host = hostRef.current
      if (!host) return
      const viewerContainer = document.createElement('div')
      viewerContainer.className = 'absolute inset-0'
      viewerContainer.dataset.molstarCanvas = 'true'
      host.replaceChildren(viewerContainer)
      viewerContainerRef.current = viewerContainer

      async function initialize() {
        try {
          structureLoadedRef.current = false
          setStructureLoaded(false)
          setLoading(true)
          setError(null)
          setViewerInitFailed(false)
          const viewer = await createMolstarViewer(viewerContainer)
          activeViewer = viewer
          if (cancelled) {
            if (disposedViewerRef.current !== viewer) {
              disposedViewerRef.current = viewer
              viewer.dispose()
            }
            return
          }
          viewerRef.current = viewer
          setViewerReadyVersion((version) => version + 1)
          onReadyRef.current?.()
        } catch (caught) {
          if (cancelled) return
          setViewerInitFailed(true)
          const message =
            caught instanceof Error ? caught.message : translationsRef.current.loadFailed
          setError(message)
          onErrorRef.current?.(message)
        } finally {
          if (!cancelled) setLoading(false)
        }
      }

      void initialize()

      return () => {
        cancelled = true
        mountedRef.current = false
        structureLoadedRef.current = false
        loadGenerationRef.current += 1
        for (const frame of animationFrames) {
          window.cancelAnimationFrame(frame)
        }
        animationFrames.clear()
        if (activeViewer && disposedViewerRef.current !== activeViewer) {
          disposedViewerRef.current = activeViewer
          activeViewer.dispose()
        }
        if (viewerRef.current === activeViewer) viewerRef.current = null
        if (viewerContainerRef.current === viewerContainer) viewerContainerRef.current = null
        viewerContainer.remove()
      }
    }, [viewerInitToken])

    /**
     * Fullscreen re-parents the viewer into a body-level portal, which replaces
     * the host element. The Mol* container is created imperatively, so move it
     * across by hand instead of letting React drop it — a WebGL canvas keeps its
     * context when it is re-attached within the same document.
     */
    useLayoutEffect(() => {
      const host = hostRef.current
      const container = viewerContainerRef.current
      if (!host || !container) return
      if (container.parentElement !== host) host.replaceChildren(container)
      viewerRef.current?.plugin.handleResize()
    }, [isFullscreen, viewerReadyVersion])

    useEffect(() => {
      const viewer = viewerRef.current
      if (!viewer || viewerReadyVersion === 0) return
      const currentSource = sourceRef.current
      const generation = loadGenerationRef.current + 1
      loadGenerationRef.current = generation

      async function loadCurrentSource(activeViewer: MolstarViewer) {
        if (!isCurrentLoad(generation, loadGenerationRef, activeViewer, viewerRef)) return
        if (!hasStructureData(currentSource)) {
          setError(null)
          structureLoadedRef.current = false
          setStructureLoaded(false)
          setStructureLoading(false)
          setSelectedChain(null)
          selectedChainRef.current = null
          setChains([])
          try {
            await clearStructures(activeViewer.plugin)
          } catch (caught) {
            if (!isCurrentLoad(generation, loadGenerationRef, activeViewer, viewerRef)) return
            const message =
              caught instanceof Error ? caught.message : translationsRef.current.loadFailed
            setError(message)
            onErrorRef.current?.(message)
          }
          return
        }

        try {
          setStructureLoading(true)
          structureLoadedRef.current = false
          setStructureLoaded(false)
          setError(null)
          setSelectedChain(null)
          selectedChainRef.current = null
          setChains(currentSource?.chains ?? [])

          await clearStructures(activeViewer.plugin)
          if (!isCurrentLoad(generation, loadGenerationRef, activeViewer, viewerRef)) return

          if (currentSource?.file) {
            const text = await currentSource.file.text()
            if (!isCurrentLoad(generation, loadGenerationRef, activeViewer, viewerRef)) return
            await activeViewer.loadStructureFromData(
              text,
              structureFormatFromName(currentSource.file.name),
              { dataLabel: currentSource.file.name },
            )
          } else if (currentSource?.url) {
            await loadStructureFromAuthenticatedUrl(activeViewer, currentSource.url)
          }
          if (!isCurrentLoad(generation, loadGenerationRef, activeViewer, viewerRef)) return

          // Mol* resolves the load even when the payload parsed into nothing —
          // an HTML error page or a truncated upload leaves an empty viewport
          // with no clue why, so treat "no structure" as a load failure.
          if (!hasLoadedStructure(activeViewer.plugin)) {
            throw new Error(translationsRef.current.fetchNoAtoms)
          }

          const pluginChains = enumerateChainsFromPlugin(activeViewer.plugin)
          setChains(pluginChains.length ? pluginChains : currentSource?.chains ?? [])
          await applyVisualPreset(
            activeViewer.plugin,
            representationRef.current,
            colorRef.current,
            selectedChainRef.current,
          )
          if (!isCurrentLoad(generation, loadGenerationRef, activeViewer, viewerRef)) return

          if (currentSource?.highlightedResidues?.length) {
            await applyResidueHighlights(activeViewer.plugin, currentSource.highlightedResidues)
          }
          if (!isCurrentLoad(generation, loadGenerationRef, activeViewer, viewerRef)) return

          structureLoadedRef.current = true
          setStructureLoaded(true)
          activeViewer.plugin.managers.camera.focusObject({ durationMs: 250 })
        } catch (caught) {
          if (!isCurrentLoad(generation, loadGenerationRef, activeViewer, viewerRef)) return
          const message =
            caught instanceof Error ? caught.message : translationsRef.current.loadFailed
          setError(message)
          onErrorRef.current?.(message)
          structureLoadedRef.current = false
          setStructureLoaded(false)
        } finally {
          if (isCurrentLoad(generation, loadGenerationRef, activeViewer, viewerRef)) {
            setStructureLoading(false)
          }
        }
      }

      const queuedLoad = loadQueueRef.current
        .catch(() => undefined)
        .then(() => loadCurrentSource(viewer))
      loadQueueRef.current = queuedLoad
      void queuedLoad
      return () => {
        if (loadGenerationRef.current === generation) {
          loadGenerationRef.current += 1
        }
      }
    }, [reloadToken, sourceKey, viewerReadyVersion])

    useEffect(() => {
      const host = hostRef.current
      const viewer = viewerRef.current
      if (!host || !viewer || loading) return

      const resize = () => viewer.plugin.handleResize()
      const observer = new ResizeObserver(resize)
      observer.observe(host)
      resize()

      return () => observer.disconnect()
    }, [loading, viewerReadyVersion])

    useEffect(() => {
      const viewer = viewerRef.current
      if (!viewer || loading || !structureLoaded) return

      setError(null)
      applyVisualPreset(viewer.plugin, representation, color, selectedChainRef.current)
        .then(() => {
          if (viewerRef.current === viewer) {
            viewer.plugin.managers.camera.focusObject({ durationMs: 200 })
          }
        })
        .catch((caught) => {
          if (viewerRef.current !== viewer) return
          const message =
            caught instanceof Error
              ? caught.message
              : translationsRef.current.visualizationUpdateFailed
          setError(message)
        })
    }, [representation, color, structureLoaded, loading])

    useEffect(() => {
      const viewer = viewerRef.current
      if (!viewer || loading || !structureLoaded) return
      if (!source?.highlightedResidues?.length) return

      void applyResidueHighlights(viewer.plugin, source.highlightedResidues)
    }, [source?.highlightedResidues, structureLoaded, loading])

    useEffect(() => {
      if (!isFullscreen) return
      const previousOverflow = document.body.style.overflow
      const animationFrames = animationFramesRef.current
      const fullscreenButton = fullscreenButtonRef
      document.body.style.overflow = 'hidden'
      const onKeyDown = (event: KeyboardEvent) => {
        if (event.key === 'Escape') setIsFullscreen(false)
      }
      window.addEventListener('keydown', onKeyDown)
      // Entering and leaving fullscreen swaps the toggle for a freshly mounted
      // one, so focus whichever button the ref points at when the frame runs.
      const frame = scheduleAnimationFrame(() => {
        viewerRef.current?.plugin.handleResize()
        fullscreenButton.current?.focus()
      })

      return () => {
        document.body.style.overflow = previousOverflow
        window.removeEventListener('keydown', onKeyDown)
        window.cancelAnimationFrame(frame)
        animationFrames.delete(frame)
        if (mountedRef.current) {
          scheduleAnimationFrame(() => fullscreenButton.current?.focus())
        }
      }
    }, [isFullscreen])

    const handleView = (view: ViewPreset) => {
      const viewer = viewerRef.current
      if (!viewer) return
      setError(null)
      applyViewPreset(viewer.plugin, view).catch((caught) => {
        const message =
          caught instanceof Error ? caught.message : translationsRef.current.cameraUpdateFailed
        setError(message)
      })
    }

    const handleResetCamera = () => {
      const viewer = viewerRef.current
      if (!viewer) return
      setError(null)
      resetCamera(viewer.plugin).catch((caught) => {
        const message =
          caught instanceof Error ? caught.message : translationsRef.current.cameraUpdateFailed
        setError(message)
      })
    }

    const handleChainChange = (chainId: string | null) => {
      setSelectedChain(chainId)
      selectedChainRef.current = chainId
      const viewer = viewerRef.current
      if (!viewer || !structureLoaded) return
      setError(null)
      applyChainFilter(viewer.plugin, representation, color, chainId).catch((caught) => {
        const message =
          caught instanceof Error
            ? caught.message
            : translationsRef.current.visualizationUpdateFailed
        setError(message)
      })
    }

    const handleRetry = () => {
      if (viewerInitFailed) {
        setViewerInitToken((value) => value + 1)
      } else {
        setReloadToken((value) => value + 1)
      }
    }

    const handleCopyFasta = async () => {
      const viewer = viewerRef.current
      if (!viewer || !structureLoaded) return
      const sequences = extractChainSequences(viewer.plugin)
      if (!sequences.length) {
        showToast(v.copyFastaEmpty, 'error')
        return
      }
      const currentSource = sourceRef.current
      const label =
        currentSource?.proteinName ?? currentSource?.pdbId ?? currentSource?.file?.name ?? null
      const copied = await copyTextToClipboard(formatFasta(sequences, label))
      showToast(
        copied
          ? format(v.copyFastaSuccess, {
              chains: sequences.length,
              residues: sequences.reduce((total, chain) => total + chain.residueCount, 0),
            })
          : v.copyFastaFailed,
        copied ? 'success' : 'error',
      )
    }

    const body = (
      <>
        {!isFullscreen && showMetadata && source ? (
          <StructureMetadataPanel source={source} />
        ) : null}
        {hasSource ? (
          <StructureControls
            representation={representation}
            color={color}
            chains={chains}
            selectedChain={selectedChain}
            onRepresentationChange={(value) => {
              setError(null)
              setRepresentation(value)
            }}
            onColorChange={(value) => {
              setError(null)
              setColor(value)
            }}
            onViewChange={handleView}
            onChainChange={handleChainChange}
            onResetCamera={handleResetCamera}
            onCopyFasta={() => void handleCopyFasta()}
            canCopyFasta={structureLoaded}
            allowFullscreen={allowFullscreen}
            isFullscreen={isFullscreen}
            onToggleFullscreen={() => setIsFullscreen((value) => !value)}
            fullscreenButtonRef={fullscreenButtonRef}
          />
        ) : null}
        {isFullscreen && (!hasSource || !allowFullscreen) ? (
          <Button
            ref={fullscreenButtonRef}
            type="button"
            variant="outline"
            size="sm"
            className="mb-2 self-end"
            onClick={() => setIsFullscreen(false)}
          >
            {v.exitFullscreen}
          </Button>
        ) : null}
        <div className={isFullscreen ? 'min-h-0 flex-1' : undefined}>
          <div
            className="molstar-viewer-host relative overflow-hidden border border-border"
            style={{ height: isFullscreen ? '100%' : height }}
          >
            <div ref={hostRef} data-molstar-host className="absolute inset-0" />
            {loading || structureLoading ? (
              <StructureLoadingState
                message={structureLoading ? v.loading : undefined}
              />
            ) : null}
            {error && hasSource ? (
              <StructureErrorState
                error={error}
                onRetry={handleRetry}
              />
            ) : null}
            {error && !hasSource ? (
              <StructureErrorState
                error={error}
                inline={false}
                className="absolute inset-3"
                onRetry={handleRetry}
              />
            ) : null}
            {!loading && !structureLoading && !hasSource && !error ? (
              <StructureEmptyState />
            ) : null}
          </div>
        </div>
      </>
    )

    // The overlay is portalled to <body> so a transformed, clipped or
    // stacking-context ancestor on the hosting page cannot trap it — those turn
    // `position: fixed` into "expands to nothing" and read as a dead button.
    if (isFullscreen) {
      return createPortal(
        <div
          className="fixed inset-0 z-[9999] flex min-h-0 flex-col bg-background p-4"
          role="dialog"
          aria-modal="true"
          aria-label={v.fullscreenTitle}
        >
          {body}
        </div>,
        document.body,
      )
    }

    return <div className={className}>{body}</div>
  },
)
