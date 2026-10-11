import { useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { ArrowSquareOutIcon, BookOpenTextIcon, QuotesIcon } from '@phosphor-icons/react'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Badge } from '../../components/reui/badge'
import { listEvidenceNotes } from '../../lib/api/evidenceNotes'
import { workspaceText } from '../../lib/api/researchWorkspace'
import { useProjectAccess } from '../../lib/hooks/useProjectAccess'
import { useI18n } from '../../lib/i18n'
import { EvidenceNoteCard } from './EvidenceNoteCard'
import { EvidenceNoteEditor } from './EvidenceNoteEditor'
import { EvidenceSourceRetrieval } from './EvidenceSourceRetrieval'
import { LiteratureSourceDetails } from './LiteratureSourceDetails'
import { citationValueLabel, safeCitationUrl } from './citationMarkers'
import { evidenceMarkdown, evidenceRelations, noteMatches, referenceUrl, relationLabel, type EvidenceNote, type LiteratureReference } from './evidenceNotes'

export function LiteratureWorkbench({ projectId, references, readOnly = false }: {
  projectId: string; references: LiteratureReference[]; readOnly?: boolean
}) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const access = useProjectAccess(projectId)
  const canWrite = !readOnly && access.data?.permissions.write === true
  const [mode, setMode] = useState<'papers' | 'arguments'>('papers')
  const [search, setSearch] = useState('')
  const [gapsOnly, setGapsOnly] = useState(false)
  const [selectedId, setSelectedId] = useState(references[0]?.document_id ?? '')
  const [editor, setEditor] = useState<{ reference: LiteratureReference; note?: EvidenceNote } | null>(null)
  const notes = useInfiniteQuery({
    queryKey: ['evidence-notes', projectId], initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => listEvidenceNotes(projectId, pageParam),
    getNextPageParam: (page) => page.next_cursor ?? undefined, retry: false,
  })
  const allNotes = notes.data?.pages.flatMap((page) => page.items) ?? []
  const complete = notes.isSuccess && !notes.hasNextPage
  const hasNote = (id: string) => allNotes.some((note) => note.document_id === id)
  const visibleReferences = references.filter((reference) => (!gapsOnly || !hasNote(reference.document_id)) &&
    `${workspaceText(reference.title, language)} ${reference.authors ?? ''} ${reference.ref_id} ${reference.doi ?? ''}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()))
  const selected = visibleReferences.find((reference) => reference.document_id === selectedId) ?? visibleReferences[0]
  const visibleNotes = allNotes.filter((note) => noteMatches(note, search))
  const displayedNotes = mode === 'papers' ? allNotes.filter((note) => note.document_id === selected?.document_id) : visibleNotes
  const grouped = new Map<string, EvidenceNote[]>()
  for (const note of visibleNotes) grouped.set(note.argument.trim(), [...(grouped.get(note.argument.trim()) ?? []), note])
  const editNote = (note: EvidenceNote) => setEditor({ note, reference: references.find((reference) => reference.document_id === note.document_id) ?? {
    document_id: note.document_id, ref_id: '', status: 'available', title: { default: note.document_title }, url: note.source_url,
  } })
  const exportNotes = () => {
    const blob = new Blob([evidenceMarkdown(displayedNotes, zh)], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = `evidence-notes-${projectId}.md`; anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const card = (note: EvidenceNote) => <EvidenceNoteCard key={note.id} note={note} projectId={projectId} canWrite={canWrite} showArgument={mode === 'papers'} onEdit={() => editNote(note)} />
  return <section className="grid min-w-0 gap-5" aria-label={zh ? '文献论据工作台' : 'Literature evidence workbench'}>
    <header className="grid gap-4 border bg-background p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4"><div><p className="mb-2 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Evidence notebook</p>
        <h2 className="text-xl font-semibold">{zh ? '把论文变成可核对的论据' : 'From papers to traceable evidence'}</h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{zh ? '我们的论点 → 论文原文 → 论据解释 → 适用边界。每条论据都保留论文链接，支持与反驳放在一起阅读。' : 'Project argument → original passage → interpretation → limits. Keep the paper link with every excerpt and read supporting and conflicting evidence together.'}</p></div><QuotesIcon className="hidden size-8 shrink-0 text-primary sm:block" /></div>
      <div className="flex flex-wrap gap-2 text-xs"><Badge variant="outline">{references.length} {zh ? '篇文献' : 'papers'}</Badge><Badge variant="outline">{allNotes.length}{complete ? '' : '+'} {zh ? '条已加载论据' : 'loaded evidence cards'}</Badge><Badge variant="outline">{allNotes.filter((note) => note.review_status === 'accepted').length} {zh ? '条已认可' : 'accepted cards'}</Badge></div>
    </header>
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex gap-1" role="group" aria-label={zh ? '阅读方式' : 'Reading view'}>
        <Button variant={mode === 'papers' ? 'default' : 'outline'} aria-pressed={mode === 'papers'} onClick={() => setMode('papers')}><BookOpenTextIcon />{zh ? '按文献阅读' : 'By paper'}</Button>
        <Button variant={mode === 'arguments' ? 'default' : 'outline'} aria-pressed={mode === 'arguments'} onClick={() => setMode('arguments')}><QuotesIcon />{zh ? '按论点对照' : 'By argument'}</Button>
      </div>
      <Input className="min-w-40 flex-1" aria-label={zh ? '查找文献与论据' : 'Find papers and evidence'} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={mode === 'papers' ? (zh ? '标题、作者、DOI…' : 'Title, author, DOI…') : (zh ? '论点、原文、论据解释…' : 'Argument, quote, interpretation…')} />
      {mode === 'papers' ? <Button variant="outline" disabled={!complete} aria-pressed={gapsOnly} onClick={() => setGapsOnly(!gapsOnly)}>{zh ? '仅看待整理' : 'Needs annotation'}</Button> : null}
      <Button variant="outline" disabled={!displayedNotes.length} onClick={exportNotes}>{zh ? '导出当前论据' : 'Export shown evidence'}</Button>
    </div>
    {notes.isPending ? <p role="status" className="text-sm text-muted-foreground">{zh ? '正在加载已整理的论据…' : 'Loading evidence cards…'}</p> : null}
    {notes.isError ? <div role="alert" className="flex flex-wrap items-center gap-3 border border-destructive/40 p-3 text-sm"><span>{zh ? '论据读取失败，不能据此判断文献尚未整理。' : 'Evidence could not be loaded; this does not mean the papers are unannotated.'}</span><Button variant="outline" onClick={() => notes.refetch()}>{zh ? '重试' : 'Retry'}</Button></div> : null}
    {notes.hasNextPage ? <Button variant="outline" disabled={notes.isFetchingNextPage} onClick={() => notes.fetchNextPage()}>{zh ? '加载更多论据（当前统计未完整）' : 'Load more evidence (counts are incomplete)'}</Button> : null}
    {editor ? <EvidenceNoteEditor key={`${editor.reference.document_id}-${editor.note?.id ?? 'new'}`} projectId={projectId} reference={editor.reference} note={editor.note} argumentChoices={[...new Set(allNotes.map((note) => note.argument))]} onClose={() => setEditor(null)} /> : null}
    {mode === 'papers' ? <div className="grid min-w-0 items-start gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
      <nav aria-label={zh ? '文献目录' : 'Paper library'} className="grid max-h-[38rem] gap-1 overflow-auto border bg-background p-2">
        {visibleReferences.map((reference) => <Button key={reference.document_id} variant="ghost" aria-pressed={selected?.document_id === reference.document_id} className={`h-auto min-w-0 flex-col items-start gap-2 whitespace-normal p-3 text-left ${selected?.document_id === reference.document_id ? 'bg-muted border-l-primary' : ''}`} onClick={() => setSelectedId(reference.document_id)}>
          <span className="text-[10px] font-normal text-muted-foreground">{reference.ref_id} {reference.year ? `· ${reference.year}` : ''}</span>
          <span className="line-clamp-3 text-sm leading-5">{workspaceText(reference.title, language)}</span>
          <span className="text-xs font-normal text-muted-foreground">{hasNote(reference.document_id) ? `${allNotes.filter((note) => note.document_id === reference.document_id).length} ${zh ? '条论据' : 'evidence cards'}` : complete ? (zh ? '待补齐论点与摘录' : 'Needs argument & excerpt') : (zh ? '论据状态待加载' : 'Evidence status not yet loaded')}</span>
        </Button>)}
        {!visibleReferences.length ? <p className="p-3 text-sm text-muted-foreground">{zh ? '没有符合条件的文献。' : 'No matching papers.'}</p> : null}
      </nav>
      {selected ? <div className="grid min-w-0 gap-4">
        <div className="grid gap-3 border bg-background p-5">
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground"><span>{selected.ref_id} · {citationValueLabel(selected.verification_status || selected.status, language)}</span><span>{[selected.year, selected.journal?.trim() || (zh ? '期刊未记录' : 'Journal not recorded')].filter(Boolean).join(' · ')}</span></div>
          <h3 className="text-lg font-semibold leading-7">{workspaceText(selected.title, language)}</h3>
          {selected.authors ? <p className="text-sm text-muted-foreground">{selected.authors}</p> : null}
          <div className="flex flex-wrap items-center gap-3">{referenceUrl(selected) ? <a href={referenceUrl(selected)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm text-primary hover:underline"><ArrowSquareOutIcon />{zh ? '打开论文' : 'Open paper'}</a> : <span className="text-xs text-muted-foreground">{zh ? '论文链接待补齐' : 'Paper link missing'}</span>}
            {selected.doi ? <a className="text-xs text-primary hover:underline" href={safeCitationUrl(`https://doi.org/${selected.doi}`)} target="_blank" rel="noopener noreferrer">DOI {selected.doi}</a> : null}
            {canWrite ? <Button variant="outline" onClick={() => setEditor({ reference: selected })}>{zh ? '添加论点与原文' : 'Add argument & passage'}</Button> : null}</div>
          {canWrite ? <EvidenceSourceRetrieval key={`retrieve-${selected.document_id}`} projectId={projectId} reference={selected} /> : null}
          <LiteratureSourceDetails key={`source-${selected.document_id}`} projectId={projectId} documentId={selected.document_id} metadata={selected.metadata ?? {}} abstract={selected.abstract} />
        </div>
        {displayedNotes.map(card)}
        {complete && !displayedNotes.length ? <div className="border border-dashed p-6"><h4 className="font-medium">{zh ? '这篇文献还没有形成项目论据' : 'This paper has no project evidence card yet'}</h4><p className="mt-2 text-sm leading-6 text-muted-foreground">{zh ? '已有题录或自动拆句仍需整理。请选出所需原文，写清它支持或限制哪个论点，以及适用条件。' : 'Bibliographic records and extracted sentences still need interpretation. Select a passage, identify the argument it supports or limits, and record its conditions.'}</p></div> : null}
      </div> : null}
    </div> : <div className="grid gap-7">
      {[...grouped].map(([argument, group]) => <section key={argument} className="grid gap-3"><h3 className="border-b pb-3 text-lg font-semibold">{argument}<span className="ml-3 text-xs font-normal text-muted-foreground">{group.length} {zh ? '条论据' : 'evidence cards'}</span></h3><div className="flex flex-wrap gap-2">{evidenceRelations.map((relation) => <Badge key={relation} variant="outline">{relationLabel(relation, zh)} · {group.filter((note) => note.relation === relation).length}</Badge>)}</div>{group.map(card)}</section>)}
      {!visibleNotes.length && complete ? <div className="border border-dashed p-6 text-sm text-muted-foreground">{zh ? '尚无符合条件的论据。先在“按文献阅读”中添加论点与原文，同一论点的支持和反驳会汇集在这里。' : 'No matching evidence. Add an argument and passage in “By paper”; support and contradictions for the same argument appear together here.'}</div> : null}
    </div>}
  </section>
}
