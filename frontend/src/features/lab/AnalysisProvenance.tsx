import { useState } from 'react'
import { downloadArtifact, getArtifact } from '../../lib/api/artifacts'
import type { AnalysisRecord } from '../../lib/api/wetlab'
import { useI18n } from '../../lib/i18n'
import { Button } from '../../components/ui/Button'
import { Disclosure } from '../../components/ui/Disclosure'

export function AnalysisProvenance({ record, summary }: { record: AnalysisRecord; summary: { source_format?: string; evidence_kind?: string; source_checksum_sha256?: string; processing?: Record<string, unknown>; uncertainty?: unknown; selected_method?: string; supersedes_result_id?: string | null } }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const [error, setError] = useState('')
  const source = record.source_artifact_id
  return <div className="space-y-2 rounded border border-border-soft p-3 text-sm">
    <dl className="grid gap-2 sm:grid-cols-2">
      <div><dt className="text-text-secondary">{zh ? '证据类型' : 'Evidence type'}</dt><dd>{summary.evidence_kind ?? (zh ? '未记录' : 'Not recorded')}</dd></div>
      <div><dt className="text-text-secondary">{zh ? '分析方法' : 'Analysis method'}</dt><dd>{summary.selected_method ?? record.analysis_version}</dd></div>
      <div><dt className="text-text-secondary">{zh ? '源文件格式' : 'Source format'}</dt><dd>{summary.source_format ?? '—'}</dd></div>
      <div><dt className="text-text-secondary">{zh ? '原始文件' : 'Raw source'}</dt><dd className="break-all font-mono text-xs">{source || (zh ? '未保存预览' : 'Unsaved preview')}</dd></div>
    </dl>
    {source ? <Button type="button" variant="outline" size="sm" onClick={() => { setError(''); void getArtifact(source).then(downloadArtifact).catch((err: unknown) => setError(err instanceof Error ? err.message : String(err))) }}>{zh ? '下载原始文件' : 'Download raw source'}</Button> : null}
    {summary.source_checksum_sha256 ? <p className="break-all font-mono text-xs">SHA-256: {summary.source_checksum_sha256}</p> : null}
    {summary.supersedes_result_id ? <p className="break-all text-xs">{zh ? '替代分析记录' : 'Supersedes analysis'}: {summary.supersedes_result_id}</p> : null}
    {summary.processing ? <Disclosure title={zh ? '处理参数与版本来源' : 'Processing parameters and lineage'}><pre className="max-h-72 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(summary.processing, null, 2)}</pre></Disclosure> : null}
    {summary.uncertainty != null ? <Disclosure title={zh ? '不确定性与拟合限制' : 'Uncertainty and fit limitations'}><pre className="max-h-48 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(summary.uncertainty, null, 2)}</pre></Disclosure> : <p className="text-xs text-text-secondary">{zh ? '未提供置信区间；数值显示精度不代表测量精度。' : 'No confidence interval supplied; displayed precision does not establish measurement precision.'}</p>}
    {error ? <p role="alert" className="text-destructive">{error}</p> : null}
  </div>
}
