import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Button } from '../../components/ui/Button'
import { Disclosure } from '../../components/ui/Disclosure'
import type { Project } from '../../lib/api/projects'
import { getResearchWorkspace, workspaceText } from '../../lib/api/researchWorkspace'
import { useI18n } from '../../lib/i18n'
import { projectBrief } from '../projects/projectBrief'
import { ReviewMarkdown } from './ReviewMarkdown'
import { workspaceCitationRecords } from './findingCitations'
import { reviewSections } from './reviewSections'

export function ProjectResearchOverview({ project }: { project: Project }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const archived = project.status === 'archived'
  const query = useQuery({ queryKey: ['research-workspace', project.id], queryFn: () => getResearchWorkspace(project.id) })
  const workspace = query.data
  const report = workspace?.review_document
  const content = report ? workspaceText(report.content, language) : ''
  const sections = reviewSections(content)
  const objective = sections.find((section) => /objective|研究目标|研究问题/i.test(section.title))
  const keyFinding = sections.find((section) => /structure|signaling|findings|结论|结构|机制|结果/i.test(section.title))
    ?? sections.find((section) => section !== objective)
  const unresolved = sections.filter((section) => /uncertainty|conflict|limitation|gate|next|争议|矛盾|局限|下一步|闸门|待验证/i.test(section.title))
  const url = (tab: string) => `/research?project=${encodeURIComponent(project.id)}&tab=${tab}`
  return <section aria-label={zh ? '项目研究总结' : 'Project research summary'} className="space-y-6 pb-6">
    <header className="space-y-2"><p className="text-xs text-text-secondary">{archived ? (zh ? '已归档项目 · 已保存的研究成果' : 'Archived project · saved research record') : (zh ? '已完成项目 · 已保存的研究成果' : 'Completed project · saved research record')}</p><h2 className="text-2xl font-semibold">{zh ? '研究总结与遗留问题' : 'Research summary and open questions'}</h2><p className="text-sm text-text-secondary">{zh ? '回顾项目目标、报告结论及来源；归档不会改变证据的审阅状态。' : 'Review the objectives, report findings and sources. Archiving does not change evidence review status.'}</p></header>
    {query.isPending ? <p role="status">{zh ? '正在读取项目研究记录…' : 'Loading the research record…'}</p> : null}
    {query.isError ? <div role="alert">{zh ? '研究记录读取失败。' : 'Could not load the research record.'}<Button type="button" variant="link" onClick={() => { void query.refetch() }}>{zh ? '重试' : 'Retry'}</Button></div> : null}
    {workspace ? <>
      <nav aria-label={zh ? '已保存的材料' : 'Saved materials'} className="flex flex-wrap gap-3 border-y border-border-soft py-3 text-sm">
        <Link className="text-primary" to={url('evidence')}>{workspace.review_sections.reduce((sum, section) => sum + (section.items?.length ?? 0), 0)} {zh ? '条研究发现' : 'research findings'} →</Link>
        <Link className="text-primary" to={url('references')}>{workspace.references.length} {zh ? '篇文献' : 'references'} →</Link>
        <Link className="text-primary" to={url('structures')}>{workspace.structures.length} {zh ? '个结构' : 'structures'} →</Link>
        <Link className="text-primary" to={url('timeline')}>{zh ? '查看决策记录' : 'Decision record'} →</Link>
      </nav>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-6">
          <section className="space-y-2"><h3 className="font-semibold">{zh ? '研究目标与问题' : 'Research objectives and questions'}</h3><ReviewMarkdown>{objective?.body || projectBrief(project, language).objective || (zh ? '原资料未记录目标。' : 'No objective is recorded in the source.')}</ReviewMarkdown></section>
          {keyFinding ? <section className="space-y-2 border-t border-border-soft pt-4"><h3 className="font-semibold">{zh ? '报告要点' : 'Report findings'}</h3><p className="text-xs text-text-secondary">{keyFinding.title} · {zh ? '报告原文' : 'from the saved report'}</p><ReviewMarkdown>{keyFinding.body}</ReviewMarkdown></section> : null}
        </div>
        <aside className="min-w-0 space-y-4 rounded-lg bg-surface-2 p-4"><h3 className="font-semibold">{zh ? '遗留问题与推进条件' : 'Open questions and advancement conditions'}</h3>{unresolved.length ? unresolved.map((section) => <section key={section.title} className="space-y-2"><h4 className="text-sm font-medium">{section.title}</h4><ReviewMarkdown>{section.body}</ReviewMarkdown></section>) : <p className="text-sm text-text-secondary">{zh ? '报告未单列遗留问题；这不代表所有问题已经解决。' : 'The report has no separate open-questions section; this does not imply all questions are resolved.'}</p>}</aside>
      </div>
      {report && content.trim() ? <Disclosure title={zh ? '完整综述与引用来源' : 'Full report and cited sources'}><p className="mb-3 text-xs text-text-secondary">{workspaceText(report.title, language)} · {zh ? '原记录状态' : 'Recorded status'}: {report.status}</p><ReviewMarkdown citations={workspaceCitationRecords(workspace.references, language)} projectId={project.id}>{content}</ReviewMarkdown></Disclosure> : <p className="text-sm text-text-secondary">{zh ? '尚未找到正式综述，可从上方入口查看已有资料。' : 'No report is recorded. Use the links above to inspect saved materials.'}</p>}
      <p className="border-t border-border-soft pt-3 text-xs text-text-secondary">{zh ? '此页直接呈现已保存报告。结构化目标树是另一套记录，未建立目标树不表示项目没有开展研究。' : 'This page presents the saved report. A structured goal tree is a separate record; its absence does not mean no research was done.'}</p>
    </> : null}
  </section>
}
