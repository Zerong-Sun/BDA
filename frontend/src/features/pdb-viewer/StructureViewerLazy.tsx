import { lazy, Suspense } from 'react'
import type { StructureViewerProps } from './StructureViewer'
import { StructureViewerFallback } from './StructureViewerFallback'

const LazyStructureViewer = lazy(() =>
  import('./StructureViewer').then((module) => ({ default: module.StructureViewer })),
)

export function StructureViewerLazy(props: StructureViewerProps) {
  return (
    <Suspense
      fallback={<StructureViewerFallback height={props.height ?? 360} />}
    >
      <LazyStructureViewer {...props} />
    </Suspense>
  )
}
