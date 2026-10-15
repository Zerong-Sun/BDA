import { Link } from 'react-router'
import { BookOpen } from '@phosphor-icons/react'
import { useI18n } from '../../lib/i18n'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { Button } from '../../components/ui/Button'

/** Keep the project list in view; detailed team roles belong in Research team. */
export function ScienceWelcome() {
  const { language } = useI18n()
  const { projectId } = useProjectContext()
  const zh = language === 'zh'
  return <header className="workspace-welcome science-page-header">
    <div className="space-y-2">
      <p className="science-eyebrow">BIGO / AI FOR SCIENCE</p>
      <h1>{zh ? '研究工作区' : 'Research workspace'}</h1>
      <p className="max-w-3xl text-sm leading-6 text-muted-foreground">{zh ? '选择项目，衔接证据、设计、实验、结果与下一轮学习。' : 'Choose a project to connect evidence, design, experiments, results and the next learning cycle.'}</p>
    </div>
    <Button variant="outline" title={zh ? '查看使用流程' : 'How the workspace works'} render={<Link to={`/guide${projectId ? `?project=${encodeURIComponent(projectId)}` : ''}`} />}><BookOpen aria-hidden="true" className="sm:hidden" /><span className="sr-only sm:not-sr-only">{zh ? '查看使用流程' : 'How the workspace works'}</span></Button>
  </header>
}
