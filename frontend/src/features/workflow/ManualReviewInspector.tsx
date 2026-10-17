import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { getWorkflowGraph, updateWorkflowNode } from '../../lib/api/workflow'
import type { WorkflowNode } from '../../lib/schemas/workflow'
import { useI18n } from '../../lib/i18n'
import { Button } from '../../components/ui/Button'
import { Textarea } from '../../components/ui/textarea'
import { Frame, FrameHeader, FramePanel, FrameTitle } from '../../components/reui/frame'

/** Manual review records use versioned workflow edits, never script execution. */
export function ManualReviewInspector({ node, workflowVersion, readOnly, onDirtyChange }: {
  node: WorkflowNode; workflowVersion?: number; readOnly: boolean; onDirtyChange?: (dirty: boolean) => void
}) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const client = useQueryClient()
  const [baseline, setBaseline] = useState({ node, version: workflowVersion })
  const [criteria, setCriteria] = useState(String(node.parameters.acceptance_criteria ?? node.parameters.description ?? ''))
  const [notes, setNotes] = useState(String(node.parameters.review_notes ?? ''))
  const [saved, setSaved] = useState(false)
  const effectiveVersion = baseline.version ?? (node.version === baseline.node.version ? workflowVersion : undefined)
  const dirty = criteria !== String(baseline.node.parameters.acceptance_criteria ?? baseline.node.parameters.description ?? '')
    || notes !== String(baseline.node.parameters.review_notes ?? '')
  useEffect(() => { onDirtyChange?.(!readOnly && dirty); return () => onDirtyChange?.(false) }, [dirty, readOnly, onDirtyChange])
  const save = useMutation({
    mutationFn: async () => {
      if (readOnly || !criteria.trim() || effectiveVersion === undefined) throw new Error(zh ? '请检查编辑权限、版本和验收条件。' : 'Check edit access, version and acceptance criteria.')
      return updateWorkflowNode(node.workflow_run_id, node.id, { parameters: {
        ...baseline.node.parameters, acceptance_criteria: criteria.trim(), description: criteria.trim(), review_status: 'pending_review',
        ...(notes || Object.hasOwn(baseline.node.parameters, 'review_notes') ? { review_notes: notes.trim() } : {}),
      } }, effectiveVersion)
    },
    onSuccess: async (updated) => {
      // Record the completed write before fetching a new version. A failed read
      // must not make a successful save appear to have failed or silently retry it.
      setCriteria(String(updated.parameters.acceptance_criteria ?? ''))
      setNotes(String(updated.parameters.review_notes ?? ''))
      setBaseline({ node: updated, version: undefined })
      setSaved(true)
      await client.invalidateQueries({ queryKey: ['workflow-graph', node.workflow_run_id] })
      await client.invalidateQueries({ queryKey: ['workflow-preflight', node.workflow_run_id] })
    },
  })
  const reload = useMutation({
    mutationFn: async () => {
      const graph = await getWorkflowGraph(node.workflow_run_id)
      if (!graph.nodes.some((item) => item.id === node.id)) throw new Error(zh ? '此步骤已被移除，请刷新工作流。' : 'This step was removed. Refresh the workflow.')
      return graph
    },
    onSuccess: (graph) => {
      const latest = graph.nodes.find((item) => item.id === node.id)
      if (!latest) return
      setBaseline({ node: latest, version: graph.workflow.version })
      setCriteria(String(latest.parameters.acceptance_criteria ?? latest.parameters.description ?? ''))
      setNotes(String(latest.parameters.review_notes ?? ''))
      setSaved(false); save.reset()
      client.setQueryData(['workflow-graph', node.workflow_run_id], graph)
    },
  })
  const locked = readOnly || save.isPending || reload.isPending
  return <Frame variant="inverse" spacing="xs" className="h-full w-full min-w-0">
    <FrameHeader><FrameTitle>{zh ? '人工审阅步骤' : 'Manual review step'}</FrameTitle></FrameHeader>
    <FramePanel className="space-y-3 p-3">
      <h3 className="break-words font-semibold">{node.node_key}</h3>
      <p className="text-sm text-text-secondary">{zh ? '记录输入、文献来源和验收条件。保存修改后仍为待审阅，不会启动计算或代表任务已完成。' : 'Record inputs, literature sources and acceptance criteria. Saving keeps the review pending; it does not run computation or record completion.'}</p>
      {typeof node.parameters.evidence_summary === 'string' && <p className="whitespace-pre-wrap rounded border border-border-soft p-3 text-sm">{node.parameters.evidence_summary}</p>}
      {node.parameters.criteria_basis === 'case_recommendation' && <p className="text-xs text-text-secondary">{zh ? '以下门控是可修改的案例推荐值；不代表数据已通过，也不是通用实验标准。' : 'These editable gates are case recommendations; they do not indicate a passing result or a universal assay standard.'}</p>}
      <label className="block space-y-1 text-sm"><span>{zh ? '输入、文献来源与验收条件' : 'Inputs, sources and acceptance criteria'}</span><Textarea rows={12} maxLength={10000} value={criteria} disabled={locked} onChange={(event) => { setCriteria(event.target.value); setSaved(false) }} /></label>
      <label className="block space-y-1 text-sm"><span>{zh ? '本步骤记录与结论' : 'Step observations and conclusions'}</span><Textarea rows={6} maxLength={10000} value={notes} disabled={locked} onChange={(event) => { setNotes(event.target.value); setSaved(false) }} placeholder={zh ? '记录已观察的结果、证据链接和待确认事项。' : 'Record observations, evidence links and unresolved questions.'} /></label>
      <Button type="button" disabled={locked || !criteria.trim() || !dirty || effectiveVersion === undefined} onClick={() => save.mutate()}>{zh ? '保存审阅条件' : 'Save review criteria'}</Button>
      <Button type="button" variant="outline" disabled={locked} onClick={() => reload.mutate()}>{zh ? '放弃修改并读取最新版本' : 'Discard edits and load latest'}</Button>
      {saved ? <p role="status">{zh ? '审阅条件已保存，仍待复核。' : 'Review criteria saved; review remains pending.'}</p> : null}
      {save.isError ? <p role="alert">{save.error.message}</p> : null}
      {reload.isError ? <p role="alert">{reload.error.message}</p> : null}
    </FramePanel>
  </Frame>
}
