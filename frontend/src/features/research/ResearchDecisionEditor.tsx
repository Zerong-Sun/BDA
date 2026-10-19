import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '../../components/ui/Button'
import { Checkbox } from '../../components/ui/checkbox'
import { Textarea } from '../../components/ui/textarea'
import { updateResearchDecision } from '../../lib/api/researchDecision'
import type { ResearchGoal } from '../../lib/api/researchGoals'
import { useI18n } from '../../lib/i18n'
import { goalContract } from './decisionReadiness'
import { relationLabel, type EvidenceNote } from './evidenceNotes'

export function ResearchDecisionEditor({ projectId, goal, notes, complete, onClose }: {
  projectId: string; goal: ResearchGoal; notes: EvidenceNote[]; complete: boolean; onClose: () => void
}) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const client = useQueryClient()
  // A background refetch must not silently authorize overwriting a newer contract.
  const [baseVersion] = useState(goal.version)
  const [draft, setDraft] = useState(() => goalContract(goal))
  const [lines, setLines] = useState(() => ({ alternatives: draft.alternatives.join('\n'), success_criteria: draft.success_criteria.join('\n'), falsification_criteria: draft.falsification_criteria.join('\n') }))
  const save = useMutation({
    mutationFn: () => updateResearchDecision(goal.id, baseVersion, { ...draft,
      alternatives: lines.alternatives.split('\n').map((value) => value.trim()).filter(Boolean),
      success_criteria: lines.success_criteria.split('\n').map((value) => value.trim()).filter(Boolean),
      falsification_criteria: lines.falsification_criteria.split('\n').map((value) => value.trim()).filter(Boolean),
    }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['research-goals', projectId] }); onClose() },
  })
  const missingIds = draft.evidence_note_ids.filter((id) => !notes.some((note) => note.id === id))
  const toggle = (id: string, checked: boolean) => setDraft({ ...draft, evidence_note_ids: checked ? [...draft.evidence_note_ids, id] : draft.evidence_note_ids.filter((value) => value !== id) })
  return <form className="grid gap-4 border border-primary/40 p-4" onSubmit={(event) => { event.preventDefault(); save.mutate() }} aria-label={zh ? '编辑决策定义' : 'Edit decision definition'}>
    <div className="flex items-center justify-between gap-2"><h3 className="font-semibold">{zh ? '明确这个问题的决策条件' : 'Define what would change this decision'}</h3><Button type="button" variant="ghost" disabled={save.isPending} onClick={onClose}>{zh ? '取消' : 'Cancel'}</Button></div>
    <fieldset className="grid gap-4" disabled={save.isPending}>
      <label className="grid gap-1.5 text-sm">{zh ? '待验证假设' : 'Testable hypothesis'}<Textarea maxLength={3000} value={draft.hypothesis} onChange={(event) => setDraft({ ...draft, hypothesis: event.target.value })} /></label>
      {(['alternatives', 'success_criteria', 'falsification_criteria'] as const).map((key) => <label key={key} className="grid gap-1.5 text-sm">{({ alternatives: zh ? '备选方案（包含当前方案，每行一个）' : 'Alternatives (include the current option; one per line)', success_criteria: zh ? '成功标准（指标、阈值、条件，每行一项）' : 'Success criteria (metric, threshold, conditions; one per line)', falsification_criteria: zh ? '反证 / 停止标准（每行一项）' : 'Falsification / stopping criteria (one per line)' })[key]}<Textarea maxLength={10010} value={lines[key]} onChange={(event) => setLines({ ...lines, [key]: event.target.value })} /></label>)}
      <label className="grid gap-1.5 text-sm">{zh ? '下一次要做的决策及其触发条件' : 'Next decision and its trigger'}<Textarea maxLength={2000} value={draft.next_decision} onChange={(event) => setDraft({ ...draft, next_decision: event.target.value })} /></label>
      <div className="grid gap-2"><p className="text-sm font-medium">{zh ? '明确关联哪些论文论据' : 'Explicitly link literature evidence'}</p>
        <p className="text-xs text-muted-foreground">{zh ? '选择只建立关系，不认可论据，也不把论文结果当作项目实验结果。' : 'Selection creates a link; it does not accept the evidence or turn paper findings into project experiments.'}</p>
        {!complete ? <p role="status" className="text-xs text-muted-foreground">{zh ? '论据列表尚未完整，保留已关联但未加载的 ID。' : 'Evidence is not fully loaded. Existing links to unloaded IDs are preserved.'}</p> : null}
        <div className="grid max-h-64 gap-2 overflow-auto">
          {notes.map((note) => <label key={note.id} className="flex items-start gap-2 border p-2 text-sm"><Checkbox checked={draft.evidence_note_ids.includes(note.id)} onCheckedChange={(checked) => toggle(note.id, checked)} /><span>{relationLabel(note.relation, zh)} · {note.argument}<span className="mt-1 block text-xs text-muted-foreground">{note.document_title}</span></span></label>)}
          {missingIds.map((id) => <label key={id} className="flex items-center gap-2 text-xs"><Checkbox checked onCheckedChange={() => toggle(id, false)} /><span>{zh ? '未解析的已有引用' : 'Unresolved existing link'} · {id}</span></label>)}
        </div>
      </div>
    </fieldset>
    <p className="text-xs text-muted-foreground">{zh ? '可以先保存不完整定义。系统标出未填写项，不补写标准，也不自动判断实验成败。' : 'Incomplete definitions can be saved. Missing criteria remain explicit; outcomes are not automatically judged.'}</p>
    {save.isError ? <p role="alert" className="text-sm text-destructive">{save.error instanceof Error ? save.error.message : (zh ? '保存失败' : 'Save failed')}</p> : null}
    <Button type="submit" disabled={save.isPending}>{zh ? '保存决策定义' : 'Save decision definition'}</Button>
  </form>
}
