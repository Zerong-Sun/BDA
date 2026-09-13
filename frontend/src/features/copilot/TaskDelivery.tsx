import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '../../components/ui/Button'
import { Textarea } from '../../components/ui/textarea'
import { saveTaskDecisionRecord } from '../../lib/api/agentRuns'
import { getProjectOverview, updateProjectPrompt } from '../../lib/api/projects'
import { Link } from 'react-router'
import { z } from 'zod'
import type { AgentRun } from '../../lib/api/agentRuns'
import { useI18n } from '../../lib/i18n'
import { Disclosure } from '../../components/ui/Disclosure'
import { deliveryLabel } from './taskPresentation'

const Outcome = z.object({
  decision_record_id: z.string().optional(),
  sections: z.record(z.string(), z.string()).optional(),
  summary: z.string().optional(), missing: z.array(z.string()).optional(), next_action: z.string().optional(),
  steps: z.array(z.object({ id: z.string(), title: z.string(), title_zh: z.string(), status: z.string() })).optional(),
  deliverables: z.array(z.object({ kind: z.string(), id: z.string() })).optional(),
  evidence: z.array(z.object({ call_id: z.string(), tool: z.string(), successful: z.boolean() })).optional(),
})
export function TaskDelivery({ run }: { run: AgentRun }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const client = useQueryClient()
  const [brief, setBrief] = useState<{ text: string; version: number } | null>(null)
  const [reason, setReason] = useState('')
  const record = useMutation({ mutationFn: () => saveTaskDecisionRecord(run.id, run.version), onSuccess: (data) => {
    client.setQueryData(['agent-run', run.project_id, run.id], data)
    void client.invalidateQueries({ queryKey: ['timeline', run.project_id] })
  }, onError: () => { void client.invalidateQueries({ queryKey: ['agent-run', run.project_id, run.id] }) } })
  const prepareBrief = useMutation({ mutationFn: () => getProjectOverview(run.project_id), onSuccess: (data) => {
    const sections = run.outcome?.sections as Record<string, string> | undefined
    setBrief({ text: [String(run.outcome?.summary ?? ''), ...Object.entries(sections ?? {}).map(([key, value]) => `${key}\n${value}`)].join('\n\n'), version: data.project.version })
  } })
  const applyBrief = useMutation({ mutationFn: () => updateProjectPrompt(run.project_id, brief!.text.trim(), brief!.version, reason.trim()), onSuccess: () => {
    setBrief(null); setReason('')
    void client.invalidateQueries({ queryKey: ['project-overview', run.project_id] })
    void client.invalidateQueries({ queryKey: ['projects'] })
    void client.invalidateQueries({ queryKey: ['project-library'] })
  } })
  const result = Outcome.safeParse(run.outcome ?? {})
  if (!result.success) return <p role="alert">{zh ? '任务结果格式无效，请重新加载。' : 'Invalid task result. Reload the task.'}</p>
  const outcome = result.data
  const base = `/research?project=${encodeURIComponent(run.project_id)}`
  const terminal = ['succeeded', 'failed'].includes(run.status)
  const issueLabels: Record<string, string> = zh ? { structured_delivery_required: '答复缺少合规的交付结构，请审核或补充要求。', unverified_evidence_call_ids: '部分引用没有对应的成功工具记录。', scientific_review_unavailable: '自动科学复核未完成，请人工审核。' } : {}
  const missingLabel = (item: string) => issueLabels[item] ?? outcome.steps?.find((step) => step.id === item)?.[zh ? 'title_zh' : 'title'] ?? item
  return <section className="space-y-3 rounded-lg border border-border p-3" aria-label={zh ? '任务交付' : 'Task delivery'}>
    <h4 className="font-semibold">{deliveryLabel(run, zh)}</h4>
    {outcome.steps?.length ? <ol className="space-y-2">{outcome.steps.map((step) => <li key={step.id} className="rounded border border-border-soft p-2 text-sm"><span className="mr-2">{step.status === 'completed' ? '✓' : '○'}</span>{zh ? step.title_zh : step.title}<span className="ml-2 text-xs text-text-secondary">{step.status === 'completed' ? (zh ? '已核对记录' : 'Records checked') : (zh ? '待完成' : 'Pending')}</span></li>)}</ol> : null}
    {outcome.summary ? <div><p className="text-xs text-text-secondary">{zh ? '交付内容与依据' : 'Deliverable and basis'}</p><p className="whitespace-pre-wrap break-words text-sm">{outcome.summary}</p></div> : null}
    {outcome.sections && Object.keys(outcome.sections).length ? <Disclosure title={zh ? '查看完整交付内容' : 'Full deliverable'}><dl className="space-y-3">{Object.entries(outcome.sections).map(([key, value]) => <div key={key}><dt className="text-xs font-semibold">{key.replaceAll('_', ' ')}</dt><dd className="whitespace-pre-wrap text-sm">{value}</dd></div>)}</dl></Disclosure> : null}
    {outcome.missing?.length ? <div><p className="text-xs text-text-secondary">{zh ? '尚未完成或需要核对' : 'Remaining work or checks'}</p><ul className="list-disc pl-5 text-sm">{outcome.missing.map((item, i) => <li key={i}>{missingLabel(item)}</li>)}</ul></div> : null}
    {outcome.next_action ? <div><p className="text-xs text-text-secondary">{zh ? '下一步' : 'Next action'}</p><p className="text-sm">{outcome.next_action}</p></div> : null}
    {outcome.deliverables?.map((item) => <Link className="block text-sm text-primary" key={`${item.kind}-${item.id}`} to={`${base}&tab=${item.kind === 'literature' ? 'references' : 'data'}`}>{item.kind === 'literature' ? (zh ? '打开检索与文献' : 'Open literature') : (zh ? '打开待审核研究笔记' : 'Open research notes')} · {item.id.slice(0, 8)}</Link>)}
    {outcome.evidence?.length ? <Disclosure title={zh ? '查看来源与操作记录' : 'Sources and actions'}><ul className="space-y-1 text-xs">{outcome.evidence.map((item) => <li key={item.call_id}>{item.successful ? '✓' : '×'} {item.tool} · {item.call_id}</li>)}</ul></Disclosure> : null}
    <p className="text-xs text-text-secondary">{zh ? '步骤核对说明交付记录存在；科研结论和计算提交仍需对应审核。' : 'Step checks confirm delivery records. Scientific conclusions and compute submission still need their respective review.'}</p>
    {terminal && outcome.summary && !outcome.decision_record_id ? <Button type="button" variant="outline" disabled={record.isPending} onClick={() => record.mutate()}>{zh ? '保存为待审核计划记录' : 'Save as a plan for review'}</Button> : null}
    {outcome.decision_record_id ? <p className="text-sm" role="status">{zh ? '已保存到项目决策记录，可关联目标并继续编辑。' : 'Saved to the project decision record. You can attach a goal and edit it there.'}</p> : null}
    {terminal && outcome.summary && run.task_contract?.service_kind === 'brief' ? <Button type="button" variant="outline" disabled={prepareBrief.isPending} onClick={() => prepareBrief.mutate()}>{zh ? '编辑并应用为项目任务书' : 'Edit and apply as project brief'}</Button> : null}
    {brief ? <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); applyBrief.mutate() }}>
      <label>{zh ? '任务书草案' : 'Brief draft'}<Textarea value={brief.text} onChange={(e) => setBrief({ ...brief, text: e.target.value })} /></label>
      <label>{zh ? '修改原因' : 'Reason for the change'}<Textarea value={reason} onChange={(e) => setReason(e.target.value)} /></label>
      <Button type="submit" disabled={!brief.text.trim() || !reason.trim() || applyBrief.isPending}>{zh ? '保存任务书' : 'Save project brief'}</Button>
      <Button type="button" variant="ghost" onClick={() => setBrief(null)}>{zh ? '取消编辑' : 'Cancel edit'}</Button>
    </form> : null}
    {record.error || prepareBrief.error || applyBrief.error ? <p role="alert" className="text-sm text-destructive">{String(record.error ?? prepareBrief.error ?? applyBrief.error)}</p> : null}
    <Link className="text-sm text-primary" to={`${base}&tab=timeline`}>{zh ? '查看项目决策树' : 'Open the project decision tree'}</Link>
  </section>
}
