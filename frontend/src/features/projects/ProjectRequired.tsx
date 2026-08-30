import type { ReactNode } from 'react'
import { AppFrame } from '@/components/ui/AppFrame'
import { Skeleton } from '@/components/ui/Skeleton'
import { ProjectChooser } from './ProjectChooser'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'

export function ProjectRequired({ children }: { children: ReactNode }) {
  const { t } = useI18n()
  const { hasProject, projectsLoading, hasStaleProjectReference } = useProjectContext()

  if (projectsLoading) {
    return (
      <AppFrame panelClassName="grid gap-3 p-5" aria-label={t.projects.projectRequired.loading}>
        <Skeleton className="h-5 w-44" />
        <Skeleton className="h-8 w-full" />
      </AppFrame>
    )
  }
  if (!hasProject) {
    return (
      <ProjectChooser
        title={t.projects.projectRequired.title}
        description={
          hasStaleProjectReference
            ? t.projects.projectRequired.staleDescription
            : t.projects.projectRequired.defaultDescription
        }
      />
    )
  }
  return children
}
