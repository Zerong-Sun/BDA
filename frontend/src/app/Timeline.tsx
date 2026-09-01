import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useI18n } from '../lib/i18n'
import { PageHead } from '../components/ui/PageHead'
import { ProjectTimeline } from '../features/timeline/ProjectTimeline'

export default function TimelinePage() {
  const { t } = useI18n()
  const { projectId, activeProject } = useProjectContext()

  return (
    <div className="space-y-4">
      <PageHead eyebrow={t.timeline.subtitle} title={t.timeline.title} />
      {projectId ? (
        <ProjectTimeline projectId={projectId} hasPrompt={Boolean(activeProject?.prompt)} />
      ) : null}
    </div>
  )
}
