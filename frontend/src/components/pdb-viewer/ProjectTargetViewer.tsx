import type { ProjectTargetStructure } from '../../lib/schemas/target'
import { StructureViewerLazy } from './StructureViewerLazy'
import { structureSourceFromTarget } from './types'

interface ProjectTargetViewerProps {
  target: ProjectTargetStructure
  projectId?: string
  height?: number | string
  className?: string
  allowFullscreen?: boolean
  showMeta?: boolean
}

export function ProjectTargetViewer({
  target,
  projectId,
  height = 280,
  className,
  allowFullscreen = true,
  showMeta = true,
}: ProjectTargetViewerProps) {
  const source = structureSourceFromTarget(target, projectId)
  if (!source.url) return null

  return (
    <StructureViewerLazy
      source={source}
      height={height}
      className={className}
      allowFullscreen={allowFullscreen}
      showMetadata={showMeta}
    />
  )
}
