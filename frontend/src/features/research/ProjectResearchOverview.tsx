import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Button } from '../../components/ui/Button'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../components/ui/accordion'
import type { Project } from '../../lib/api/projects'
import { isProjectIndex, listAllResearchBriefs, latestProgressBrief } from '../../lib/api/researchBriefs'
import { getResearchWorkspace, workspaceText } from '../../lib/api/researchWorkspace'
import { useI18n } from '../../lib/i18n'
import { projectBrief } from '../projects/projectBrief'
import { ReviewMarkdown } from './ReviewMarkdown'
import { workspaceCitationRecords } from './findingCitations'
import { findingReviewCounts, isNewerSavedRecord, reviewOverview, splitObjectiveQuestions } from './reviewOverview'
import { localizeToken } from './researchUi'

export function ProjectResearchOverview({ project }: { project: Project }) {
  const { language, t } = useI18n()
  const zh = language === 'zh'
  const archived = project.status === 'archived'
  const retrospective = archived || project.status === 'completed'
  const [reportOpen, setReportOpen] = useState<string[]>([])
  const reportRef = useRef<HTMLDivElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)
  const [progressOpen, setProgressOpen] = useState<string[]>([])
  const briefsQuery = useQuery({ queryKey: ['research-briefs-complete', project.id], queryFn: () => listAllResearchBriefs(project.id), enabled: !retrospective })
  const progress = retrospective ? undefined : latestProgressBrief(briefsQuery.data ?? [])
  const progressSections = reviewOverview(progress?.content ?? '')
  const query = useQuery({ queryKey: ['research-workspace', project.id], queryFn: () => getResearchWorkspace(project.id) })
  const workspace = query.data
  const savedDocument = workspace?.review_document
  const indexDocument = savedDocument && Object.values(savedDocument.title).some(title => typeof title === 'string' && isProjectIndex(title)) ? savedDocument : undefined
  const report = indexDocument ? undefined : savedDocument
  const content = report ? workspaceText(report.content, language) : ''
  const { objectives, findings, unresolved } = reviewOverview(content)
  const preferProgress = Boolean(progress && (!report || isNewerSavedRecord(progress.updated_at, report.updated_at)))
  const progressFindings = preferProgress ? progressSections.findings : []
  const progressConditions = preferProgress ? progressSections.unresolved : []
  const displayedFindings = progressFindings.length ? progressFindings : findings
  const unsectionedProgress = preferProgress && !displayedFindings.length ? progress?.content?.trim() : undefined
  const displayedUnresolved = progressConditions.length ? progressConditions : unresolved
  const dateLabel = (value: string) => Number.isFinite(Date.parse(value)) ? new Intl.DateTimeFormat(language === 'zh' ? 'zh-CN' : 'en-GB', { dateStyle: 'medium', timeZone: 'Asia/Shanghai' }).format(new Date(value)) : (zh ? '日期未记录' : 'Date not recorded')
  const brief = projectBrief(project, language)
  const objectiveParts = objectives.map(section => splitObjectiveQuestions(section.body, section.title))
  const objective = { objective: objectiveParts.map(part => part.objective).filter(Boolean).join('\n\n'), questions: objectiveParts.map(part => part.questions).filter(Boolean).join('\n\n') }
  const citations = workspaceCitationRecords(workspace?.references ?? [], language)
  const prose = (value: string) => <ReviewMarkdown compactCitations citations={/\[(?:cite:)?\d/.test(value) ? citations : []} projectId={project.id}>{value}</ReviewMarkdown>
  const reviewCounts = findingReviewCounts(workspace?.review_sections.flatMap(section => section.items ?? []) ?? [])
  const statusLabel = (status: string) => status === 'progress_note' ? (zh ? '进展记录' : 'Progress note') : status === 'unrecorded' ? (zh ? '未记录复核状态' : 'Review status not recorded') : localizeToken(status, t.research.enums)
  const url = (tab: string) => `/research?project=${encodeURIComponent(project.id)}&tab=${tab}`
  const openReport = () => {
    setReportOpen(['report'])
    reportRef.current?.scrollIntoView?.({ block: 'start', behavior: 'smooth' })
  }
  const openProgress = () => { setProgressOpen(['progress']); progressRef.current?.scrollIntoView?.({ block: 'start', behavior: 'smooth' }) }
  const briefSource = brief.source === 'public-package' ? (zh ? '来源：已导入资料包任务书' : 'Source: imported package brief') : (zh ? '来源：项目任务书' : 'Source: project brief')
  const source = (title: string) => <p className="text-xs text-text-muted">{zh ? '原报告章节' : 'Saved report section'} · {title}</p>

  return <section aria-label={zh ? '项目研究总结' : 'Project research summary'} className="space-y-5 pb-6">
    <header className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-xs text-text-secondary">{archived ? (zh ? '已归档项目 · 已保存的研究成果' : 'Archived project · saved research record') : project.status === 'completed' ? (zh ? '已完成项目 · 已保存的研究成果' : 'Completed project · saved research record') : project.status === 'active' ? (zh ? '进行中 · 已保存研究记录' : 'In progress · saved research record') : `${localizeToken(project.status, t.research.enums)} · ${zh ? '已保存研究记录' : 'saved research record'}`}</p>
      {progress ? <Button type="button" size="sm" onClick={openProgress}>{zh ? '阅读最新进展' : 'Read latest progress'}</Button> : null}
      {report && content.trim() ? <Button type="button" size="sm" onClick={openReport}>{zh ? '阅读完整报告' : 'Read full report'}</Button> : null}
    </header>
    {query.isPending ? <p role="status">{zh ? '正在读取项目研究记录…' : 'Loading the research record…'}</p> : null}
    {query.isError ? <div role="alert">{zh ? '研究记录读取失败。' : 'Could not load the research record.'}<Button type="button" variant="link" onClick={() => { void query.refetch() }}>{zh ? '重试' : 'Retry'}</Button></div> : null}
    {!retrospective && briefsQuery.isPending ? <p role="status">{zh ? '正在读取全部进展记录…' : 'Reading all progress records…'}</p> : null}
    {!retrospective && briefsQuery.isError ? <div role="alert">{zh ? '进展记录读取失败；下方保留已保存综述，不能确认最新进展。' : 'Progress records could not be loaded; the saved report remains below, but latest progress is not confirmed.'}<Button type="button" variant="link" onClick={() => { void briefsQuery.refetch() }}>{zh ? '重试进展记录' : 'Retry progress records'}</Button></div> : null}
    {workspace ? <>
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(16rem,1fr)]">
        <section aria-label={zh ? '项目结果' : 'Project results'} className="min-w-0 space-y-3 rounded-lg border border-border-soft p-4">
          <h2 className="text-base font-semibold">{zh ? '项目结果' : 'Project results'}</h2>
          {(progressFindings.length || unsectionedProgress) && progress ? <p className="text-xs text-text-secondary">{zh ? '来源：最新已保存进展' : 'Source: latest saved progress'} · {progress.title} · {dateLabel(progress.updated_at)} · {statusLabel(progress.status)}</p> : null}
          {displayedFindings.length ? displayedFindings.map(section => <div key={section.title} className="space-y-2">{progressFindings.length ? <p className="text-xs text-text-muted">{section.title}</p> : source(section.title)}{progressFindings.length ? <ReviewMarkdown>{section.body}</ReviewMarkdown> : prose(section.body)}</div>) : unsectionedProgress ? <div className="max-h-80 overflow-y-auto"><p className="text-xs text-text-muted">{zh ? '最新进展原文（未分章节）' : 'Latest progress record (without section headings)'}</p><ReviewMarkdown compactCitations>{unsectionedProgress}</ReviewMarkdown></div> : <p className="text-sm text-text-secondary">{indexDocument ? (zh ? '当前仅有归档索引，尚未找到独立结果报告；可查看下方研究发现与来源索引。' : 'Only an archive index is recorded; no standalone results report is available. Inspect the findings and source index below.') : report ? (zh ? '已保存报告未单列结果章节，请阅读原报告及研究发现。' : 'No separate results section is recorded. Read the saved report and research findings.') : (zh ? '尚未找到结果报告，可查看下方已有研究发现。' : 'No results report is recorded. Inspect the saved findings below.')}</p>}
        </section>
        <aside aria-label={zh ? '报告与复核' : 'Report and review'} className="min-w-0 space-y-3 rounded-lg bg-surface-2 p-4">
          <h2 className="font-semibold">{zh ? '报告与复核' : 'Report and review'}</h2>
          {report ? <><p className="text-sm font-medium">{workspaceText(report.title, language)}</p><p className="text-xs text-text-secondary">{zh ? '报告记录状态' : 'Recorded report status'}: {statusLabel(report.status)} · v{report.version} · {dateLabel(report.updated_at)}</p></> : <p className="text-sm text-text-secondary">{zh ? '尚未找到正式综述，可从下方入口查看已有资料。' : 'No report is recorded. Use the links below to inspect saved materials.'}</p>}
          {progress ? <div className="border-t border-border-soft pt-3"><p className="text-xs text-text-muted">{zh ? '最新已保存进展' : 'Latest saved progress'}</p><p className="mt-1 text-sm font-medium">{progress.title}</p><p className="mt-1 text-xs text-text-secondary">{statusLabel(progress.status)} · {dateLabel(progress.updated_at)}</p></div> : null}
          <p className="text-sm">{zh ? '最终复核：本研究记录未单独记录' : 'Final review: not separately recorded in this research record'}</p>
          <div className="border-t border-border-soft pt-3"><h3 className="mb-2 text-xs font-semibold">{zh ? '研究发现的复核记录' : 'Finding review records'}</h3>{reviewCounts.length ? <ul className="space-y-1 text-sm">{reviewCounts.map(([status, count]) => <li key={status} className="flex justify-between gap-3"><span>{statusLabel(status)}</span><span className="font-medium tabular-nums">{count}</span></li>)}</ul> : <p className="text-xs text-text-secondary">{zh ? '未找到研究发现复核记录。' : 'No finding review records are available.'}</p>}</div>
          <p className="text-xs text-text-secondary">{zh ? '报告状态与逐条证据复核分别记录；归档不代表所有科学问题已经解决。' : 'Report status and individual evidence reviews are separate records; archiving does not resolve every scientific question.'}</p>
          <Link className="block text-sm text-primary" to={`/bots/auditor?project=${encodeURIComponent(project.id)}&view=records`}>{zh ? '查看 Bot 复核记录' : 'View Bot review records'} →</Link>
          <Link className="inline-block text-sm text-primary" to={url('evidence')}>{zh ? '查看证据与复核记录' : 'Inspect evidence and review records'} →</Link>
        </aside>
      </div>
      <nav aria-label={zh ? '已保存的材料' : 'Saved materials'} className="flex flex-wrap gap-x-5 gap-y-2 border-y border-border-soft py-3 text-sm">
        <Link className="text-primary" to={url('evidence')}>{workspace.review_sections.reduce((sum, section) => sum + (section.items?.length ?? 0), 0)} {zh ? '条研究发现' : 'research findings'} →</Link>
        <Link className="text-primary" to={url('references')}>{workspace.references.length} {zh ? '篇文献' : 'references'} →</Link>
        <Link className="text-primary" to={url('structures')}>{workspace.structures.length} {zh ? '个结构' : 'structures'} →</Link>
        <Link className="text-primary" to={url('timeline')}>{zh ? '查看决策记录' : 'Decision record'} →</Link>
      </nav>
      <section aria-label={zh ? '研究目标与问题' : 'Research objectives and questions'} className="space-y-3">
        <h2 className="font-semibold">{zh ? '研究目标与问题' : 'Research objectives and questions'}</h2>
        {objective.objective ? <>{source(objectives.filter((_, index) => objectiveParts[index].objective).map(section => section.title).join(' · '))}{prose(objective.objective)}</> : <><p className="text-xs text-text-muted">{briefSource}</p><ReviewMarkdown>{brief.objective || (zh ? '原资料未记录目标。' : 'No objective is recorded in the source.')}</ReviewMarkdown></>}
        {objective.questions ? <div className="space-y-2 rounded-lg bg-surface-2 p-4"><h3 className="text-sm font-semibold">{zh ? '原报告中的研究问题' : 'Research questions from the saved report'}</h3>{source(objectives.filter((_, index) => objectiveParts[index].questions).map(section => section.title).join(' · '))}{prose(objective.questions)}</div> : brief.questions.length ? <div className="space-y-2"><p className="text-xs text-text-muted">{briefSource}</p><ReviewMarkdown>{brief.questions.map((question, index) => `${index + 1}. ${question}`).join('\n')}</ReviewMarkdown></div> : null}
      </section>
      <section aria-label={zh ? '遗留问题与推进条件' : 'Open questions and advancement conditions'} className="space-y-3 border-t border-border-soft pt-4">
        <h2 className="font-semibold">{zh ? '遗留问题与推进条件' : 'Open questions and advancement conditions'}</h2>
        {displayedUnresolved.length ? <div className="grid items-start gap-5 lg:grid-cols-2">{displayedUnresolved.map(section => <section key={section.title} className="min-w-0 space-y-2"><h3 className="text-sm font-medium">{section.title}</h3>{progressConditions.length ? <><p className="text-xs text-text-muted">{zh ? '来源：最新已保存进展' : 'Source: latest saved progress'}</p><ReviewMarkdown>{section.body}</ReviewMarkdown></> : prose(section.body)}</section>)}</div> : <p className="text-sm text-text-secondary">{zh ? '报告未单列遗留问题；这不代表所有问题已经解决。' : 'The report has no separate open-questions section; this does not imply all questions are resolved.'}</p>}
      </section>
      {progress ? <div ref={progressRef} className="scroll-mt-24 border-t border-border-soft"><Accordion value={progressOpen} onValueChange={setProgressOpen}><AccordionItem value="progress"><AccordionTrigger>{zh ? '完整进展与来源' : 'Full progress and sources'}</AccordionTrigger><AccordionContent><p className="mb-3 text-xs text-text-secondary">{progress.title} · {statusLabel(progress.status)} · {dateLabel(progress.updated_at)}</p><ReviewMarkdown>{progress.content ?? ''}</ReviewMarkdown></AccordionContent></AccordionItem></Accordion></div> : null}
      {report && content.trim() ? <div ref={reportRef} className="scroll-mt-24 border-t border-border-soft"><Accordion value={reportOpen} onValueChange={setReportOpen}><AccordionItem value="report"><AccordionTrigger>{zh ? '完整综述与引用来源' : 'Full report and cited sources'}</AccordionTrigger><AccordionContent><p className="mb-3 text-xs text-text-secondary">{workspaceText(report.title, language)} · {zh ? '原记录状态' : 'Recorded status'}: {report.status} · {dateLabel(report.updated_at)}</p><ReviewMarkdown compactCitations citations={citations} projectId={project.id}>{content}</ReviewMarkdown></AccordionContent></AccordionItem></Accordion></div> : null}
      {indexDocument ? <Accordion key={project.id} className="border-t border-border-soft"><AccordionItem value="source-index"><AccordionTrigger>{zh ? '归档来源索引' : 'Archive source index'}</AccordionTrigger><AccordionContent><ReviewMarkdown>{workspaceText(indexDocument.content, language)}</ReviewMarkdown></AccordionContent></AccordionItem></Accordion> : null}
      <p className="border-t border-border-soft pt-3 text-xs text-text-muted">{zh ? '目标、问题和结果来自已有报告与项目任务书。结构化目标树未建立时，仍保留这些原始研究记录；不自动推断问题已回答或复核已完成。' : 'Objectives, questions and results come from saved reports and project briefs. An absent structured goal tree does not erase those records or imply questions are answered or reviews complete.'}</p>
    </> : null}
  </section>
}
