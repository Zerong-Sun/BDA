import { useEffect, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../components/ui/accordion'
import { Disclosure } from '../../components/ui/Disclosure'
import { Button } from '../../components/ui/Button'
import { getArtifact } from '../../lib/api/artifacts'
import { listSavedLiteratureChunks, listSavedLiteratureTraces } from '../../lib/api/literatureSources'
import { useI18n } from '../../lib/i18n'
import { jsonRecord, text } from './jsonHelpers'
import { CitationDetails } from './CitationDetails'
import { citationValueLabel, safeCitationUrl } from './citationMarkers'

/** On-demand inspection of stored evidence, never a new remote literature search. */
export function LiteratureSourceDetails({ projectId, documentId, metadata, abstract }: {
  projectId: string; documentId: string; metadata: Record<string, unknown>; abstract?: string
}) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const [open, setOpen] = useState(false)
  const provenance = jsonRecord(metadata.content_provenance)
  const latest = jsonRecord(metadata.latest_retrieval_provenance)
  const changed = Boolean(latest.content_checksum_sha256 && latest.content_checksum_sha256 !== provenance.content_checksum_sha256)
  const chunks = useInfiniteQuery({
    queryKey: ['literature-source-chunks', projectId, documentId],
    queryFn: ({ pageParam }) => listSavedLiteratureChunks(documentId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: open && Boolean(projectId && documentId), retry: false,
  })
  const traces = useInfiniteQuery({
    queryKey: ['literature-source-traces', projectId, documentId],
    queryFn: ({ pageParam }) => listSavedLiteratureTraces(documentId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: open && Boolean(projectId && documentId), retry: false,
  })
  // The API cursor orders UUIDs, not paragraph positions. Finish the bounded
  // document pagination before presenting a continuous source-order sequence.
  const { hasNextPage, isFetchingNextPage, isFetchNextPageError, fetchNextPage } = chunks
  useEffect(() => {
    if (open && hasNextPage && !isFetchingNextPage && !isFetchNextPageError) void fetchNextPage()
  }, [open, hasNextPage, isFetchingNextPage, isFetchNextPageError, fetchNextPage])
  const artifactId = text(provenance.raw_content_artifact_id)
  const artifact = useQuery({
    queryKey: ['literature-source-artifact', projectId, artifactId], queryFn: () => getArtifact(artifactId),
    enabled: open && Boolean(projectId && artifactId), retry: false,
  })
  const savedChunks = (chunks.data?.pages.flatMap((page) => page.items) ?? []).sort((a, b) => a.position - b.position)
  const savedTraces = (traces.data?.pages.flatMap((page) => page.items) ?? []).sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id))
  const sourceLabels: Record<string, string> = { europe_pmc: 'Europe PMC', crossref: 'Crossref', epo_ops: 'EPO OPS' }
  const formatTime = (value: string) => {
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString(zh ? 'zh-CN' : 'en-GB', { timeZoneName: 'short' })
  }
  const rawUrl = safeCitationUrl(artifact.data?.download_url)
  return <Accordion value={open ? ['source'] : []} onValueChange={(values) => setOpen(values.includes('source'))} className="mt-3 rounded border border-border-soft p-3 text-xs"><AccordionItem value="source"><AccordionTrigger>{zh ? '查证：已存片段与检索记录' : 'Verify: saved excerpts and retrieval records'}</AccordionTrigger><AccordionContent>
    {open ? <div className="mt-3 space-y-3">
      <p className="text-text-muted">{zh ? '书目信息、摘要和正文片段分开保存。下方原文保留来源语言，界面语言切换不会改写证据；仅保存摘要时不能视为已阅读全文。' : 'Bibliographic metadata, abstracts and source excerpts are stored separately. Original excerpts keep their source language; changing the interface language does not translate evidence. An abstract is not a full-text reading.'}</p>
      {abstract ? <Disclosure title={zh ? '数据库中的摘要（原文）' : 'Stored abstract (original language)'}><blockquote className="mt-2 whitespace-pre-wrap border-l-2 pl-2">{abstract}</blockquote></Disclosure> : null}
      <CitationDetails prefix={`document-${documentId}`} citations={[{ ...provenance, document_id: documentId, label: zh ? '当前已索引的来源快照' : 'Currently indexed source snapshot' }]} />
      {changed ? <p role="status" className="text-warning">{zh ? '最新抓取与已索引片段的来源不同。当前片段仍引用原快照，未自动替换。' : 'The latest retrieval differs from the indexed source. Existing excerpts still refer to their original snapshot and have not been replaced.'}</p> : null}
      {rawUrl ? <a className="text-accent underline" href={rawUrl} target="_blank" rel="noopener noreferrer">{zh ? '下载保存的原始文件' : 'Download saved original file'} · {artifact.data?.filename}</a> : null}
      {artifact.isError ? <p role="alert">{zh ? '原始文件链接暂不可用。' : 'The original-file link is unavailable.'}</p> : null}
      <h4 className="font-medium">{zh ? '已保存的原文片段' : 'Saved source excerpts'} ({savedChunks.length}{chunks.hasNextPage ? (zh ? ' 已加载，尚未完整' : ' loaded, incomplete') : ''})</h4>
      {chunks.isPending ? <p role="status">{zh ? '正在读取片段…' : 'Loading excerpts…'}</p> : null}
      {chunks.hasNextPage && !chunks.isFetchNextPageError ? <p role="status">{zh ? '正在读取剩余片段，完成后按原文顺序显示…' : 'Loading the remaining excerpts before displaying them in source order…'}</p> : null}
      {chunks.isError ? <p role="alert">{zh ? '片段读取失败；不能将错误视为没有证据。' : 'Excerpts could not be loaded; this error does not mean there is no evidence.'}</p> : null}
      {chunks.isSuccess && !savedChunks.length ? <p>{zh ? '尚未保存正文或摘要片段。' : 'No source excerpts have been saved.'}</p> : null}
      {(!chunks.hasNextPage || chunks.isFetchNextPageError) ? savedChunks.map((chunk) => <Disclosure key={chunk.id} className="border-l-2 pl-2" title={`${zh ? '片段' : 'Excerpt'} ${chunk.position + 1} · v${chunk.version}`}><p className="my-1 break-all text-text-muted">{chunk.id}</p><blockquote className="whitespace-pre-wrap">{chunk.content}</blockquote></Disclosure>) : null}
      {chunks.hasNextPage && chunks.isFetchNextPageError ? <Button type="button" size="xs" variant="outline" disabled={chunks.isFetchingNextPage} onClick={() => chunks.fetchNextPage()}>{zh ? '重试加载剩余片段' : 'Retry remaining excerpts'}</Button> : null}
      <h4 className="font-medium">{zh ? '已加载检索记录（按时间排列）' : 'Loaded retrieval records (chronological)'} ({savedTraces.length})</h4>
      {traces.isPending ? <p role="status">{zh ? '正在读取检索记录…' : 'Loading retrieval records…'}</p> : null}
      {traces.isError ? <p role="alert">{zh ? '检索记录读取失败。' : 'Retrieval records could not be loaded.'}</p> : null}
      {traces.isSuccess && !savedTraces.length ? <p>{zh ? '未记录外部检索过程；可能是手动或研究包导入。' : 'No external retrieval trace is recorded; this may be a manual or research-package import.'}</p> : null}
      {savedTraces.map((trace) => <Disclosure key={trace.id} title={`${sourceLabels[trace.source] || trace.source} · ${citationValueLabel(trace.stage, language)} · ${citationValueLabel(trace.status, language)} · ${formatTime(trace.created_at)}`}><dl className="mt-1 grid gap-1 break-all"><dt>{zh ? '检索 ID' : 'Trace ID'}</dt><dd>{trace.id}</dd><dt>{zh ? '请求' : 'Request'}</dt><dd><pre className="whitespace-pre-wrap">{JSON.stringify(trace.request_json, null, 2)}</pre></dd><dt>HTTP</dt><dd>{trace.http_status ?? '—'}</dd><dt>SHA-256</dt><dd>{trace.content_checksum_sha256 || trace.response_checksum_sha256 || '—'}</dd></dl>{trace.error ? <p>{trace.error}</p> : null}</Disclosure>)}
      {traces.hasNextPage ? <Button type="button" size="xs" variant="outline" disabled={traces.isFetchingNextPage} onClick={() => traces.fetchNextPage()}>{zh ? '加载更多检索记录' : 'Load more retrieval records'}</Button> : null}
    </div> : null}
  </AccordionContent></AccordionItem></Accordion>
}
