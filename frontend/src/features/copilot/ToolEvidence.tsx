import { Link } from 'react-router'
import { z } from 'zod'
import { useI18n } from '../../lib/i18n'
import { Disclosure } from '../../components/ui/Disclosure'
import { Button } from '../../components/ui/Button'

const Selection = z.object({ artifact_id: z.string(), residues: z.array(z.object({ chain: z.string(), seq: z.number().int(), insertion_code: z.string().nullable().optional(), name: z.string().optional() })).max(200), truncated: z.boolean().optional() })
const Highlighted = z.array(z.strictObject({ chain: z.string(), seq: z.number().int(), insertion_code: z.string().nullable().optional(), name: z.string().optional() })).max(200)
const Output = z.object({ artifact_id: z.string().optional(), source_artifact_id: z.string().optional(), candidate_id: z.string().optional(), experiment_result_id: z.string().optional(), knowledge_entry_id: z.string().optional(), status: z.string().optional(), viewer_selection: Selection.optional(), filename: z.string().optional(), checksum_sha256: z.string().optional(), summary: z.unknown().optional(), provenance: z.unknown().optional(), interpretation: z.string().optional(), evidence_kind: z.string().optional() }).loose()
const Call = z.object({ name: z.string().optional(), result: z.unknown().optional() }).loose()

export function ToolEvidence({ calls = [], projectId, content }: { calls?: unknown[]; projectId: string; content?: string | null }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const entries = calls.flatMap((value) => { const call = Call.safeParse(value); return call.success && call.data.result != null ? [call.data] : [] })
  if (content) {
    try { entries.push({ name: String((calls[0] as { name?: unknown } | undefined)?.name ?? 'Tool output'), result: JSON.parse(content) }) } catch { /* Prose remains in the transcript. */ }
  }
  return <div className="mt-3 space-y-3">{entries.map((entry, index) => {
    const parsed = Output.safeParse(entry.result)
    const output: z.infer<typeof Output> = parsed.success ? parsed.data : {}
    const highlighted = entry.name === 'render_structure_view' && output.artifact_id ? Highlighted.safeParse(output.highlighted) : null
    const selection: z.infer<typeof Selection> | undefined = output.viewer_selection ?? (highlighted?.success && highlighted.data.length ? { artifact_id: output.artifact_id!, residues: highlighted.data } : undefined)
    const artifactId = selection?.artifact_id ?? output.artifact_id ?? output.source_artifact_id
    const artifactQuery = new URLSearchParams({ project: projectId })
    if (artifactId) artifactQuery.set('artifact', artifactId)
    if (selection) artifactQuery.set('residues', JSON.stringify(selection.residues))
    return <section key={index} className="space-y-2 border-t border-border-soft pt-3" aria-label={zh ? '工具证据' : 'Tool evidence'}>
      <h4 className="text-sm font-semibold">{entry.name?.replaceAll('_', ' ')}{output.filename ? ` · ${output.filename}` : ''}</h4>
      {output.evidence_kind ? <p className="text-xs text-text-secondary">{output.evidence_kind}</p> : null}
      {output.interpretation ? <p className="text-sm">{output.interpretation}</p> : null}
      {selection ? <p className="break-words text-xs">{selection.residues.map((residue) => `${residue.chain}:${residue.seq}${residue.insertion_code ?? ''} ${residue.name ?? ''}`).join(' · ')}{selection.truncated ? (zh ? ' · 已截断，请缩小筛选范围' : ' · Truncated; narrow the filter') : ''}</p> : null}
      <div className="flex flex-wrap gap-2">
        {artifactId ? <Button size="sm" variant="outline" render={<Link to={`/results?${artifactQuery}`} />}>{selection ? (zh ? '在结果页查看结构与选中残基' : 'Open structure and residues in Results') : (zh ? '在结果页查看源文件' : 'Open source in Results')}</Button> : null}
        {output.candidate_id ? <Button size="sm" variant="outline" render={<Link to={`/candidates?${new URLSearchParams({ project: projectId, candidate: output.candidate_id })}`} />}>{zh ? '打开候选' : 'Open candidate'}</Button> : null}
        {output.experiment_result_id ? <Button size="sm" variant="outline" render={<Link to={`/lab?${new URLSearchParams({ project: projectId, section: 'analysis' })}`} />}>{zh ? '查看保存的分析与质控' : 'Review saved analysis and QC'}</Button> : null}
        {output.knowledge_entry_id ? <Button size="sm" variant="outline" render={<Link to={`/research?${new URLSearchParams({ project: projectId, tab: 'methods', knowledge: output.knowledge_entry_id })}`} />}>{zh ? '打开已保存的讨论报告' : 'Open saved discussion report'}</Button> : null}
      </div>
      {output.knowledge_entry_id && output.status ? <p className="text-xs text-text-secondary">{zh ? '记录状态' : 'Recorded status'}: {output.status.replaceAll('_', ' ')}</p> : null}
      <Disclosure title={zh ? '完整工具结果与来源' : 'Complete tool output and provenance'}><pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(entry.result, null, 2)}</pre></Disclosure>
    </section>
  })}</div>
}
