import {
  type ColorPreset,
  type RepresentationPreset,
  type ViewPreset,
} from './ColorPresets'
import { StructureControls } from './StructureControls'

interface ViewerControlsProps {
  representation: RepresentationPreset
  color: ColorPreset
  onRepresentationChange: (value: RepresentationPreset) => void
  onColorChange: (value: ColorPreset) => void
  onViewChange: (value: ViewPreset) => void
  isFullscreen?: boolean
  onExitFullscreen?: () => void
}

/** @deprecated Use StructureControls instead. */
export function ViewerControls({
  representation,
  color,
  onRepresentationChange,
  onColorChange,
  onViewChange,
  isFullscreen = false,
  onExitFullscreen,
}: ViewerControlsProps) {
  return (
    <StructureControls
      representation={representation}
      color={color}
      chains={[]}
      selectedChain={null}
      onRepresentationChange={onRepresentationChange}
      onColorChange={onColorChange}
      onViewChange={onViewChange}
      onChainChange={() => {}}
      onResetCamera={() => onViewChange('focus')}
      isFullscreen={isFullscreen}
      onToggleFullscreen={onExitFullscreen}
    />
  )
}
