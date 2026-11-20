import type { StructureViewerProps } from './StructureViewer'
import { hasStructureData, type StructureSource } from './types'
import { StructureViewer } from './StructureViewer'

/** @deprecated Use StructureViewerProps with `source` instead. */
export interface MolStarViewerProps extends Omit<StructureViewerProps, 'source'> {
  sourceUrl?: string | null
  file?: File | null
}

function toStructureSource(props: MolStarViewerProps): StructureSource | null {
  if (!props.sourceUrl && !props.file) return null
  return {
    url: props.sourceUrl ?? null,
    file: props.file ?? null,
  }
}

/** Backward-compatible wrapper around StructureViewer. */
export function MolStarViewer(props: MolStarViewerProps) {
  const source = toStructureSource(props)
  if (!hasStructureData(source)) {
    return <StructureViewer {...props} source={null} />
  }
  return <StructureViewer {...props} source={source} />
}
