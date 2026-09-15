import { Link, useNavigate } from 'react-router'
import type { Project } from '../../lib/api/projects'
import { useI18n } from '../../lib/i18n'
import { Button } from '../../components/ui/Button'
import { projectBrief } from './projectBrief'
import { useAppStore } from '../../lib/store/appStore'

export function ProjectBriefPanel({ project, compact = false }: { project: Project; compact?: boolean }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const brief = projectBrief(project, language)
  const navigate = useNavigate()
  const discuss = (question: string) => {
    const state = useAppStore.getState()
    state.setActiveProjectId(project.id)
    state.setCopilotSelectedEntityIds([])
    state.setCopilotSessionBot(project.id, null)
    state.setCopilotDraft(zh
      ? `${question}\n\n请依据本项目已有资料回答，引用来源，并区分已知证据、推断和尚待回答的问题。`
      : `${question}\n\nUse the existing project materials, cite sources, and distinguish evidence, inference and open questions.`)
    navigate(`/bots?project=${encodeURIComponent(project.id)}&view=chat`)
  }
  return <section className={`project-brief ${compact ? 'project-brief--compact' : ''}`} aria-label={zh ? '项目简报' : 'Project brief'}>
    <div>
      <p className="science-eyebrow">{zh ? '研究目标' : 'RESEARCH OBJECTIVE'}</p>
      <p className="project-objective">{brief.objective || (zh ? '尚未定义研究目标。先说明希望解决的问题。' : 'Define the question this project should answer.')}</p>
      {brief.source === 'public-package' ? <p className="mt-3 text-xs text-text-muted">{zh ? '来自公开演示包的项目简报 · 不是已完成的目标记录' : 'Brief from the public demo package · not completed goal records'}</p> : null}
    </div>
    {!compact ? <div className="brief-details">
      <div><h3>{zh ? '需要回答的问题' : 'Questions to answer'}</h3>
        {brief.questions.length ? <ol>{brief.questions.map((question) => <li key={question}><span>{question}</span><Button type="button" size="sm" variant="link" className="brief-question-action" aria-label={`${zh ? '与 Bot 讨论' : 'Discuss with a Bot'}: ${question}`} onClick={() => discuss(question)}>{zh ? '与 Bot 讨论 →' : 'Discuss with a Bot →'}</Button></li>)}</ol>
          : <p className="text-sm text-text-secondary">{zh ? '在下方添加可检验的问题，记录证据与判断。' : 'Add testable questions below and connect the evidence behind each decision.'}</p>}
      </div>
      {brief.deliverables.length ? <div><h3>{zh ? '预期交付' : 'Expected deliverables'}</h3><ul>{brief.deliverables.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}
    </div> : null}
    {compact ? <Button type="button" variant="outline" render={<Link to={`/research?project=${encodeURIComponent(project.id)}&tab=goals`} />}>{zh ? '查看项目简报' : 'Read project brief'}</Button> : null}
  </section>
}
