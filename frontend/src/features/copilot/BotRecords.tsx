import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Button } from '../../components/ui/Button'
import { ApiState } from '../../components/ui/ApiState'
import { getBotRecords, downloadBotRecords } from '../../lib/api/botRecords'
import { ReviewMarkdown } from '../research/ReviewMarkdown'
import { useI18n } from '../../lib/i18n'

export function BotRecords({ projectId, botId }: { projectId: string; botId: string }) {
  const zh = useI18n().language === 'zh'
  const [input, setInput] = useState('')
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [downloadError, setDownloadError] = useState('')
  const [downloading, setDownloading] = useState(false)
  const records = useQuery({ queryKey: ['bot-records', projectId, botId, query, offset], queryFn: () => getBotRecords(projectId, botId, query, offset), refetchInterval: 5000 })
  const download = async () => {
    setDownloading(true)
    setDownloadError('')
    try { await downloadBotRecords(projectId, botId) }
    catch (error) { setDownloadError(error instanceof Error ? error.message : String(error)) }
    finally { setDownloading(false) }
  }
  return <section aria-label={zh ? 'Bot 工作记录' : 'Bot work records'} className="space-y-4">
    <p className="text-sm text-text-secondary">{zh ? '由平台消息和任务自动保存。来源身份与状态保留；工作流引用不代表执行完成，任务成功不等同于科学验证通过。' : 'Saved automatically from platform messages and tasks. Source identity and status are preserved. Workflow references do not establish execution, and task success is not scientific validation.'}</p>
    <form className="flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); setQuery(input); setOffset(0) }}>
      <input className="min-w-0 flex-1 rounded border p-2" aria-label={zh ? '搜索工作记录' : 'Search work records'} value={input} maxLength={500} onChange={(event) => setInput(event.target.value)} placeholder={zh ? '工作流 ID、引用、关键词…' : 'Workflow ID, reference, keyword…'} />
      <Button type="submit">{zh ? '搜索' : 'Search'}</Button>
      <Button type="button" variant="outline" disabled={downloading || !records.data?.record_id} onClick={() => void download()}>{zh ? '下载完整 MD' : 'Download full MD'}</Button>
    </form>
    {downloadError ? <p role="alert">{downloadError}</p> : null}
    <ApiState isLoading={records.isLoading} isError={records.isError} error={records.error} onRetry={() => void records.refetch()}>
      {records.data ? <>
        <p className="break-all text-xs text-text-secondary">{zh ? '匹配 / 全部' : 'Matches / total'}: {records.data.matched} / {records.data.total} · {records.data.updated_at ?? (zh ? '尚未生成' : 'Not generated')}<br />SHA-256: {records.data.sha256 ?? '—'}</p>
        {records.data.items.length === 0 ? <p>{zh ? '没有匹配记录。' : 'No matching records.'}</p> : records.data.items.map((item) => <article key={`${item.kind}:${item.id}`} className="space-y-2 rounded border p-4">
          <h3 className="break-all font-medium">{item.bot} · {item.kind} · {item.status}</h3>
          <p className="break-all text-xs text-text-secondary">{item.id} · {item.created_at} · v{item.source_version}</p>
          <ReviewMarkdown projectId={projectId}>{item.content}</ReviewMarkdown>
          {item.error ? <p role="note" className="whitespace-pre-wrap text-sm">{item.error}</p> : null}
          {item.kind === 'agent_run' ? <Link className="text-accent underline" to={`/bots/${encodeURIComponent(botId)}?project=${encodeURIComponent(projectId)}&run=${encodeURIComponent(item.id)}`}>{zh ? '查看任务与原始转录' : 'Open task and source transcript'}</Link> : null}
          {item.conversation_id ? <p className="break-all text-xs">Conversation: {item.conversation_id}</p> : null}
          <details><summary>{zh ? '来源、工作流与证据引用' : 'Sources, workflows and evidence references'}</summary><pre className="overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify({ references: item.references, citations: item.citations, turn_ids: item.turn_ids, outcome: item.outcome }, null, 2)}</pre></details>
        </article>)}
        <div className="flex gap-2">
          <Button variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>{zh ? '上一页' : 'Previous'}</Button>
          <Button variant="outline" disabled={offset + records.data.items.length >= records.data.matched} onClick={() => setOffset(offset + 50)}>{zh ? '下一页' : 'Next'}</Button>
        </div>
      </> : null}
    </ApiState>
  </section>
}
