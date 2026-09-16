import { useEffect, useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { getPatentLandscape, queuePatentLookup, searchPatentClaims } from '../../lib/api/patents'
import { getOperation, isSettled } from '../../lib/api/operations'
import { useProjectAccess } from '../../lib/hooks/useProjectAccess'
import { useI18n } from '../../lib/i18n'
import { useAppStore } from '../../lib/store/appStore'

function LookupProgress({ id, projectId }: { id: string; projectId: string }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const client = useQueryClient()
  const operation = useQuery({
    queryKey: ['operation', id], queryFn: () => getOperation(id),
    refetchInterval: (query) => query.state.data && isSettled(query.state.data) ? false : 2000,
  })
  const status = operation.data?.status
  useEffect(() => {
    if (status && ['succeeded', 'failed', 'cancelled'].includes(status)) {
      void client.invalidateQueries({ queryKey: ['patents', projectId] })
    }
  }, [status, client, projectId])
  const labels: Record<string, string> = zh
    ? { succeeded: '任务已结束；部分公开文本可能不可用，请查看活动记录与检索结果。', failed: '任务失败，请查看活动记录。', cancelled: '任务已取消。' }
    : { succeeded: 'Task finished; some publications may be unavailable. Check Activity and search results.', failed: 'Task failed. Check Activity.', cancelled: 'Task cancelled.' }
  return <p role="status" className="text-sm text-text-secondary">{operation.isError
    ? (zh ? '无法读取进度，可在活动记录中继续查看。' : 'Progress unavailable. Check Activity.')
    : labels[status ?? ''] ?? (zh ? '已排队，正在等待检索结果…' : 'Queued; waiting for retrieval results…')}</p>
}

/** Mounted only when the reference tools disclosure is opened. */
export function PatentPanel({ projectId }: { projectId: string }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const access = useProjectAccess(projectId)
  const demo = useAppStore((state) => state.appMode === 'demo')
  const canWrite = !demo && access.data?.permissions.write === true
  const [draft, setDraft] = useState('')
  const [search, setSearch] = useState('')
  const [operations, setOperations] = useState<string[]>([])
  const landscape = useQuery({ queryKey: ['patents', projectId, 'landscape'], queryFn: () => getPatentLandscape(projectId) })
  const claims = useInfiniteQuery({
    queryKey: ['patents', projectId, 'claims', search], enabled: search.length >= 2,
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => searchPatentClaims(projectId, search, pageParam),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  })
  const lookup = useMutation({
    mutationFn: ({ documentId, kind }: { documentId: string; kind: 'claims' | 'legal' }) => queuePatentLookup(projectId, documentId, kind),
    onSuccess: (result) => setOperations((ids) => [...ids, result.operation_id]),
  })
  const actionButtons = (documentId: string) => <div className="flex flex-wrap gap-2">
    <Button type="button" size="xs" variant="outline" disabled={!canWrite || lookup.isPending} onClick={() => lookup.mutate({ documentId, kind: 'claims' })}>{zh ? '检索权利要求' : 'Retrieve claims'}</Button>
    <Button type="button" size="xs" variant="outline" disabled={!canWrite || lookup.isPending} onClick={() => lookup.mutate({ documentId, kind: 'legal' })}>{zh ? '查询同族与法律事件' : 'Retrieve family and legal events'}</Button>
  </div>
  const data = landscape.data
  return <section className="grid gap-4" aria-label={zh ? '专利证据' : 'Patent evidence'}>
    <p className="text-sm text-text-secondary">{zh ? '基于已保存的公开记录分组。法律事件和权利要求原文均不等同于有效性或自由实施结论。' : 'Groups reflect saved publications. Legal events and verbatim claims do not establish validity or freedom to operate.'}</p>
    <Button type="button" variant="outline" size="sm" onClick={() => void landscape.refetch()}>{zh ? '刷新同族记录' : 'Refresh families'}</Button>
    {landscape.isPending ? <p role="status">{zh ? '正在读取…' : 'Loading…'}</p> : null}
    {landscape.isError ? <p role="alert">{zh ? '专利记录加载失败。' : 'Could not load patent records.'}</p> : null}
    {data ? <>
      <p>{zh ? `已保存 ${data.records_matched} 个公开文本，${data.families.distinct} 个已知同族；${data.families.publications_without_family_id} 个文本缺少同族信息。` : `${data.records_matched} saved publications, ${data.families.distinct} known families; ${data.families.publications_without_family_id} publications lack family information.`}</p>
      {data.documents_truncated || data.families.groups_truncated || data.records_listed < data.records_matched ? <p role="status">{zh ? '当前为有上限的记录预览，不能代表完整专利格局。' : 'This bounded preview does not represent the complete patent landscape.'}</p> : null}
      {data.families.groups.map((family) => <article key={family.family_id} className="grid gap-2 rounded border p-3">
        <h4 className="font-semibold">{zh ? '同族' : 'Family'} {family.family_id} · {family.publications}</h4>
        <p className="text-sm">{family.jurisdictions.join(' · ')} · {family.applicants.join('; ')}</p>
        {family.members.map((member) => <div key={member.document_id} className="grid gap-2 border-t pt-2"><p>{member.publication_number} — {member.title}</p>{actionButtons(member.document_id)}</div>)}
        {family.members_truncated ? <p>{zh ? '仅显示前 10 个成员。' : 'Showing the first 10 members.'}</p> : null}
      </article>)}
      {data.records.filter((record) => !record.family_id).map((record) => <article key={record.document_id} className="grid gap-2 rounded border p-3"><p>{record.publication_number} — {record.title}</p>{actionButtons(record.document_id)}</article>)}
    </> : null}
    {lookup.isError ? <p role="alert">{lookup.error.message}</p> : null}
    {operations.map((id) => <LookupProgress key={id} id={id} projectId={projectId} />)}
    <form className="flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); setSearch(draft.trim()) }}>
      <Input aria-label={zh ? '搜索已保存的权利要求' : 'Search saved claims'} value={draft} maxLength={300} onChange={(event) => setDraft(event.target.value)} />
      <Button type="submit" disabled={draft.trim().length < 2}>{zh ? '搜索原文' : 'Search text'}</Button>
    </form>
    {search && claims.isPending ? <p role="status">{zh ? '搜索中…' : 'Searching…'}</p> : null}
    {claims.isError ? <p role="alert">{zh ? '搜索失败，请重试。' : 'Search failed. Please retry.'}</p> : null}
    {claims.data?.pages.flatMap((page) => page.items).map((claim) => <article key={claim.claim_id} className="rounded border p-3">
      <h4>{claim.title} · {zh ? '权利要求' : 'Claim'} {claim.claim_number} ({claim.language})</h4>
      <p className="mt-2 whitespace-pre-wrap text-sm">{claim.excerpt}</p>
    </article>)}
    {claims.isSuccess && !claims.data.pages[0].items.length ? <p>{zh ? '已保存的原文中没有匹配。请先检索公开文本的权利要求。' : 'No matches in saved text. Retrieve publication claims first.'}</p> : null}
    {claims.hasNextPage ? <Button type="button" variant="outline" disabled={claims.isFetchingNextPage} onClick={() => void claims.fetchNextPage()}>{zh ? '更多结果' : 'More results'}</Button> : null}
  </section>
}
