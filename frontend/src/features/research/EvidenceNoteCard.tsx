import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowSquareOutIcon } from '@phosphor-icons/react'
import { Badge } from '../../components/reui/badge'
import { Button } from '../../components/ui/Button'
import { Disclosure } from '../../components/ui/Disclosure'
import { reviewEvidenceNote } from '../../lib/api/evidenceNotes'
import { useI18n } from '../../lib/i18n'
import { citationValueLabel, safeCitationUrl } from './citationMarkers'
import { relationLabel, type EvidenceNote } from './evidenceNotes'

export function EvidenceNoteCard({ note, projectId, canWrite, onEdit, showArgument = true }: {
  note: EvidenceNote; projectId: string; canWrite: boolean; onEdit: () => void; showArgument?: boolean
}) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const client = useQueryClient()
  const review = useMutation({
    mutationFn: (status: 'accepted' | 'rejected' | 'pending') => reviewEvidenceNote(note.id, note.version, status),
    onSuccess: () => client.invalidateQueries({ queryKey: ['evidence-notes', projectId] }),
  })
  const url = safeCitationUrl(note.source_url)
  const anchor = ({ matched: zh ? '已与保存原文匹配' : 'Matches saved source', changed: zh ? '原文版本变化 · 待重新定位' : 'Source changed · re-anchor required', unverified: zh ? '手工摘录 · 未匹配' : 'Manual excerpt · unverified' })[note.anchor_status]
  const selectors = Array.isArray(note.source_ref.selector) ? note.source_ref.selector as Array<Record<string, unknown>> : []
  const quoteSelector = selectors.find((item) => item.type === 'TextQuoteSelector')
  const prefix = typeof quoteSelector?.prefix === 'string' ? quoteSelector.prefix : ''
  const suffix = typeof quoteSelector?.suffix === 'string' ? quoteSelector.suffix : ''
  const contentKind = typeof note.source_ref.content_kind === 'string' ? note.source_ref.content_kind : ''
  const location = [note.locator, note.structured_locator?.section, note.structured_locator?.figure, note.structured_locator?.page ? `${zh ? '第' : 'p. '}${note.structured_locator.page}${zh ? '页' : ''}` : ''].filter(Boolean).join(' · ')
  return <article className="grid min-w-0 gap-4 border border-border bg-background p-5" data-testid="evidence-note-card">
    <div className="flex flex-wrap items-center gap-2">
      <Badge variant={note.relation === 'contradicts' ? 'destructive' : 'outline'}>{relationLabel(note.relation, zh)}</Badge>
      <Badge variant="secondary">{citationValueLabel(note.review_status, language)}</Badge>
      <span className={`text-xs ${note.anchor_status === 'changed' ? 'text-destructive' : 'text-muted-foreground'}`}>{anchor}</span>
    </div>
    {showArgument ? <div><p className="mb-1 text-xs text-muted-foreground">{zh ? '我们需要的论点' : 'Our project argument'}</p><h3 className="whitespace-pre-wrap font-semibold leading-6">{note.argument}</h3></div> : null}
    <div className="border-l-2 border-primary bg-muted/20 px-4 py-3">
      <p className="mb-2 text-xs font-medium text-muted-foreground">{zh ? '论文原文 · 原语言' : 'Original passage · source language'}</p>
      <blockquote className="whitespace-pre-wrap break-words text-sm leading-7">{note.quote}</blockquote>
      <p className="mt-3 text-xs text-muted-foreground">{location || (zh ? '页码 / 章节未记录' : 'Page / section not recorded')}{typeof note.source_ref.chunk_position === 'number' ? ` · ${zh ? '片段' : 'Passage'} ${note.source_ref.chunk_position + 1}` : ''}{contentKind.includes('abstract') ? (zh ? ' · 仅摘要' : ' · Abstract only') : ''}</p>
      {note.structured_locator ? <p className="mt-1 text-xs text-muted-foreground">{zh ? '出版物位置由整理者填写，尚未做 PDF 坐标核验' : 'Publication location is human-entered; PDF coordinates have not been verified'}</p> : null}
    </div>
    <a className="inline-flex min-w-0 items-start gap-2 break-words text-sm text-primary underline-offset-4 hover:underline" href={url} target="_blank" rel="noopener noreferrer"><ArrowSquareOutIcon className="mt-0.5 shrink-0" />{note.document_title}</a>
    <dl className="grid gap-4 text-sm md:grid-cols-2">
      <div><dt className="mb-1 font-medium">{zh ? '论文观点' : 'What the paper says'}</dt><dd className="whitespace-pre-wrap leading-6 text-muted-foreground">{note.paper_claim}</dd></div>
      <div><dt className="mb-1 font-medium">{zh ? '提供的论据 / 我们的解释' : 'Evidence / our interpretation'}</dt><dd className="whitespace-pre-wrap leading-6 text-muted-foreground">{note.interpretation}</dd></div>
      <div className="border-t pt-3 md:col-span-2"><dt className="mb-1 font-medium">{zh ? '适用边界 · 尚不能证明' : 'Limits · what remains unproven'}</dt><dd className="whitespace-pre-wrap leading-6 text-muted-foreground">{note.limitations}</dd></div>
    </dl>
    <Disclosure title={zh ? '核对上下文与来源记录' : 'Check context and provenance'}>
      {prefix || suffix ? <p className="mb-3 whitespace-pre-wrap text-sm leading-7 text-muted-foreground">{prefix}<mark className="bg-primary/20 text-foreground">{note.quote}</mark>{suffix}</p> : null}
      <p className="mb-2 text-xs text-muted-foreground">{zh ? '匹配仅针对本系统保存的文字；人工复核不表示本项目已获得实验验证。' : 'Matching checks the text saved here. Human review does not mean this project has been experimentally validated.'}</p>
      <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-all text-[11px] text-muted-foreground">{JSON.stringify({ note_id: note.id, argument_id: note.argument_id, version: note.version, reviewed_by: note.reviewed_by, reviewed_at: note.reviewed_at, ...note.source_ref }, null, 2)}</pre>
    </Disclosure>
    {canWrite ? <div className="flex flex-wrap gap-2">
      <Button type="button" variant="outline" size="sm" onClick={onEdit} disabled={review.isPending}>{zh ? '编辑论据' : 'Edit evidence'}</Button>
      <Button type="button" variant="outline" size="sm" disabled={review.isPending || note.anchor_status === 'changed' || note.review_status === 'accepted'} onClick={() => review.mutate('accepted')}>{zh ? '认可这条论据' : 'Accept evidence'}</Button>
      <Button type="button" variant="ghost" size="sm" disabled={review.isPending || note.review_status === 'rejected'} onClick={() => review.mutate('rejected')}>{zh ? '排除' : 'Exclude'}</Button>
      {note.review_status !== 'pending' ? <Button type="button" variant="ghost" size="sm" disabled={review.isPending} onClick={() => review.mutate('pending')}>{zh ? '重新复核' : 'Reopen review'}</Button> : null}
    </div> : null}
    {review.isError ? <p role="alert" className="text-sm text-destructive">{review.error instanceof Error ? review.error.message : (zh ? '复核失败' : 'Review failed')}</p> : null}
  </article>
}
