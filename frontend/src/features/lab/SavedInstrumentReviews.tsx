import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Button } from '../../components/ui/Button'
import { Disclosure } from '../../components/ui/Disclosure'
import { listSavedInstrumentAnalyses } from '../../lib/api/wetlab'
import { useI18n } from '../../lib/i18n'
import { InstrumentQuality } from './InstrumentQuality'

export function SavedInstrumentReviews({ projectId }: { projectId: string }) {
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
  return <section className="space-y-3">
    <h3 className="text-sm font-medium">{copy('已保存的仪器结果与审阅', 'Saved instrument results and reviews')}</h3>
    {!loaded || cursor ? <Button type="button" variant="outline" disabled={load.isPending} onClick={() => load.mutate(false)}>{loaded ? copy('继续读取实验记录', 'Load more experiment records') : copy('读取已保存结果', 'Load saved results')}</Button> : null}
    {loaded && <Button type="button" variant="outline" disabled={load.isPending} onClick={() => load.mutate(true)}>{copy('刷新结果和审阅状态', 'Refresh results and reviews')}</Button>}
    {load.error && <p role="alert" className="text-sm text-destructive">{load.error instanceof Error ? load.error.message : String(load.error)}</p>}
    {loaded && !items.length && <p className="text-sm text-text-secondary">{cursor ? copy('已读页面中没有仪器分析，可继续读取。', 'No instrument analyses on the loaded pages; continue loading.') : copy('当前项目没有已保存的仪器分析。', 'No saved instrument analyses in this project.')}</p>}
    {items.map((item) => <Disclosure key={item.record.experiment_result_id} title={`${item.label} · ${String(item.record.qc_review?.status ?? 'unreviewed')} · ${item.record.experiment_result_id.slice(0, 8)}`}>
      <p className="mb-2 text-sm">{item.record.experiment_type} · {item.record.value ?? '—'} {item.record.unit} · {item.record.analysis_version}</p>
      <InstrumentQuality projectId={projectId} quality={item.quality} record={item.record} onReviewed={(record) => setItems((current) => current.map((saved) => saved.record.experiment_result_id === record.experiment_result_id ? { ...saved, record: { ...record, version: record.version ?? saved.record.version, qc_review: record.qc_review ?? null } } : saved))} />
    </Disclosure>)}
  </section>
}
