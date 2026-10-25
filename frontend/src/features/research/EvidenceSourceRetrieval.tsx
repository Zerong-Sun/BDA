import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '../../components/ui/Button'
import { getEvidenceSourceRetrieval, retrieveEvidenceSource } from '../../lib/api/evidenceNotes'
import { useI18n } from '../../lib/i18n'
import type { LiteratureReference } from './evidenceNotes'

export function EvidenceSourceRetrieval({ projectId, reference }: { projectId: string; reference: LiteratureReference }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const client = useQueryClient()
  const query = /^\d+$/.test(reference.pmid ?? '') ? `EXT_ID:${reference.pmid} AND SRC:MED`
    : /^10\.\d{4,9}\/[^"\\\s]+$/.test(reference.doi ?? '') ? `DOI:"${reference.doi}"` : ''
  const start = useMutation({ mutationFn: () => retrieveEvidenceSource(projectId, query) })
  const run = useQuery({ queryKey: ['evidence-source-retrieval', projectId, start.data?.id],
    queryFn: () => getEvidenceSourceRetrieval(start.data!.id), enabled: Boolean(start.data?.id),
    refetchInterval: (result) => result.state.data && !['pending', 'running'].includes(result.state.data.search.status) ? false : 2000,
  })
  const status = run.data?.search.status
  const finished = status && !['pending', 'running'].includes(status)
  useEffect(() => {
    if (!finished) return
    for (const key of ['research-workspace', 'evidence-note-chunks', 'literature-source-chunks', 'literature-source-traces']) {
      void client.invalidateQueries({ queryKey: [key, projectId] })
    }
  }, [finished, client, projectId])
  if (!query) return null
  return <div className="grid gap-2">
    <Button type="button" className="justify-self-start" variant="outline" size="sm" disabled={start.isPending || Boolean(start.data && !finished)} onClick={() => start.mutate()}>{zh ? '补齐摘要 / 开放全文' : 'Retrieve abstract / open full text'}</Button>
    {start.data ? <p role="status" className="text-xs text-muted-foreground">{finished ? status === 'failed' ? (zh ? '检索失败；请查看检索记录。' : 'Retrieval failed; check the retrieval record.') : (zh ? '检索已结束。可获取范围以保存的原文与检索记录为准。' : 'Retrieval finished. See saved passages and retrieval records for available content.') : (zh ? '正在检索这篇文献，保留原始来源记录…' : 'Retrieving this paper with source provenance…')}</p> : null}
    {start.isError || run.isError ? <p role="alert" className="text-xs text-destructive">{zh ? '请求失败。已有记录未受影响。' : 'Request failed. Existing records are retained.'}</p> : null}
    {run.isError ? <Button type="button" size="sm" variant="outline" onClick={() => run.refetch()}>{zh ? '重试读取检索进度' : 'Retry retrieval status'}</Button> : null}
  </div>
}
