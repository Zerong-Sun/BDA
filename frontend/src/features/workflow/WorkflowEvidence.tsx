import { useQuery } from '@tanstack/react-query'
import { getCandidate } from '../../lib/api/candidates'
import { Link } from 'react-router'
import type { WorkflowNode } from '../../lib/schemas/workflow'
import type { Artifact } from '../../lib/schemas/artifact'
import { downloadArtifact, getArtifact } from '../../lib/api/artifacts'
import { Button } from '../../components/ui/Button'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'

const text = (v: unknown) => v == null ? '—' : typeof v === 'number' ? (Number.isFinite(v) ? Number(v.toFixed(3)).toString() : '—') : String(v)
function EvidenceCandidateLink({ id, label, projectId }: { id: string; label: string; projectId: string }) {
  const { language } = useI18n()
  const query = useQuery({ queryKey: ['candidate', id], queryFn: () => getCandidate(id), staleTime: 60_000 })
  if (!query.data) return <strong>{label}{query.isError ? (language === 'zh' ? '（关联候选暂不可用）' : ' (linked candidate unavailable)') : ''}</strong>
  const actualProject = query.data.project_id
  const params = new URLSearchParams({ project: actualProject, candidate: id })
  // Preserve explicit access to historical projects after consolidation.
  if (actualProject !== projectId) params.set('history', actualProject)
  return <Link className="break-all text-primary underline" to={`/candidates?${params}`}>{label}</Link>
}

export function WorkflowEvidence({ nodes, artifacts, projectId, onSelect, expanded = false }: {
  nodes: WorkflowNode[]; artifacts: Artifact[]; projectId: string; onSelect?: (id: string) => void; expanded?: boolean
}) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const show = useToastStore((s) => s.show)
  const evidence = nodes.filter((n) => typeof n.parameters.evidence_summary === 'string')
  if (!evidence.length) return null
  return <section className="mb-4 rounded-lg border border-border-soft bg-surface-1 p-4">
    <h2 className="mb-2 font-semibold">{zh ? '已有数据与实验记录' : 'Saved data and experiment records'}</h2>
    {!expanded && <p className="mb-3 text-sm text-text-secondary">{zh ? '点击节点查看已有数值和文件。实验记录与计算预测分别关联；无需重新运行已有结果。' : 'Select a node to inspect saved values and files. Experiment records and predictions are linked separately; saved results do not need another run.'}</p>}
    <div className={expanded ? 'space-y-4' : 'grid gap-3 md:grid-cols-2 xl:grid-cols-3'}>
      {evidence.map((node) => {
        const records = (Array.isArray(node.parameters.evidence_records) ? node.parameters.evidence_records : []).filter((r): r is Record<string, unknown> => !!r && typeof r === 'object')
        const ids = Array.isArray(node.parameters.evidence_artifact_ids) ? node.parameters.evidence_artifact_ids : []
        const files = artifacts.filter((a) => ids.includes(a.id))
        return <article key={node.id} className="min-w-0 rounded-md border border-border-soft p-3">
          <Button type="button" variant="ghost" className="h-auto whitespace-normal p-0 text-left" onClick={() => onSelect?.(node.id)}>{text(node.parameters.display_name ?? node.node_key)}</Button>
          <p className="my-2 text-xs text-text-secondary">{text(node.parameters.evidence_summary)}</p>
          <p className="text-xs">{zh ? `${records.length} 条记录 · ${files.length} 个文件` : `${records.length} record${records.length === 1 ? '' : 's'} · ${files.length} file${files.length === 1 ? '' : 's'}`}</p>
          {expanded && <>
            <div className="mt-3 space-y-2">{records.map((r, i) => <div className="rounded bg-surface-2 p-2 text-xs" key={text(r.record_id ?? r.label ?? i)}>
              {r.candidate_id ? <EvidenceCandidateLink id={String(r.candidate_id)} label={text(r.label)} projectId={projectId} /> : <strong>{text(r.label)}</strong>}
              <dl className="mt-1 space-y-1">{Object.entries(r.values && typeof r.values === 'object' ? r.values : {}).map(([key, value]) => <div className="flex justify-between gap-2" key={key}><dt>{key}</dt><dd className="break-words text-right">{text(value)}</dd></div>)}</dl>
            </div>)}</div>
            <div className="mt-3 flex flex-wrap gap-2">{files.map((a) => <Button type="button" key={a.id} size="xs" variant="outline" className="h-auto max-w-full whitespace-normal break-all" onClick={async () => { try { await downloadArtifact(await getArtifact(a.id)) } catch { show(zh ? '文件下载失败，请重试' : 'File download failed. Please retry.', 'error') } }}>{a.filename}</Button>)}</div>
          </>}
        </article>
      })}
    </div>
  </section>
}
