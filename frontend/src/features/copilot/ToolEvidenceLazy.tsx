import { lazy, Suspense } from 'react'
const Evidence = lazy(() => import('./ToolEvidence').then((module) => ({ default: module.ToolEvidence })))
export function ToolEvidenceLazy({ calls, projectId, content }: { calls?: unknown[]; projectId: string; content?: string | null }) {
  if (!content && !calls?.some((call) => call && typeof call === 'object' && 'result' in call)) return null
  return <Suspense fallback={null}><Evidence calls={calls} projectId={projectId} content={content} /></Suspense>
}
