import { useQuery } from '@tanstack/react-query'
import { getCandidate } from '../../lib/api/candidates'
import { Link } from 'react-router'
import type { WorkflowNode } from '../../lib/schemas/workflow'
import type { Artifact } from '../../lib/schemas/artifact'
import { downloadArtifact, getArtifact } from '../../lib/api/artifacts'
import { Button } from '../../components/ui/Button'
import { useToastStore } from '../../components/ui/toastStore'

const text = (v: unknown) => v == null ? '—' : typeof v === 'number' ? (Number.isFinite(v) ? Number(v.toFixed(3)).toString() : '—') : String(v)
function EvidenceCandidateLink({ id, label, projectId }: { id: string; label: string; projectId: string }) {
  const query = useQuery({ queryKey: ['candidate', id], queryFn: () => getCandidate(id), staleTime: 60_000 })
  if (!query.data) return <strong>{label}{query.isError ? '（关联候选暂不可用）' : ''}</strong>
  const actualProject = query.data.project_id
  const params = new URLSearchParams({ project: actualProject, candidate: id })
  // Preserve explicit access to historical projects after consolidation.
  if (actualProject !== projectId) params.set('history', actualProject)
  return <Link className="break-all text-primary underline" to={`/candidates?${params}`}>{label}</Link>
}

export function WorkflowEvidence({ nodes, artifacts, projectId, onSelect, expanded = false }: {
  nodes: WorkflowNode[]; artifacts: Artifact[]; projectId: string; onSelect?: (id: string) => void; expanded?: boolean
}) {
  const show = useToastStore((s) => s.show)
  const evidence = nodes.filter((n) => typeof n.parameters.evidence_summary === 'string')
  if (!evidence.length) return null
  return <section className="mb-4 rounded-lg border border-border-soft bg-surface-1 p-4">
    <h2 className="mb-2 font-semibold">已有数据与实验记录</h2>
    {!expanded && <p className="mb-3 text-sm text-text-secondary">这是可编辑的数据整理草稿，点击节点查看数值和文件。已有结果无需重新运行；实验记录与计算预测分开关联。</p>}
    <div className={expanded ? 'space-y-4' : 'grid gap-3 md:grid-cols-2 xl:grid-cols-3'}>
      {evidence.map((node) => {
        const records = (Array.isArray(node.parameters.evidence_records) ? node.parameters.evidence_records : []).filter((r): r is Record<string, unknown> => !!r && typeof r === 'object')
        const ids = Array.isArray(node.parameters.evidence_artifact_ids) ? node.parameters.evidence_artifact_ids : []
        const files = artifacts.filter((a) => ids.includes(a.id))
        return <article key={node.id} className="min-w-0 rounded-md border border-border-soft p-3">
          <Button type="button" variant="ghost" className="h-auto whitespace-normal p-0 text-left" onClick={() => onSelect?.(node.id)}>{text(node.parameters.display_name ?? node.node_key)}</Button>
          <p className="my-2 text-xs text-text-secondary">{text(node.parameters.evidence_summary)}</p>
          <p className="text-xs">{records.length} 条记录 · {files.length} 个文件</p>
          {expanded && <>
            <div className="mt-3 space-y-2">{records.map((r, i) => <div className="rounded bg-surface-2 p-2 text-xs" key={text(r.record_id ?? r.label ?? i)}>
              {r.candidate_id ? <EvidenceCandidateLink id={String(r.candidate_id)} label={text(r.label)} projectId={projectId} /> : <strong>{text(r.label)}</strong>}
              <dl className="mt-1 space-y-1">{Object.entries(r.values && typeof r.values === 'object' ? r.values : {}).map(([key, value]) => <div className="flex justify-between gap-2" key={key}><dt>{key}</dt><dd className="break-words text-right">{text(value)}</dd></div>)}</dl>
            </div>)}</div>
            <div className="mt-3 flex flex-wrap gap-2">{files.map((a) => <Button type="button" key={a.id} size="xs" variant="outline" className="h-auto max-w-full whitespace-normal break-all" onClick={async () => { try { await downloadArtifact(await getArtifact(a.id)) } catch { show('文件下载失败，请重试', 'error') } }}>{a.filename}</Button>)}</div>
          </>}
        </article>
      })}
    </div>
  </section>
}
