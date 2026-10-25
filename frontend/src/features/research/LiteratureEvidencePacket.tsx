import type { ReactNode } from 'react'
import { getCoreRowModel, useReactTable } from '@tanstack/react-table'
import { DataGrid } from '../../components/reui/data-grid/data-grid'
import { DataGridTableBase } from '../../components/reui/data-grid/data-grid-table'
import { Disclosure } from '../../components/ui/Disclosure'
import { useQuery } from '@tanstack/react-query'
import { getArtifact } from '../../lib/api/artifacts'
import { Button } from '../../components/ui/Button'
import { useI18n } from '../../lib/i18n'
import { jsonArray, jsonRecord, text } from './jsonHelpers'
import { safeCitationUrl } from './citationMarkers'

const rows = (value: unknown) => jsonArray(value).map(jsonRecord)
const show = (value: unknown) => value == null || value === '' ? '—' : typeof value === 'string' ? value : JSON.stringify(value)

// Extracted source tables can contain merged cells. Use the registry table
// surface with the original semantic cells rather than flattening their spans.
const layoutColumns: [] = []
const layoutRows: [] = []
function EvidenceTable({ children }: { children: ReactNode }) {
  // The table is a layout provider here; no table callbacks escape this component.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({ data: layoutRows, columns: layoutColumns, getCoreRowModel: getCoreRowModel() })
  return <DataGrid table={table} recordCount={0} tableLayout={{ width: 'auto', dense: true }} tableClassNames={{ base: 'text-left text-xs' }}><DataGridTableBase>{children}</DataGridTableBase></DataGrid>
}

function ArchivePart({ item, projectId }: { item: Record<string, unknown>; projectId: string }) {
  const id = text(item.artifact_id)
  const query = useQuery({ queryKey: ['literature-evidence-archive', projectId, id], queryFn: () => getArtifact(id), enabled: Boolean(id), retry: false })
  const url = query.data?.project_id === projectId ? safeCitationUrl(query.data.download_url) : undefined
  return url ? <a className="text-accent underline" href={url} target="_blank" rel="noopener noreferrer">{show(item.part)} / {show(item.total_parts)} · {show(item.filename)}</a> : <span className="text-text-muted">{show(item.filename)} · {query.isError ? '链接读取失败 / Link unavailable' : '正在读取 / Loading'}</span>
}

