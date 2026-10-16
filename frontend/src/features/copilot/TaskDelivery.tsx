import { useState } from 'react'
import { requireCopilotWrite, useCopilotReadOnly } from './commandAccess'
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
import { deliveryMessage, executionLabel, reportCharacters } from './deliveryDisplay'

const Outcome = z.object({
  decision_record_id: z.string().optional(),
  scientific_review: z.string().optional(),
  scientific_review_error: z.string().optional(),
  sections: z.record(z.string(), z.string()).optional(),
  summary: z.string().optional(), missing: z.array(z.string()).optional(), next_action: z.string().optional(),
  steps: z.array(z.object({ id: z.string(), title: z.string(), title_zh: z.string(), status: z.string() })).optional(),
  deliverables: z.array(z.object({ kind: z.string(), id: z.string() })).optional(),
  evidence: z.array(z.object({ call_id: z.string(), tool: z.string(), successful: z.boolean() })).optional(),
})
const SECTION_LABELS: Record<string, [string, string]> = {
  objective: ['Objective', '研究目标'], constraints: ['Constraints', '约束条件'],
  success_criteria: ['Success criteria', '成功标准'], missing_inputs: ['Missing inputs', '待补充输入'],
  search_scope: ['Search scope', '检索范围'], evidence_comparison: ['Evidence comparison', '证据比较'],
  disagreements: ['Disagreements', '证据分歧'], limitations: ['Limitations', '限制'],
  route_comparison: ['Route comparison', '路线比较'], inputs: ['Inputs', '所需输入'],
  risks: ['Risks', '风险'], next_step: ['Next step', '下一步'],
  current_state: ['Current state', '当前状态'], blockers: ['Blockers', '阻碍'],
  recovery: ['Recovery proposal', '恢复建议'], observations: ['Observations', '观察结果'],
  hypotheses: ['Hypotheses', '假设'], next_round: ['Next round', '下一轮计划'],
}
function ExecutionError({ error, zh }: { error?: string | null; zh: boolean }) {
  if (!error) return null
  return <div className="space-y-2"><p role="alert" className="text-sm text-destructive break-words">{deliveryMessage(error, zh)}</p>{deliveryMessage(error, zh) !== error ? <Disclosure title={zh ? '查看原始错误' : 'Original error'}><p className="break-words text-xs">{error}</p></Disclosure> : null}</div>
}

