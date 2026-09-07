import { Dialog, DialogContent, DialogTitle } from '../../components/ui/dialog'
import { Input } from '../../components/ui/Input'
import { Checkbox } from '../../components/ui/checkbox'
import { WorkflowSection, WorkflowSelect, WorkflowOption } from './WorkflowControls'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '../../components/ui/Button'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'
import type { WorkflowEdge } from '../../lib/schemas/workflow'
import {
  gateResults,
  releaseGate,
  retryGate,
  previewGate,
  previewSources,
} from '../../lib/api/workflowGates'
import { emptyPolicy, gateLabel, type GatePolicy, type GateSummary } from './gates'
import { getArtifact } from '../../lib/api/artifacts'
import { StructureViewerLazy } from '../pdb-viewer/StructureViewerLazy'
import { GatePolicyEditor } from './GatePolicyEditor'

export function GateInspector({
  workflowId,
  edge,
  runs,
  readOnly,
  onSave,
  onClose,
  onSource,
  onArtifact,
  onEditMapping,
  onDelete,
}: {
  workflowId: string
  edge: WorkflowEdge
  runs: GateSummary[]
  readOnly: boolean
  onSave: (edge: WorkflowEdge) => Promise<void>
  onClose: () => void
  onSource: () => void
  onArtifact: (id: string) => void
  onEditMapping: () => void
  onDelete: () => Promise<void>
}) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const [policy, setPolicy] = useState<GatePolicy>((edge.gate as GatePolicy) ?? emptyPolicy())
  const [previewArtifactId, setPreviewArtifactId] = useState('')
  const artifactPreview = useQuery({
    queryKey: ['artifact', previewArtifactId],
    queryFn: () => getArtifact(previewArtifactId),
    enabled: !!previewArtifactId,
  })
  const [selectedRun, setSelectedRun] = useState('')
  const gate = runs.find((r) => r.id === selectedRun) ?? runs.find((r) => !r.preview) ?? runs[0]
  const [sourceJob, setSourceJob] = useState('')
  const sources = useQuery({
    queryKey: ['gate-preview-sources', workflowId, edge.id],
    queryFn: () => previewSources(workflowId, edge.id!),
    enabled: !!edge.id,
  })
  const [q, setQ] = useState('')
  const [offset, setOffset] = useState(0)
  const [sort, setSort] = useState('')
  const [descending, setDescending] = useState(true)
  const [selection, setSelection] = useState<Record<string, string[]>>({})
  const selected = gate ? (selection[gate.id] ?? gate.selected_ids ?? []) : []
  const setSelected = (ids: string[]) => gate && setSelection((s) => ({ ...s, [gate.id]: ids }))
  const cache = useQueryClient()
  const toast = useToastStore((s) => s.show)
  const results = useQuery({
    queryKey: [
      'gate-results',
      workflowId,
      gate?.id,
      gate?.version,
      gate?.status,
      q,
      offset,
      sort,
      descending,
    ],
    queryFn: () => gateResults(workflowId, gate!.id, q, offset, sort, descending),
    enabled: !!gate,
  })
  const action = useMutation({
    mutationFn: async (kind: 'save' | 'preview' | 'release' | 'retry') => {
      if (kind === 'save')
        await onSave({
          ...edge,
          gate: {
            ...policy,
            configured: true,
            script_preview_id:
              runs.find(
                (r) =>
                  r.preview &&
                  r.status === 'previewed' &&
                  JSON.stringify({ ...r.policy, configured: true, script_preview_id: null }) ===
                    JSON.stringify({ ...policy, configured: true, script_preview_id: null }),
              )?.id ??
              (gate?.preview && gate.status === 'previewed' ? gate.id : policy.script_preview_id),
          },
        })
      if (kind === 'preview') {
        const row = await previewGate(workflowId, edge.id!, policy, sourceJob || undefined)
        setSelectedRun(row.id)
      }
      if (kind === 'release' && gate) await releaseGate(workflowId, gate, selected)
      if (kind === 'retry' && gate) {
        const row = await retryGate(workflowId, gate.id)
        setSelectedRun(row.id)
        setOffset(0)
      }
    },
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ['workflow-gates', workflowId] })
      await cache.invalidateQueries({ queryKey: ['gate-results', workflowId] })
    },
    onError: (e) => toast(e.message, 'error'),
  })
  const reviewable = gate?.status === 'awaiting_review' && !gate.preview
  return (
    <aside className="h-full overflow-auto rounded-lg border border-border-soft bg-surface-1 p-3 text-sm">
      <div className="flex items-center justify-between">
        <strong>{zh ? '连线与门控' : 'Connection gate'}</strong>
        <Button type="button" size="sm" variant="ghost" onClick={onClose}>
          ×
        </Button>
      </div>
      <p className="my-2 break-words text-xs">
        {edge.source}.{edge.source_port} → {edge.target}.{edge.target_port}
      </p>
      {!readOnly && (
        <div className="flex gap-2">
          <Button type="button" size="sm" variant="outline" onClick={onEditMapping}>
            {zh ? '修改连接端口' : 'Edit connection ports'}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => void onDelete().catch((e) => toast(e.message, 'error'))}
          >
            {zh ? '删除连接' : 'Delete connection'}
          </Button>
        </div>
      )}
      <p className="my-2 text-accent">{gateLabel(edge.gate as GatePolicy, gate, zh)}</p>
      <Button type="button" size="sm" variant="outline" onClick={onSource}>
        {zh ? '上游输出标准（所有出边共用）' : 'Upstream output standard (shared)'}
      </Button>
      <WorkflowSection
        className="my-3"
        title={<> {zh ? '本分支筛选规则' : 'Branch screening policy'} </>}
      >
        <div className="mt-2">
          <GatePolicyEditor value={policy} onChange={setPolicy} disabled={readOnly} />
        </div>
      </WorkflowSection>
      <label className="mb-2 block text-xs">
        {zh ? '试运行数据（同项目、同插件）' : 'Preview data (same project and plugin)'}
        <WorkflowSelect
          className="w-full bg-surface-2 p-2"
          value={sourceJob}
          onChange={(e) => setSourceJob(e.target.value)}
        >
          <WorkflowOption value="">
            {zh ? '当前上游结果' : 'Current upstream results'}
          </WorkflowOption>
          {sources.data?.items.map((r) => (
            <WorkflowOption key={r.id} value={r.id}>
              {r.node_key} · #{r.attempt} · {r.count} · {r.created_at}
            </WorkflowOption>
          ))}
        </WorkflowSelect>
      </label>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          disabled={readOnly || action.isPending}
          onClick={() => action.mutate('save')}
        >
          {zh ? '保存规则' : 'Save rules'}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={action.isPending || (!runs.length && !sourceJob)}
          onClick={() => action.mutate('preview')}
        >
          {zh ? '试运行' : 'Preview'}
        </Button>
      </div>
      {gate?.error && (
        <p role="alert" className="my-2 text-danger">
          {gate.error}
        </p>
      )}
      {gate?.status === 'error' && (
        <Button
          type="button"
          size="sm"
          onClick={() => action.mutate('retry')}
          disabled={action.isPending}
        >
          {zh ? '重试筛选' : 'Retry screening'}
        </Button>
      )}
      <label className="mt-4 block text-xs">
        {zh ? '筛选记录' : 'Evaluation history'}
        <WorkflowSelect
          className="mt-1 w-full bg-surface-2 p-2"
          value={gate?.id ?? ''}
          onChange={(e) => {
            setSelectedRun(e.target.value)
            setOffset(0)
          }}
        >
          <WorkflowOption value="" disabled>
            {zh ? '等待上游结果' : 'Waiting for results'}
          </WorkflowOption>
          {runs.map((r) => (
            <WorkflowOption key={r.id} value={r.id}>
              {r.preview ? 'Preview ' : ''}#{r.revision} · {r.status} · {r.created_at}
            </WorkflowOption>
          ))}
        </WorkflowSelect>
      </label>
      <div className="my-2 grid gap-2">
        <Input
          className="rounded bg-surface-2 p-2 text-xs"
          placeholder={zh ? '搜索序列、名称、淘汰原因' : 'Search sequence, name, rejection reason'}
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setOffset(0)
          }}
        />
        <Input
          className="rounded bg-surface-2 p-2 text-xs"
          placeholder={zh ? '按指标排序' : 'Sort by metric'}
          value={sort}
          onChange={(e) => {
            setSort(e.target.value)
            setOffset(0)
          }}
        />
        <label className="text-xs">
          <Checkbox checked={descending} onCheckedChange={(checked) => setDescending(!!checked)} />{' '}
          {zh ? '降序' : 'Descending'}
        </label>
      </div>
      {results.isError && <p role="alert">{results.error.message}</p>}
      {reviewable && (
        <div className="my-2 flex gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() =>
              setSelected([
                ...new Set([
                  ...selected,
                  ...(results.data?.items.filter((r) => r.passed).map((r) => r.id) ?? []),
                ]),
              ])
            }
          >
            {zh ? '选择本页合格项' : 'Select qualified on page'}
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setSelected([])}>
            {zh ? '清空' : 'Clear'}
          </Button>
        </div>
      )}
      {results.data?.items.map((r) => (
        <div key={r.id} className="my-2 rounded border border-border-soft p-2 text-xs">
          <label className="flex gap-2">
            <Checkbox
              disabled={!reviewable || !r.passed}
              checked={selected.includes(r.id)}
              onCheckedChange={(checked) =>
                setSelected(checked ? [...selected, r.id] : selected.filter((id) => id !== r.id))
              }
            />
            <span className="break-all">{r.key}</span>
            <span className={r.passed ? 'text-success' : 'text-danger'}>
              {r.needs_attention
                ? zh
                  ? '待处理'
                  : 'Needs attention'
                : r.passed
                  ? zh
                    ? '合格'
                    : 'Qualified'
                  : zh
                    ? '淘汰'
                    : 'Rejected'}
            </span>
          </label>
          <p className="mt-1 break-words text-text-secondary">{r.reasons.join(' · ')}</p>
          <WorkflowSection title={<> {zh ? '序列、指标与文件' : 'Sequence, metrics and files'} </>}>
            {r.sequence && <pre className="my-2 whitespace-pre-wrap break-all">{r.sequence}</pre>}
            <dl>
              {Object.entries(r.metrics).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2">
                  <dt className="break-all">{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
            {r.files?.map((f) => (
              <Button
                type="button"
                key={`${f.artifact_id}-${f.port}`}
                size="sm"
                variant="ghost"
                onClick={() => setPreviewArtifactId(f.artifact_id)}
              >
                {zh ? '预览文件' : 'Preview file'} · {f.port}
              </Button>
            ))}
          </WorkflowSection>
        </div>
      ))}
      {results.data && (
        <div className="flex items-center justify-between text-xs">
          <Button
            type="button"
            size="sm"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 100))}
          >
            ←
          </Button>
          <span>
            {results.data.total ? offset + 1 : 0}–{Math.min(offset + 100, results.data.total)} /{' '}
            {results.data.total}
          </span>
          <Button
            type="button"
            size="sm"
            disabled={offset + 100 >= results.data.total}
            onClick={() => setOffset(offset + 100)}
          >
            →
          </Button>
        </div>
      )}
      {previewArtifactId && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open) setPreviewArtifactId('')
          }}
        >
          <DialogContent className="max-h-[90vh] overflow-auto sm:max-w-[85vw]">
            <DialogTitle>
              {artifactPreview.data?.filename ?? (zh ? '文件预览' : 'File preview')}
            </DialogTitle>
            {artifactPreview.isError && <p role="alert">{artifactPreview.error.message}</p>}
            {artifactPreview.data && (
              <>
                {/\.(pdb|cif|mmcif)$/i.test(artifactPreview.data.filename) ? (
                  <StructureViewerLazy
                    height="65vh"
                    source={{
                      artifactId: artifactPreview.data.id,
                      url: artifactPreview.data.download_url,
                      format: artifactPreview.data.filename.endsWith('.pdb') ? 'pdb' : 'mmcif',
                    }}
                  />
                ) : (
                  <Button type="button" onClick={() => onArtifact(previewArtifactId)}>
                    {zh ? '查看文件详情' : 'View file details'}
                  </Button>
                )}
              </>
            )}
          </DialogContent>
        </Dialog>
      )}
      {reviewable && (
        <Button
          type="button"
          className="mt-3 w-full"
          disabled={action.isPending}
          onClick={() => action.mutate('release')}
        >
          {selected.length
            ? `${zh ? '放行所选' : 'Release selected'} (${selected.length})`
            : zh
              ? '不保留结果，结束分支'
              : 'Keep none and end branch'}
        </Button>
      )}
    </aside>
  )
}
