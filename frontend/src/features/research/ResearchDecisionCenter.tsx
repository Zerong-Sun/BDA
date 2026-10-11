import { useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { Button } from '../../components/ui/Button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { Badge } from '../../components/reui/badge'
import { listEvidenceNotes } from '../../lib/api/evidenceNotes'
import { listResearchGoals } from '../../lib/api/researchGoals'
import { listAllTimeline } from '../../lib/api/timeline'
import { useProjectAccess } from '../../lib/hooks/useProjectAccess'
import { useI18n } from '../../lib/i18n'
import { useAppStore } from '../../lib/store/appStore'
import { safeCitationUrl } from './citationMarkers'
import { decisionReadiness } from './decisionReadiness'
import { relationLabel } from './evidenceNotes'
import { ResearchDecisionEditor } from './ResearchDecisionEditor'

export function ResearchDecisionCenter({ projectId }: { projectId: string }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const [params, setParams] = useSearchParams()
  const [editing, setEditing] = useState(false)
  const demo = useAppStore((state) => state.appMode === 'demo')
  const access = useProjectAccess(projectId)
  const canWrite = !demo && access.data?.permissions.write === true
  const goals = useQuery({ queryKey: ['research-goals', projectId], queryFn: () => listResearchGoals(projectId), enabled: Boolean(projectId), staleTime: 30_000 })
  const evidence = useInfiniteQuery({ queryKey: ['evidence-notes', projectId], initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => listEvidenceNotes(projectId, pageParam), getNextPageParam: (page) => page.next_cursor ?? undefined, enabled: Boolean(projectId), retry: false })
  const timeline = useQuery({ queryKey: ['project-timeline', projectId], queryFn: () => listAllTimeline(projectId), enabled: Boolean(projectId), retry: false, staleTime: 30_000 })
  const selected = goals.data?.find((goal) => goal.id === params.get('goal')) ?? goals.data?.find((goal) => goal.status === 'open') ?? goals.data?.[0]
  const notes = evidence.data?.pages.flatMap((page) => page.items) ?? []
  const complete = evidence.isSuccess && !evidence.hasNextPage
  const readiness = selected ? decisionReadiness(selected, notes, complete) : null
  const records = timeline.data ?? []
  const linkedRecords = selected ? records.filter((entry) => selected.links?.some((link) => link.resource_type === 'timeline_entry' && link.resource_id === entry.id)) : []
  const ledger = records.filter((entry) => ['decision', 'result', 'resolution', 'method'].includes(entry.entry_type)).slice(-3).reverse()
  const url = (tab: string) => `/research?project=${encodeURIComponent(projectId)}&tab=${tab}`
  const checkLabels = {
    hypothesis: zh ? '有可验证的假设' : 'Testable hypothesis recorded',
    alternatives: zh ? '有至少两个备选方案' : 'At least two alternatives recorded',
    success: zh ? '已写明成功标准' : 'Success criteria recorded',
    falsification: zh ? '已写明反证或停止标准' : 'Falsification / stopping criteria recorded',
    next: zh ? '已写明下一次决策与触发条件' : 'Next decision and trigger recorded',
    sources: zh ? '已关联且能找到论据' : 'Linked evidence is available',
    review: zh ? '关联论据均已复核且原文匹配' : 'Linked evidence reviewed and source-matched',
  }
  return <section data-testid="research-decision-center" aria-label={zh ? '研究决策中心' : 'Research decision center'} className="research-decision-center mb-5 grid min-w-0 gap-5 border bg-background p-4 sm:p-5">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs uppercase tracking-wide text-muted-foreground">Decision workspace</p><h2 className="mt-1 text-xl font-semibold">{zh ? '下一步为什么值得做' : 'Why this next step is worth taking'}</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{zh ? '把问题、备选方案、正反论据和决策标准放在一起。缺少记录代表未知，不代表假设被否定；材料完整也不代表实验已成功。' : 'Read the question, alternatives, counterevidence and decision criteria together. Missing records mean unknown, not false; complete documentation does not mean an experiment succeeded.'}</p></div>
      <div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="outline" render={<Link to={url('references')} />}>{zh ? '文献论据' : 'Literature evidence'}</Button><Button type="button" size="sm" variant="outline" render={<Link to={`/learning?project=${encodeURIComponent(projectId)}`} />}>{zh ? '学习与下一轮实验' : 'Learning & next experiments'}</Button></div>
    </header>
    {goals.isPending ? <p role="status">{zh ? '正在读取问题与决策定义…' : 'Loading questions and decision definitions…'}</p> : null}
    {goals.isError ? <p role="alert">{zh ? '目标读取失败，无法判断决策状态。' : 'Goals could not be loaded; decision status is unknown.'}<Button type="button" variant="link" onClick={() => goals.refetch()}>{zh ? '重试' : 'Retry'}</Button></p> : null}
    {goals.isSuccess && params.get('goal') && !goals.data.some((goal) => goal.id === params.get('goal')) ? <p role="status" className="text-sm text-muted-foreground">{zh ? '链接中的问题在当前项目中不可用，下面显示当前可用的问题。' : 'The linked question is unavailable in this project. An available question is shown below.'}</p> : null}
    {selected && readiness ? <>
      <div className="grid gap-1 text-sm font-medium"><p>{zh ? '当前问题' : 'Current question'}</p><Select items={goals.data?.map((goal) => ({ value: goal.id, label: goal.title }))} value={selected.id} onValueChange={(value) => { if (!value) return; setEditing(false); setParams((current) => { const next = new URLSearchParams(current); next.set('goal', value); return next }, { replace: true }) }}><SelectTrigger className="w-full min-w-0" aria-label={zh ? '当前问题' : 'Current question'}><SelectValue /></SelectTrigger><SelectContent>{goals.data?.map((goal) => <SelectItem key={goal.id} value={goal.id}>{goal.title}</SelectItem>)}</SelectContent></Select></div>
      <div className="flex flex-wrap items-center gap-2"><Badge variant="outline">{zh ? '目标记录状态' : 'Recorded goal status'} · {selected.status}</Badge><span className="text-sm text-muted-foreground">{readiness.readyForReview ? (zh ? '材料具备 · 仍由研究者判断是否推进' : 'Documentation ready · a researcher must decide whether to proceed') : (zh ? '存在未补齐的条件 · 结论保持开放' : 'Unresolved conditions · keep the conclusion open')}</span>{canWrite ? <Button type="button" size="sm" variant="outline" onClick={() => setEditing(!editing)}>{zh ? '编辑决策定义' : 'Edit decision definition'}</Button> : null}</div>
      {editing && canWrite ? <ResearchDecisionEditor key={`${projectId}-${selected.id}`} projectId={projectId} goal={selected} notes={notes} complete={complete} onClose={() => setEditing(false)} /> : null}
      <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(16rem,1fr)]">
        <div className="grid min-w-0 gap-4"><div><h3 className="text-sm font-semibold">{zh ? '待验证假设' : 'Testable hypothesis'}</h3><p className="mt-1 whitespace-pre-wrap text-sm leading-6">{readiness.contract.hypothesis || (zh ? '尚未明确。请与目标描述区分，写出可被实验否定的判断。' : 'Not defined. Record an assertion that could be falsified, separately from the goal description.')}</p></div>
          {(['alternatives', 'success_criteria', 'falsification_criteria'] as const).map((key) => <div key={key}><h3 className="text-sm font-semibold">{({ alternatives: zh ? '备选方案' : 'Alternatives', success_criteria: zh ? '成功标准' : 'Success criteria', falsification_criteria: zh ? '反证 / 停止标准' : 'Falsification / stopping criteria' })[key]}</h3>{readiness.contract[key].length ? <ul className="mt-1 list-disc space-y-1 pl-5 text-sm leading-6">{readiness.contract[key].map((item) => <li key={item} className="whitespace-pre-wrap break-words">{item}</li>)}</ul> : <p className="mt-1 text-sm text-muted-foreground">{zh ? '尚未填写' : 'Not recorded'}</p>}</div>)}
          <div className="border-l-2 border-primary bg-muted/30 p-3"><h3 className="text-sm font-semibold">{zh ? '下一次决策及其触发条件' : 'Next decision and trigger'}</h3><p className="mt-1 whitespace-pre-wrap text-sm leading-6">{readiness.contract.next_decision || (zh ? '尚未填写：需要什么新信息，才决定继续、改路线或停止？' : 'Not recorded: what new information would trigger continuing, changing direction or stopping?')}</p></div>
        </div>
        <div className="grid content-start gap-2 border bg-muted/10 p-3"><h3 className="text-sm font-semibold">{zh ? '需要补齐什么' : 'What still needs attention'}</h3><p className="text-xs leading-5 text-muted-foreground">{zh ? '这是记录完整性检查，不是科研成功率或自动放行。' : 'Documentation checks, not a success probability or automatic authorization.'}</p>{readiness.criteria.map((item) => <p key={item.key} className="flex gap-2 text-sm leading-6"><span aria-hidden="true">{item.satisfied ? '✓' : '○'}</span><span>{checkLabels[item.key]} · {item.satisfied ? (zh ? '已记录' : 'Recorded') : (zh ? '未解决' : 'Unresolved')}</span></p>)}
          {!complete ? <p role="status" className="text-xs text-muted-foreground">{zh ? '论据未加载完整，来源检查暂不能作为完整结论。' : 'Evidence loading is incomplete; source checks are provisional.'}</p> : null}
          {readiness.missing.length ? <p className="text-xs text-muted-foreground">{readiness.missing.length} {complete ? (zh ? '个关联论据当前不可用；请核对引用。' : 'linked evidence records are unavailable; check the links.') : (zh ? '个关联论据尚未加载。' : 'linked evidence records are not yet loaded.')}</p> : null}
        </div>
      </div>
      <section className="grid gap-3" aria-label={zh ? '关联文献论据' : 'Linked literature evidence'}><h3 className="font-semibold">{zh ? '关联正反论据 · 关系针对卡片中的论点' : 'Linked evidence · each relation refers to the card’s assertion'}</h3>
        {evidence.isError ? <p role="alert">{zh ? '论据读取失败，不据此判断论据不存在。' : 'Evidence could not be loaded; this does not mean it is absent.'}<Button type="button" variant="link" onClick={() => evidence.refetch()}>{zh ? '重试论据' : 'Retry evidence'}</Button></p> : null}
        {readiness.linked.map((note) => <article key={note.id} className="grid min-w-0 gap-2 border p-3"><div className="flex flex-wrap gap-2"><Badge variant={note.relation === 'contradicts' ? 'destructive' : 'outline'}>{relationLabel(note.relation, zh)}</Badge><span className="text-xs text-muted-foreground">{note.review_status} · {note.anchor_status}</span></div><p className="text-sm font-medium">{note.argument}</p><blockquote className="border-l-2 pl-3 text-sm leading-6">{note.quote}</blockquote><p className="text-sm leading-6">{note.interpretation}</p><p className="text-xs leading-5 text-muted-foreground">{zh ? '边界' : 'Limits'} · {note.limitations}</p><a className="break-words text-sm text-primary underline" href={safeCitationUrl(note.source_url)} target="_blank" rel="noopener noreferrer">{note.document_title}</a></article>)}
        {!readiness.contract.evidence_note_ids.length ? <p className="text-sm text-muted-foreground">{zh ? '尚未明确关联论据；不会把项目中的所有论文自动视为这个假设的证据。' : 'No evidence explicitly linked. The project library is not automatically treated as evidence for this hypothesis.'}</p> : null}
        {evidence.hasNextPage ? <Button type="button" variant="outline" disabled={evidence.isFetchingNextPage} onClick={() => evidence.fetchNextPage()}>{zh ? '继续加载论据' : 'Load more evidence'}</Button> : null}
      </section>
      {linkedRecords.length ? <div className="grid gap-2"><h3 className="text-sm font-semibold">{zh ? '与这个问题关联的决策记录' : 'Decision records linked to this question'}</h3>{linkedRecords.map((entry) => <Link key={entry.id} to={url('timeline')} className="text-sm text-primary underline">{entry.decision_ref ? `${entry.decision_ref} · ` : ''}{entry.title} · {entry.outcome}</Link>)}</div> : null}
    </> : goals.isSuccess ? <p className="text-sm text-muted-foreground">{zh ? '还没有研究问题。先在下方目标树中添加一个具体问题，再填写决策标准。' : 'No research questions yet. Add a concrete question in the goal tree below, then define its decision criteria.'}</p> : null}
    <section className="grid gap-3 border-t pt-4" aria-label={zh ? '项目学习记录' : 'Project learning ledger'}><div className="flex flex-wrap items-center justify-between gap-2"><div><h3 className="font-semibold">{zh ? '项目学习记录' : 'Project learning ledger'}</h3><p className="mt-1 text-xs text-muted-foreground">{zh ? '最近 3 条决策、结果、方法或修正的索引；完整依据与推理见决策记录。' : 'The three latest decisions, results, methods or resolutions. Open the decision record for full evidence and reasoning.'}</p></div><Button type="button" variant="outline" size="sm" render={<Link to={url('timeline')} />}>{zh ? '完整决策记录' : 'Full decision record'}</Button></div>
      {timeline.isPending ? <p role="status">{zh ? '正在读取项目历史…' : 'Loading project history…'}</p> : null}
      {timeline.isError ? <p role="alert">{zh ? '项目历史读取失败，不能据此认定没有决策记录。' : 'History could not be loaded; this does not mean no decisions exist.'}<Button type="button" variant="link" onClick={() => timeline.refetch()}>{zh ? '重试历史' : 'Retry history'}</Button></p> : null}
      {ledger.map((entry) => <article key={entry.id} className="grid gap-1 border-l-2 border-border pl-3"><p className="text-xs text-muted-foreground">{entry.occurred_at.slice(0, 10)} · {entry.entry_type} · {entry.decided_by}</p><h4 className="text-sm font-medium"><Link to={url('timeline')} className="text-primary underline">{entry.decision_ref ? `${entry.decision_ref} · ` : ''}{entry.title}</Link></h4><p className="text-xs text-muted-foreground">{zh ? '记录中的结论' : 'Recorded outcome'} · {entry.outcome}{entry.supersedes_id ? ` · ${zh ? '替代既有记录' : 'Supersedes an earlier record'} ${entry.supersedes_id.slice(0, 8)}` : ''}</p></article>)}
      {timeline.isSuccess && !ledger.length ? <p className="text-sm text-muted-foreground">{zh ? '尚无这些类型的记录；不据此评价项目是否产生了学习。' : 'No records of these types yet; this does not establish whether the project has learned anything.'}</p> : null}
    </section>
  </section>
}