export function TaskDelivery({ run }: { run: AgentRun }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const sectionLabel = (key: string) => SECTION_LABELS[key]?.[zh ? 1 : 0] ?? key.replaceAll('_', ' ')
  const readOnly = useCopilotReadOnly()
  const client = useQueryClient()
  const [brief, setBrief] = useState<{ text: string; version: number } | null>(null)
  const [reason, setReason] = useState('')
  const record = useMutation({ mutationFn: () => { requireCopilotWrite(); return saveTaskDecisionRecord(run.id, run.version) }, onSuccess: (data) => {
    client.setQueryData(['agent-run', run.project_id, run.id], data)
    void client.invalidateQueries({ queryKey: ['timeline', run.project_id] })
  }, onError: () => { void client.invalidateQueries({ queryKey: ['agent-run', run.project_id, run.id] }) } })
  const prepareBrief = useMutation({ mutationFn: () => getProjectOverview(run.project_id), onSuccess: (data) => {
    const sections = run.outcome?.sections as Record<string, string> | undefined
    setBrief({ text: [String(run.outcome?.summary ?? ''), ...Object.entries(sections ?? {}).map(([key, value]) => `${sectionLabel(key)}\n${value}`)].join('\n\n'), version: data.project.version })
  } })
  const applyBrief = useMutation({ mutationFn: () => { requireCopilotWrite(); return updateProjectPrompt(run.project_id, brief!.text.trim(), brief!.version, reason.trim()) }, onSuccess: () => {
    setBrief(null); setReason('')
    void client.invalidateQueries({ queryKey: ['project-overview', run.project_id] })
    void client.invalidateQueries({ queryKey: ['projects'] })
    void client.invalidateQueries({ queryKey: ['project-library'] })
  } })
  const result = Outcome.safeParse(run.outcome ?? {})
  if (!result.success) return <><ExecutionError error={run.error} zh={zh} /><p role="alert">{zh ? '任务结果格式无效，请重新加载。' : 'Invalid task result. Reload the task.'}</p></>
  const outcome = result.data
  const characters = reportCharacters(outcome)
  const hasReport = Boolean(outcome.summary?.trim() || Object.values(outcome.sections ?? {}).some((value) => value.trim()))
  const reviewCompleted = outcome.scientific_review === 'automated_review_completed'
  const reviewUnavailable = outcome.scientific_review === 'unavailable' || Boolean(outcome.scientific_review_error)
  const reviewLabel = reviewCompleted ? (zh ? '已完成' : 'Completed')
    : reviewUnavailable ? (zh ? '未完成' : 'Incomplete') : (zh ? '未记录完成' : 'No completion recorded')
  const base = `/research?project=${encodeURIComponent(run.project_id)}`
  const terminal = ['succeeded', 'failed'].includes(run.status)
  const issueLabels: Record<string, string> = zh
    ? { structured_delivery_required: '答复缺少所需章节，请审核或补充要求。', unverified_evidence_call_ids: '部分引用没有对应的成功工具记录。', scientific_review_unavailable: '自动科学复核未完成，请人工审核。' }
    : { structured_delivery_required: 'Required delivery sections are missing. Review the answer or add instructions.', unverified_evidence_call_ids: 'Some citations have no matching successful tool record.', scientific_review_unavailable: 'Scientific review did not complete. Review the answer manually.' }
  issueLabels.delivery_length_exceeded = zh ? '交付超过本次要求的字数限制，需要精简。' : 'The delivery exceeds the requested character limit and needs shortening.'
  const reviewErrors: Record<string, [string, string]> = {
    llm_output_truncated: ['Review exceeded the model output limit. Shorten the scope or adjust the model limit and retry.', '复核达到模型输出上限。可缩小范围，或调整模型上限后重试。'],
    llm_completion_deadline_exceeded: ['Review timed out. Retry after the model service recovers.', '复核请求超时，可在模型服务恢复后重试。'],
    copilot_turn_limit_reached: ['Review reached the task turn limit. Continue with a sufficient budget.', '复核达到任务轮次上限，可补充预算后继续。'],
    invalid_review_delivery: ['The review result failed delivery validation. The saved draft still needs review.', '复核结果未通过交付校验，已保存的草稿仍需审核。'],
  }
  if (outcome.scientific_review_error && reviewErrors[outcome.scientific_review_error]) {
    issueLabels.scientific_review_unavailable = reviewErrors[outcome.scientific_review_error][zh ? 1 : 0]
  }
  const missingLabel = (item: string) => issueLabels[item] ?? outcome.steps?.find((step) => step.id === item)?.[zh ? 'title_zh' : 'title'] ?? SECTION_LABELS[item]?.[zh ? 1 : 0] ?? deliveryMessage(item, zh)
  const remaining = (outcome.missing ?? []).filter((item) => item !== run.error)
  return <section className="task-report space-y-5 border-t border-border pt-4" aria-label={zh ? '任务交付' : 'Task delivery'}>
    <h4 className="text-base font-semibold">{hasReport ? (zh ? '交付报告' : 'Delivery report') : (zh ? '本次结果' : 'Current result')}</h4>
    <dl className="task-report-meta">
      <div><dt className="text-xs text-text-secondary">{zh ? '任务执行' : 'Execution'}</dt><dd className="font-medium">{executionLabel(run.status, zh)}</dd></div>
      <div><dt className="text-xs text-text-secondary">{zh ? '自动事实复核' : 'Automated factual review'}</dt><dd className="font-medium">{reviewLabel}</dd></div>
      <div><dt className="text-xs text-text-secondary">{zh ? '报告字符数' : 'Report characters'}</dt><dd className="font-medium tabular-nums">{hasReport ? characters : (zh ? '尚无报告' : 'No report yet')}</dd></div>
    </dl>

    <ExecutionError error={run.error} zh={zh} />
    {outcome.scientific_review === 'automated_review_completed' ? <p className="text-xs text-text-secondary">{zh ? '自动事实复核已完成；这不代表科研验证或人工批准。' : 'Automated factual review completed. This does not constitute scientific validation or human approval.'}</p> : null}
    {outcome.steps?.length ? <ol className="space-y-2">{outcome.steps.map((step) => <li key={step.id} className="rounded border border-border-soft p-2 text-sm"><span className="mr-2">{step.status === 'completed' ? '✓' : '○'}</span>{zh ? step.title_zh : step.title}<span className="ml-2 text-xs text-text-secondary">{step.status === 'completed' ? (zh ? '已核对记录' : 'Records checked') : (zh ? '待完成' : 'Pending')}</span></li>)}</ol> : null}
    {outcome.summary ? <div><p className="mb-2 text-sm font-semibold">{zh ? '结论摘要' : 'Summary'}</p><p className="whitespace-pre-wrap break-words text-sm leading-7">{outcome.summary}</p></div> : null}
    {outcome.sections && Object.keys(outcome.sections).length ? <Disclosure key={run.id} title={zh ? '查看完整交付内容' : 'Full deliverable'} defaultOpen={characters <= 1200}><dl className="space-y-5">{Object.entries(outcome.sections).map(([key, value]) => <div key={key}><dt className="mb-1 text-sm font-semibold">{sectionLabel(key)}</dt><dd className="whitespace-pre-wrap break-words text-sm leading-7">{value}</dd></div>)}</dl></Disclosure> : null}
    {remaining.length ? <div className="task-report-pending"><p className="mb-2 text-sm font-semibold">{zh ? '尚未完成或需要核对' : 'Remaining work or checks'}</p><ul className="list-disc space-y-1 pl-5 text-sm leading-7 break-words">{remaining.map((item, i) => <li key={i}>{missingLabel(item)}</li>)}</ul></div> : null}
    {outcome.next_action ? <div><p className="mb-2 text-sm font-semibold">{zh ? '下一步' : 'Next action'}</p><p className="text-sm leading-7 break-words">{deliveryMessage(outcome.next_action, zh)}</p></div> : null}
    {outcome.deliverables?.map((item) => <Link className="block text-sm text-primary" key={`${item.kind}-${item.id}`} to={`${base}&tab=${item.kind === 'literature' ? 'references' : 'data'}`}>{item.kind === 'literature' ? (zh ? '打开检索与文献' : 'Open literature') : (zh ? '打开待审核研究笔记' : 'Open research notes')} · {item.id.slice(0, 8)}</Link>)}
    {outcome.evidence?.length ? <Disclosure title={zh ? '查看来源与操作记录' : 'Sources and actions'}><ul className="space-y-1 text-xs">{outcome.evidence.map((item) => <li key={item.call_id}>{item.successful ? '✓' : '×'} {item.tool} · {item.call_id}</li>)}</ul></Disclosure> : null}
    {hasReport ? <Disclosure title={zh ? '计数与审核说明' : 'Counting and review notes'}><p className="text-xs text-text-secondary">{zh ? '字符数包含摘要、原章节标题与正文、待补事项和下一步；不含页面提示。步骤核对仅说明交付记录存在，科研结论和计算提交仍需对应审核。' : 'Counts summary, original section titles and text, remaining items and next action; excludes interface labels. Step checks confirm records only; scientific conclusions and compute submission still need review.'}</p></Disclosure> : null}
    {terminal && outcome.summary && !outcome.decision_record_id ? <Button type="button" variant="outline" disabled={readOnly || record.isPending} onClick={() => record.mutate()}>{zh ? '保存为待审核计划记录' : 'Save as a plan for review'}</Button> : null}
    {outcome.decision_record_id ? <p className="text-sm" role="status">{zh ? '已保存到项目决策记录，可关联目标并继续编辑。' : 'Saved to the project decision record. You can attach a goal and edit it there.'}</p> : null}
    {terminal && outcome.summary && run.task_contract?.service_kind === 'brief' ? <Button type="button" variant="outline" disabled={readOnly || prepareBrief.isPending} onClick={() => prepareBrief.mutate()}>{zh ? '编辑并应用为项目任务书' : 'Edit and apply as project brief'}</Button> : null}
    {brief ? <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); applyBrief.mutate() }}>
      <label>{zh ? '任务书草案' : 'Brief draft'}<Textarea value={brief.text} onChange={(e) => setBrief({ ...brief, text: e.target.value })} /></label>
      <label>{zh ? '修改原因' : 'Reason for the change'}<Textarea value={reason} onChange={(e) => setReason(e.target.value)} /></label>
      <Button type="submit" disabled={readOnly || !brief.text.trim() || !reason.trim() || applyBrief.isPending}>{zh ? '保存任务书' : 'Save project brief'}</Button>
      <Button type="button" variant="ghost" onClick={() => setBrief(null)}>{zh ? '取消编辑' : 'Cancel edit'}</Button>
    </form> : null}
    {record.error || prepareBrief.error || applyBrief.error ? <p role="alert" className="text-sm text-destructive">{String(record.error ?? prepareBrief.error ?? applyBrief.error)}</p> : null}
    <Link className="block pt-1 text-sm text-primary" to={`${base}&tab=timeline`}>{zh ? '查看项目决策树' : 'Open the project decision tree'}</Link>
  </section>
}
