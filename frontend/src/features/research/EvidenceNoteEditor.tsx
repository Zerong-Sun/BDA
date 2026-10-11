import { useRef, useState } from 'react'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { listSavedLiteratureChunks } from '../../lib/api/literatureSources'
import { saveEvidenceNote } from '../../lib/api/evidenceNotes'
import { useI18n } from '../../lib/i18n'
import { evidenceRelations, noteDraft, referenceUrl, relationLabel, type ArgumentChoice, type EvidenceNote, type LiteratureReference } from './evidenceNotes'

export function EvidenceNoteEditor({ projectId, reference, note, onClose, argumentChoices = [] }: {
  projectId: string; reference: LiteratureReference; note?: EvidenceNote; onClose: () => void; argumentChoices?: Array<string | ArgumentChoice>
}) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const client = useQueryClient()
  const [draft, setDraft] = useState(() => noteDraft(note, referenceUrl(reference)))
  const choices = argumentChoices.map((choice) => typeof choice === 'string' ? { argument: choice, id: null } : choice)
  const selectedArgument = choices.find((choice) => choice.argument === draft.argument && (!draft.argument_id || choice.id === draft.argument_id))
  const sourceElement = useRef<HTMLParagraphElement>(null)
  const [selection, setSelection] = useState<{ quote: string; start: number } | null>(null)
  const chunks = useInfiniteQuery({
    queryKey: ['evidence-note-chunks', projectId, reference.document_id], initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => listSavedLiteratureChunks(reference.document_id, pageParam),
    getNextPageParam: (page) => page.next_cursor ?? undefined, retry: false,
  })
  const sourceChunks = (chunks.data?.pages.flatMap((page) => page.items) ?? []).sort((a, b) => a.position - b.position)
  const selected = sourceChunks.find((chunk) => chunk.id === draft.chunk_id)
  const save = useMutation({
    mutationFn: () => saveEvidenceNote(reference.document_id, draft, note),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['evidence-notes', projectId] }),
        client.invalidateQueries({ queryKey: ['literature-claims', projectId] }),
      ])
      onClose()
    },
  })
  const field = (key: 'argument' | 'paper_claim' | 'interpretation' | 'limitations', label: string, hint: string) => <label className="grid gap-1.5 text-sm font-medium">
    {label}<Textarea required autoFocus={key === 'argument'} value={draft[key]} maxLength={key === 'argument' ? 2000 : 4000} placeholder={hint}
      onChange={(event) => setDraft({ ...draft, [key]: event.target.value, ...(key === 'argument' ? { argument_id: null } : {}) })} />
  </label>
  const captureSelection = () => {
    const range = window.getSelection()?.rangeCount ? window.getSelection()?.getRangeAt(0) : undefined
    const element = sourceElement.current
    if (!range || !element || !element.contains(range.commonAncestorContainer) || range.collapsed) { setSelection(null); return }
    const prefix = range.cloneRange()
    prefix.selectNodeContents(element)
    prefix.setEnd(range.startContainer, range.startOffset)
    setSelection({ quote: range.toString(), start: Array.from(prefix.toString()).length })
  }
  return <form className="grid gap-5 border border-primary/40 bg-background p-5" onSubmit={(event) => { event.preventDefault(); save.mutate() }}>
    <div className="flex items-center justify-between gap-3"><h3 className="font-semibold">{note ? (zh ? '编辑论据卡' : 'Edit evidence card') : (zh ? '新建论据卡' : 'New evidence card')}</h3>
      <Button type="button" variant="ghost" size="sm" disabled={save.isPending} onClick={onClose}>{zh ? '取消' : 'Cancel'}</Button></div>
    <fieldset className="grid min-w-0 gap-5" disabled={save.isPending}>
      {field('argument', zh ? '1 · 我们需要的论点' : '1 · Our project argument', zh ? '写一个可被支持或反驳的具体判断' : 'One specific, testable project assertion')}
      {choices.length ? <Select items={choices.map((choice) => ({ value: choice.id ?? choice.argument, label: choice.argument }))} value={selectedArgument ? selectedArgument.id ?? selectedArgument.argument : null} onValueChange={(value) => {
        const choice = choices.find((item) => (item.id ?? item.argument) === value)
        if (choice) setDraft({ ...draft, argument: choice.argument, argument_id: choice.id ?? null })
      }}>
        <SelectTrigger aria-label={zh ? '复用已有论点' : 'Reuse an existing argument'} className="w-full min-w-0"><SelectValue placeholder={zh ? '或选择已有论点，将多篇文献放在一起对照' : 'Or reuse an existing argument to compare papers'} /></SelectTrigger>
        <SelectContent>{choices.map((choice) => <SelectItem className="max-w-[36rem] whitespace-normal" key={choice.id ?? choice.argument} value={choice.id ?? choice.argument}>{choice.argument}</SelectItem>)}</SelectContent>
      </Select> : null}
      {note && draft.argument !== note.argument ? <p className="text-xs text-muted-foreground">{zh ? '论点文字改变后，这条论据会归入新的论点；其他论文的论据不会被自动改写。' : 'Changing the assertion moves this card to a new argument. Evidence from other papers is not silently reinterpreted.'}</p> : null}
      <div className="grid min-w-0 gap-2">
        <label className="text-sm font-medium" htmlFor="evidence-source-chunk">{zh ? '2 · 选择原文片段' : '2 · Select a source passage'}</label>
        <Select value={draft.chunk_id ?? 'manual'} onValueChange={(value) => { setDraft({ ...draft, chunk_id: value === 'manual' ? null : value, quote: '', quote_start: null }); setSelection(null) }}>
          <SelectTrigger id="evidence-source-chunk" className="w-full min-w-0"><SelectValue>{selected ? `${zh ? '片段' : 'Passage'} ${selected.position + 1}` : draft.chunk_id ? (zh ? '加载已选片段…' : 'Loading selected passage…') : (zh ? '手工摘录（未与已存原文核对）' : 'Manual excerpt (not source-matched)')}</SelectValue></SelectTrigger>
          <SelectContent><SelectItem value="manual">{zh ? '手工摘录（未核对）' : 'Manual excerpt (unverified)'}</SelectItem>
            {sourceChunks.map((chunk) => <SelectItem key={chunk.id} value={chunk.id}>{chunk.position + 1} · {chunk.content.slice(0, 110)}</SelectItem>)}
          </SelectContent>
        </Select>
        {chunks.isPending ? <p role="status" className="text-xs text-muted-foreground">{zh ? '正在读取原文片段…' : 'Loading source passages…'}</p> : null}
        {chunks.isError ? <p role="alert" className="text-xs text-destructive">{zh ? '原文片段加载失败。' : 'Source passages could not be loaded.'}</p> : null}
        {chunks.hasNextPage || chunks.isError ? <Button type="button" size="sm" variant="outline" disabled={chunks.isFetching} onClick={() => chunks.hasNextPage ? chunks.fetchNextPage() : chunks.refetch()}>{zh ? '继续加载片段' : 'Load more passages'}</Button> : null}
        {selected ? <div className="grid gap-2 border bg-muted/20 p-3">
          <p className="text-xs text-muted-foreground">{zh ? '选中下面需要引用的文字，再点击“采用选文”。也可以直接复制到摘录框。' : 'Select the relevant words, then choose “Use selection”, or copy them into the quote field.'}</p>
          <p ref={sourceElement} onMouseUp={captureSelection} onKeyUp={captureSelection} className="max-h-56 overflow-auto whitespace-pre-wrap break-words text-sm leading-7">{selected.content}</p>
          <Button type="button" variant="outline" size="sm" disabled={!selection} onClick={() => selection && setDraft({ ...draft, quote: selection.quote, quote_start: selection.start })}>{zh ? '采用选文' : 'Use selection'}</Button>
        </div> : !draft.chunk_id ? <p className="text-xs text-muted-foreground">{zh ? '手工粘贴的原文会保留，但不会标为已匹配；请填写章节、页码或图表位置。' : 'A pasted quote remains unverified. Record its section, page or figure location.'}</p> : null}
        <label className="grid gap-1.5 text-sm font-medium">{zh ? '原文摘录（保留原语言）' : 'Original quote (source language)'}
          <Textarea required maxLength={12000} value={draft.quote} onChange={(event) => setDraft({ ...draft, quote: event.target.value, quote_start: null })} className="min-h-28 leading-6" /></label>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="grid gap-1.5 text-sm font-medium">{zh ? '出版物页码（从 1 开始）' : 'Publication page (1-based)'}<Input type="number" min={1} max={100000} step={1} value={draft.structured_locator?.page ?? ''} onChange={(event) => setDraft({ ...draft, structured_locator: { ...draft.structured_locator, page: event.target.value ? Number(event.target.value) : null } })} /></label>
        <label className="grid gap-1.5 text-sm font-medium">{zh ? '章节' : 'Section'}<Input maxLength={500} value={draft.structured_locator?.section ?? ''} onChange={(event) => setDraft({ ...draft, structured_locator: { ...draft.structured_locator, section: event.target.value } })} /></label>
        <label className="grid gap-1.5 text-sm font-medium">{zh ? '图表标识' : 'Figure / table'}<Input maxLength={200} value={draft.structured_locator?.figure ?? ''} onChange={(event) => setDraft({ ...draft, structured_locator: { ...draft.structured_locator, figure: event.target.value } })} /></label>
      </div>
      <p className="text-xs text-muted-foreground">{zh ? '页码、章节、图表是人工定位信息；文字匹配和文档指纹单独核验。' : 'Page, section and figure are human-entered locations. Text matching and document fingerprints are checked separately.'}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="grid gap-1.5 text-sm font-medium">{zh ? '论文链接' : 'Paper URL'}<Input required type="url" value={draft.source_url} onChange={(event) => setDraft({ ...draft, source_url: event.target.value })} /></label>
        <label className="grid gap-1.5 text-sm font-medium">{zh ? '原文位置（章节 / 页码 / 图表）' : 'Location (section / page / figure)'}<Input maxLength={500} value={draft.locator ?? ''} onChange={(event) => setDraft({ ...draft, locator: event.target.value })} placeholder={zh ? '例如 Results · Figure 2 · p. 5' : 'e.g. Results · Figure 2 · p. 5'} /></label>
      </div>
      {field('paper_claim', zh ? '3 · 论文实际说了什么' : '3 · What the paper says', zh ? '用自己的话概括作者的发现，与原文摘录分开' : 'Paraphrase the author’s finding separately from the quote')}
      <div className="flex flex-wrap gap-2" role="group" aria-label={zh ? '证据关系' : 'Evidence relation'}>{evidenceRelations.map((relation) => <Button key={relation} type="button" variant={draft.relation === relation ? 'default' : 'outline'} aria-pressed={draft.relation === relation} size="sm" onClick={() => setDraft({ ...draft, relation })}>{relationLabel(relation, zh)}</Button>)}</div>
      {field('interpretation', zh ? '4 · 它能为我们的论点提供什么论据' : '4 · How this informs our argument', zh ? '说明从论文发现到本项目判断的逻辑；外推请明确标注' : 'Explain the reasoning and identify any extrapolation')}
      {field('limitations', zh ? '5 · 适用边界与尚不能证明的部分' : '5 · Limits and what remains unproven', zh ? '物种、样本、实验条件、相关性与因果性、相反结果等' : 'Species, sample, conditions, correlation vs causation, conflicting results…')}
    </fieldset>
    {save.isError ? <p role="alert" className="text-sm text-destructive">{save.error instanceof Error ? save.error.message : (zh ? '保存失败' : 'Save failed')}</p> : null}
    <div className="flex flex-wrap items-center gap-3"><Button type="submit" disabled={save.isPending}>{save.isPending ? (zh ? '保存中…' : 'Saving…') : (zh ? '保存为待复核论据' : 'Save for review')}</Button><p className="text-xs text-muted-foreground">{zh ? '修改内容会重新进入待复核；原文匹配不等于论点成立。' : 'Edits require a new review. A matching quote does not establish the argument.'}</p></div>
  </form>
}
