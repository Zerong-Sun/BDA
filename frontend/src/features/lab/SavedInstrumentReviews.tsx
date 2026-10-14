import { useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Button } from '../../components/ui/Button'
import { Disclosure } from '../../components/ui/Disclosure'
import { listSavedInstrumentAnalyses } from '../../lib/api/wetlab'
import { useI18n } from '../../lib/i18n'
import { InstrumentQuality } from './InstrumentQuality'
import { AnalysisResult } from './InstrumentResult'
import { AnalysisProvenance } from './AnalysisProvenance'
import type { InstrumentAnalysisData } from '../../lib/schemas/instrumentAnalysis'

type SavedAnalysis = Awaited<ReturnType<typeof listSavedInstrumentAnalyses>>['items'][number]

function SavedAnalysisTitle({ item }: { item: SavedAnalysis }) {
  const { language } = useI18n()
  const copy = (cn: string, en: string) => language === 'zh' ? cn : en
  const status = String(item.record.qc_review?.status ?? 'unreviewed')
  const id = item.record.experiment_result_id.slice(0, 8)
  if (item.analysis?.instrument !== 'bli') return <>{item.label} · {status} · {id}</>
  const { summary } = item.analysis
  const processing = summary.processing ?? {}
  const method = processing.analysis_method ?? summary.selected_method
  const instrumentMethod = method === 'instrument_kobs'
  const methodLabel = method === 'measured_global' ? copy('实测曲线全局拟合', 'Measured global fit')
    : instrumentMethod ? copy('仪器 Kobs 回归', 'Instrument Kobs regression')
      : typeof method === 'string' ? method : copy('方法未记录', 'Method not recorded')
  const baselineMode = processing.baseline ?? processing.baseline_mode
  const baseline = instrumentMethod ? copy('基线：不适用', 'Baseline: not applied')
    : baselineMode === 'initial_point' ? copy('基线：初始点', 'Baseline: initial point')
      : baselineMode === 'fitted_offset' ? copy('基线：拟合偏移', 'Baseline: fitted offset')
        : typeof baselineMode === 'string' ? `${copy('基线', 'Baseline')}: ${baselineMode}` : copy('基线未记录', 'Baseline not recorded')
  const referenceLabel = processing.reference_label
  const reference = instrumentMethod || processing.reference_applied === false || referenceLabel === null
    ? copy('未扣除参比', 'No reference subtraction')
    : typeof referenceLabel === 'string' && referenceLabel ? `${copy('扣除参比', 'Reference-subtracted')}: ${referenceLabel}`
      : copy('参比设置未记录', 'Reference not recorded')
  const kd = item.record.value == null ? '—' : new Intl.NumberFormat(language, { maximumSignificantDigits: 3 }).format(item.record.value)
  return <span className="min-w-0 space-y-1 text-left">
    <span className="block font-medium">{summary.sample_id} · KD {kd} {item.record.unit ?? 'nM'} · {status}</span>{' '}
    <span className="block text-xs font-normal text-text-secondary">{methodLabel} · {baseline} · {reference}</span>{' '}
    <span className="block break-all text-xs font-normal text-text-muted">{item.label} · {item.record.analysis_version} · {id}</span>
  </span>
}

export function SavedInstrumentReviews({ projectId, onReanalyse, autoLoad = false }: { projectId: string; autoLoad?: boolean; onReanalyse?: (analysis: InstrumentAnalysisData, label: string) => void }) {
  const { language } = useI18n()
  const copy = (cn: string, en: string) => language === 'zh' ? cn : en
  const [items, setItems] = useState<Awaited<ReturnType<typeof listSavedInstrumentAnalyses>>['items']>([])
  const [cursor, setCursor] = useState<string | null | undefined>(undefined)
  const [loaded, setLoaded] = useState(false)
  const load = useMutation({
    mutationFn: (restart: boolean) => listSavedInstrumentAnalyses(projectId, restart ? undefined : cursor ?? undefined),
    onSuccess: (data, restart) => {
      setItems((current) => restart ? data.items : [...current, ...data.items.filter((next) => !current.some((item) => item.record.experiment_result_id === next.record.experiment_result_id))])
      setCursor(data.next_cursor); setLoaded(true)
    },
  })
  const requested = useRef(false)
  const { mutate } = load
  useEffect(() => {
    if (autoLoad && !requested.current) { requested.current = true; mutate(true) }
  }, [autoLoad, mutate])
  return <section className="space-y-3">
    <h3 className="text-sm font-medium">{copy('已保存的仪器结果与审阅', 'Saved instrument results and reviews')}</h3>
    {!loaded || cursor ? <Button type="button" variant="outline" disabled={load.isPending} onClick={() => load.mutate(false)}>{loaded ? copy('继续读取实验记录', 'Load more experiment records') : copy('读取已保存结果', 'Load saved results')}</Button> : null}
    {loaded && <Button type="button" variant="outline" disabled={load.isPending} onClick={() => load.mutate(true)}>{copy('刷新结果和审阅状态', 'Refresh results and reviews')}</Button>}
    {load.error && <p role="alert" className="text-sm text-destructive">{load.error instanceof Error ? load.error.message : String(load.error)}</p>}
    {loaded && !items.length && <p className="text-sm text-text-secondary">{cursor ? copy('已读页面中没有仪器分析，可继续读取。', 'No instrument analyses on the loaded pages; continue loading.') : copy('当前项目没有已保存的仪器分析。', 'No saved instrument analyses in this project.')}</p>}
    {items.map((item) => <Disclosure key={item.record.experiment_result_id} title={<SavedAnalysisTitle item={item} />}>
      <p className="mb-2 text-sm">{item.record.experiment_type} · {item.record.value ?? '—'} {item.record.unit} · {item.record.analysis_version}</p>
      {item.analysis ? <AnalysisResult projectId={projectId} analysed={{ ...item.analysis, record: item.record }} onReviewed={(record) => setItems((current) => current.map((saved) => saved.record.experiment_result_id === record.experiment_result_id ? { ...saved, record: { ...record, version: record.version ?? saved.record.version, qc_review: record.qc_review ?? null } } : saved))} /> : <>
        <AnalysisProvenance record={item.record} summary={{}} />
        {item.summaryError ? <p role="status" className="my-2 text-sm text-text-secondary">{item.summaryError}</p> : null}
        <InstrumentQuality projectId={projectId} quality={item.quality} record={item.record} onReviewed={(record) => setItems((current) => current.map((saved) => saved.record.experiment_result_id === record.experiment_result_id ? { ...saved, record: { ...record, version: record.version ?? saved.record.version, qc_review: record.qc_review ?? null } } : saved))} />
      </>}
      {item.analysis && onReanalyse ? <Button type="button" className="mt-3" variant="outline" onClick={() => onReanalyse(item.analysis!, item.label)}>{copy('修改参数并创建新版本', 'Edit parameters and create a new version')}</Button> : null}
    </Disclosure>)}
  </section>
}
