import { Link } from 'react-router'
import { ArrowUpRightIcon } from '@phosphor-icons/react'
import { useI18n } from '../../lib/i18n'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { Button } from '../../components/ui/Button'
import { PageHead } from '../../components/ui/PageHead'

/** Keep the project list in view; detailed team roles belong in Research team. */
export function ScienceWelcome() {
  const { language } = useI18n()
  const { projectId } = useProjectContext()
  const zh = language === 'zh'
  return <>
    <PageHead eyebrow="Projects" title={zh ? '项目' : 'Projects'} actions={projectId ?
      <Button type="button" render={<Link to={`/bots${projectId ? `?project=${encodeURIComponent(projectId)}` : ''}`} />}>
        {zh ? '进入研究团队' : 'Open research team'}<ArrowUpRightIcon />
      </Button>
    : undefined} />
    {!projectId ? <p className="mb-5 text-sm text-text-secondary">{zh ? '选择或创建项目，开始研究。' : 'Choose or create a project to begin.'}</p> : null}
  </>
}