/** Source extraction and scientific interpretation keep separate review states. */
export function LiteratureEvidencePacket({ projectId, documentId, metadata }: { projectId: string; documentId: string; metadata: Record<string, unknown> }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const packet = jsonRecord(metadata.evidence_packet)
  const matches = (!packet.project_id || packet.project_id === projectId) && (!packet.document_id || packet.document_id === documentId)
  const curated = Boolean(metadata.evidence_curation)
  const archiveId = text(packet.archive_artifact_id)
  const archive = useQuery({ queryKey: ['literature-evidence-archive', projectId, archiveId], queryFn: () => getArtifact(archiveId), enabled: matches && Boolean(archiveId), retry: false })
  if (!matches) return <p role="alert">{zh ? '证据包归属不匹配，已停止显示。' : 'Evidence packet attribution does not match this paper.'}</p>
  if (!packet.schema) return <p className="text-xs text-text-muted">{zh ? '尚未提取图表与数据证据包。' : 'Figures and data have not yet been extracted.'}</p>
  const analysis = curated ? {} : jsonRecord(packet.analysis)
  const figures = rows(packet.figures), tables = rows(packet.tables), values = rows(packet.data)
  const argumentsList = curated ? [] : [...rows(packet.arguments), ...rows(analysis.arguments)]
  const passages = rows(packet.passages)
  const sourceUrl = safeCitationUrl(packet.source_url)
  const archiveUrl = archive.data?.project_id === projectId ? safeCitationUrl(archive.data.download_url) : undefined
  const gaps = [...new Set([...jsonArray(packet.gaps), ...jsonArray(analysis.gaps)].map(show))]
  const source = (id: unknown) => {
    const table = tables.find((t) => t.id === id)
    return passages.find((p) => p.id === id)?.text ?? figures.find((f) => f.id === id)?.caption ?? (table
      ? [text(table.caption), ...jsonArray(table.rows).map((row) => rows(row).map((cell) => text(cell.text)).join(' ')), text(table.footnotes)].filter(Boolean).join(' ')
      : undefined)
  }
  const exportPacket = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(packet, null, 2)], { type: 'application/json' }))
    const a = document.createElement('a'); a.href = url; a.download = `literature-evidence-${documentId}.json`; a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return <section className="grid gap-3 rounded border border-border-soft p-4 text-sm" aria-label={zh ? '文献证据包' : 'Paper evidence packet'}>
    <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-semibold">{zh ? '论点 · 论据 · 图片 · 数据' : 'Arguments · Evidence · Figures · Data'}</h4><Button type="button" size="xs" variant="outline" onClick={exportPacket}>{zh ? '导出证据包' : 'Export evidence packet'}</Button></div>
    <p className="text-xs text-text-muted">{zh ? '提取及模型分析草稿，待复核。图片已下载不代表已目视审查；图中数值未自动估读。' : 'Extraction and model analysis are drafts for review. Downloaded figures are not necessarily visually reviewed; plot values are not estimated.'}</p>
    <p className="text-xs">{show(packet.content_kind)} · {figures.length} {zh ? '图项' : 'figures'} · {tables.length} {zh ? '表' : 'tables'} · {values.length} {zh ? '有原文定位的数值' : 'anchored values'}</p>
    {metadata.latest_evidence_packet ? <p className="text-warning">{zh ? '已发现新的来源版本；本证据包保留原有定位，需另行比较。' : 'A newer source snapshot exists; this packet preserves the earlier anchors.'}</p> : null}
    {sourceUrl ? <a className="text-accent underline" href={sourceUrl} target="_blank" rel="noopener noreferrer">{zh ? '原始来源与许可' : 'Original source and license'}</a> : null}
    {rows(packet.archive_artifacts).length > 1 ? <div className="grid gap-1 text-xs"><p>{zh ? '下载本项目全部文献包分卷，解压到同一目录后打开 report.html：' : 'Download every part into the same folder, extract, then open report.html:'}</p>{rows(packet.archive_artifacts).map((part) => <ArchivePart key={text(part.artifact_id)} item={part} projectId={projectId} />)}</div> : archiveUrl ? <a className="text-accent underline" href={archiveUrl} target="_blank" rel="noopener noreferrer">{zh ? '项目历史文献归档（含旧报告及旁支资料）' : 'Historical project archive (earlier reports and related reading)'}</a> : null}
    {analysis.project_relevance ? <p>{show(analysis.project_relevance)}</p> : null}
    {analysis.paper_claim ? <p><strong>{zh ? '论文论点：' : 'Paper claim: '}</strong>{show(analysis.paper_claim)}</p> : null}
    {argumentsList.length ? <Disclosure title={`${zh ? '项目论点及支持、反驳和适用条件' : 'Project arguments, support, contradictions and conditions'} (${argumentsList.length})`}>
      <div className="grid gap-3 pt-2">{argumentsList.map((a, i) => <article key={i} className="space-y-2 border-l-2 pl-3"><h5 className="font-medium">{show(a.project_argument)}</h5><p>{show(a.paper_claim)}</p><p>{show(a.relation)} · {show(a.interpretation)}</p><p className="text-text-muted">{show(a.limitations)}</p>{jsonArray(a.source_ids).map((id, n) => <Disclosure key={n} title={`${zh ? '原文定位' : 'Source'}: ${show(id)}`}><blockquote className="whitespace-pre-wrap">{show(source(id))}</blockquote></Disclosure>)}</article>)}</div>
    </Disclosure> : null}
    <Disclosure title={`${zh ? '定量数据、实验条件与原文' : 'Quantitative data, conditions and sources'} (${values.length})`}>
      {!values.length ? <p className="pt-2">{zh ? '尚无通过原文数值定位的提取结果；不等于论文没有数据。' : 'No values with exact source anchors are saved; this does not mean the paper contains no data.'}</p> : <div className="overflow-x-auto pt-2"><EvidenceTable><thead><tr>{(zh ? ['指标', '数值 / 单位', '条件与对照', 'n / 误差', '原文定位'] : ['Measure', 'Value / unit', 'Conditions / control', 'n / uncertainty', 'Source']).map((h) => <th key={h} className="border p-2">{h}</th>)}</tr></thead><tbody>{values.map((v, i) => <tr key={i}><td className="border p-2">{show(v.measure)}{!curated ? <p>{show(v.interpretation)}</p> : null}</td><td className="border p-2">{show(v.value)} {show(v.unit)}</td><td className="border p-2">{show(v.condition)}<p>{show(v.comparator)}</p></td><td className="border p-2">{show(v.n)} / {show(v.uncertainty)}</td><td className="border p-2"><Disclosure title={show(v.source_id)}><blockquote>{show(v.source_quote)}</blockquote></Disclosure></td></tr>)}</tbody></EvidenceTable></div>}
    </Disclosure>
    <Disclosure title={`${zh ? '原始图片和图注' : 'Original figures and captions'} (${figures.length})`}>
      <div className="grid gap-4 pt-2">{figures.map((f, i) => <article key={i} className="space-y-2"><h5 className="font-medium">{show(f.label || f.id)}</h5>{rows(f.assets).map((asset, n) => {
        const url = safeCitationUrl(asset.url)
        return url ? <div key={n}>{/\.(png|jpe?g|gif|webp)(\?|$)/i.test(url) ? <img loading="lazy" className="max-h-[45rem] max-w-full object-contain" src={url} alt={`${show(f.label)} — ${show(packet.library_title)}`} /> : null}<a href={url} className="text-accent underline" target="_blank" rel="noopener noreferrer">{zh ? '打开原始图文件' : 'Open original figure'}</a></div> : <p key={n} className="text-warning">{zh ? '图片地址待补齐：' : 'Image URL unresolved: '}{show(asset.reference)}</p>
      })}<p className="whitespace-pre-wrap text-xs">{show(f.caption)}</p>{rows(analysis.figure_notes).filter((n) => n.id === f.id).map((n, j) => <p key={j}>{show(n.panels)} · {show(n.use)}<br />{show(n.limits)}</p>)}<p className="text-xs text-text-muted">{show(packet.license_code)} · {show(f.visual_review_status)}</p></article>)}</div>
    </Disclosure>
    <Disclosure title={`${zh ? '原始表格（保留表头和脚注）' : 'Original tables with headers and footnotes'} (${tables.length})`}>
      {tables.map((t, i) => <div key={i} className="overflow-x-auto py-3"><h5 className="font-medium">{show(t.label || t.id)} · {show(t.caption)}</h5><EvidenceTable><tbody>{jsonArray(t.rows).map((row, j) => <tr key={j}>{rows(row).map((cell, k) => {
        const Cell = cell.header ? 'th' : 'td'
        return <Cell key={k} className="border p-2" rowSpan={Math.max(1, Number(cell.rowspan) || 1)} colSpan={Math.max(1, Number(cell.colspan) || 1)}>{show(cell.text)}</Cell>
      })}</tr>)}</tbody></EvidenceTable><p>{show(t.footnotes)}</p></div>)}
    </Disclosure>
    <Disclosure title={`${zh ? '补充材料' : 'Supplementary materials'} (${rows(packet.supplements).length})`}>
      {rows(packet.supplements).map((s, i) => <div key={i} className="space-y-1 py-2"><p>{show(s.label || s.id)} · {show(s.content_status)}</p><p className="text-xs">{show(s.description)}</p>{rows(s.assets).map((a, j) => {
        const url = safeCitationUrl(a.url)
        return url ? <a key={j} className="mr-3 text-accent underline" href={url} target="_blank" rel="noopener noreferrer">{show(a.reference)}</a> : null
      })}</div>)}
    </Disclosure>
    {gaps.length ? <Disclosure title={`${zh ? '尚缺的证据与限制' : 'Evidence gaps and limitations'} (${gaps.length})`}><ul className="list-disc space-y-1 pl-5 pt-2">{gaps.map((gap) => <li key={gap}>{gap}</li>)}</ul></Disclosure> : null}
  </section>
}
