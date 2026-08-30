import { useState, type RefObject } from 'react'
import { ArrowsOut, ClipboardText, CornersIn, Crosshair } from '@phosphor-icons/react'
import { Frame, FramePanel } from '@/components/reui/frame'
import { Button } from '@/components/ui/Button'
import { Label } from '@/components/ui/label'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { getViewOptions, type ColorPreset, type RepresentationPreset, type ViewPreset } from './ColorPresets'
import { ColorSchemeSelector } from './ColorSchemeSelector'
import { ChainSelector } from './ChainSelector'
import { RepresentationSelector } from './RepresentationSelector'
import { useI18n } from '../../lib/i18n'

interface StructureControlsProps {
  representation: RepresentationPreset
  color: ColorPreset
  chains: string[]
  selectedChain: string | null
  onRepresentationChange: (value: RepresentationPreset) => void
  onColorChange: (value: ColorPreset) => void
  onViewChange: (value: ViewPreset) => void
  onChainChange: (chainId: string | null) => void
  onResetCamera: () => void
  onCopyFasta?: () => void
  canCopyFasta?: boolean
  allowFullscreen?: boolean
  isFullscreen?: boolean
  onToggleFullscreen?: () => void
  fullscreenButtonRef?: RefObject<HTMLButtonElement | null>
}

export function StructureControls({
  representation,
  color,
  chains,
  selectedChain,
  onRepresentationChange,
  onColorChange,
  onViewChange,
  onChainChange,
  onResetCamera,
  onCopyFasta,
  canCopyFasta = false,
  allowFullscreen = true,
  isFullscreen = false,
  onToggleFullscreen,
  fullscreenButtonRef,
}: StructureControlsProps) {
  const { t } = useI18n()
  const viewOptions = getViewOptions(t.viewer)
  const [selectedView, setSelectedView] = useState<ViewPreset | null>(null)

  return (
    <Frame className="mb-2" spacing="sm">
      <FramePanel className="flex flex-wrap items-end gap-3">
        <RepresentationSelector value={representation} onChange={onRepresentationChange} />
        <ColorSchemeSelector value={color} onChange={onColorChange} />
        <ChainSelector chains={chains} value={selectedChain} onChange={onChainChange} />
        <div className="grid gap-1">
          <Label>{t.viewer.cameraView}</Label>
          <ToggleGroup
            aria-label={t.viewer.cameraView}
            variant="outline"
            size="sm"
            spacing={0}
            multiple={false}
            value={selectedView ? [selectedView] : []}
            onValueChange={(values) => {
              const view = values.at(-1)
              if (!view) return
              setSelectedView(view as ViewPreset)
              onViewChange(view as ViewPreset)
            }}
          >
            {viewOptions.map((view) => (
              <ToggleGroupItem
                key={view.id}
                value={view.id}
                aria-label={view.label}
                onClick={() => {
                  if (selectedView === view.id) onViewChange(view.id)
                }}
              >
                {view.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
        <div className="ml-auto flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onResetCamera}
          >
            <Crosshair aria-hidden="true" />
            {t.viewer.resetCamera}
          </Button>
          {onCopyFasta ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!canCopyFasta}
              title={t.viewer.copyFastaHint}
              aria-label={t.viewer.copyFasta}
              onClick={onCopyFasta}
            >
              <ClipboardText aria-hidden="true" />
              {t.viewer.copyFasta}
            </Button>
          ) : null}
          {allowFullscreen && onToggleFullscreen ? (
            <Button
              ref={fullscreenButtonRef}
              type="button"
              variant="outline"
              size="sm"
              onClick={onToggleFullscreen}
            >
              {isFullscreen ? (
                <CornersIn aria-hidden="true" />
              ) : (
                <ArrowsOut aria-hidden="true" />
              )}
              {isFullscreen ? t.viewer.exitFullscreen : t.viewer.enterFullscreen}
            </Button>
          ) : null}
        </div>
      </FramePanel>
    </Frame>
  )
}
