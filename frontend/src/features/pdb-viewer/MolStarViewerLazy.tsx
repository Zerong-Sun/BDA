import { lazy, Suspense } from 'react'
import type { MolStarViewerProps } from './MolStarViewer'
import { hasStructureData } from './types'
import { StructureViewerFallback } from './StructureViewerFallback'

const LazyStructureViewer = lazy(() =>
  import('./MolStarViewer').then((module) => ({ default: module.MolStarViewer })),
)

function toStructureSource(props: MolStarViewerProps) {
  if (!props.sourceUrl && !props.file) return null
  return {
    url: props.sourceUrl ?? null,
    file: props.file ?? null,
  }
}

export function MolStarViewerLazy(props: MolStarViewerProps) {
  const source = toStructureSource(props)
  return (
    <Suspense
      fallback={<StructureViewerFallback height={props.height ?? 360} />}
    >
      <LazyStructureViewer
        {...props}
        sourceUrl={hasStructureData(source) ? props.sourceUrl : null}
        file={hasStructureData(source) ? props.file : null}
      />
    </Suspense>
  )
}
