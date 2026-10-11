import { useState } from 'react'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArchiveIcon,
  BookOpenTextIcon,
  FloppyDiskIcon,
  MagnifyingGlassIcon,
  SpinnerGapIcon,
} from '@phosphor-icons/react'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Badge } from '../../components/reui/badge'
import {
  Frame,
  FrameDescription,
  FrameFooter,
  FrameHeader,
  FramePanel,
  FrameTitle,
} from '../../components/reui/frame'
import { Button } from '../../components/ui/Button'
import { Disclosure } from '../../components/ui/Disclosure'
import { Input } from '../../components/ui/Input'
import { Label } from '../../components/ui/label'
import { ScrollArea } from '../../components/ui/scroll-area'
import { Textarea } from '../../components/ui/textarea'
import {
  archiveCopilotKnowledgeEntry,
  createCopilotKnowledgeEntry,
  searchCopilotKnowledge,
  updateCopilotKnowledgeEntry,
  type CopilotKnowledgeEntry,
} from '../../lib/api/copilot'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useProjectAccess } from '../../lib/hooks/useProjectAccess'
import { useI18n } from '../../lib/i18n'
import { useAppStore } from '../../lib/store/appStore'
import { commaList } from './jsonHelpers'

const DEFAULT_TAGS = 'manual'

export function KnowledgePanel() {
  const context = useProjectContext()
  return <KnowledgePanelContent key={context.projectId} context={context} />
}

function KnowledgePanelContent({ context }: { context: ReturnType<typeof useProjectContext> }) {
  const { t, language } = useI18n()
  const k = t.research.knowledge
  const client = useQueryClient()
  const { activeProject, projectId } = context
  const access = useProjectAccess(projectId)
  const demo = useAppStore((state) => state.appMode === 'demo')
  const canEdit = !demo && access.data?.permissions.write === true
  const [query, setQuery] = useState('')
  const [entryTypeFilter, setEntryTypeFilter] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [entryId, setEntryId] = useState('')
  const [entryVersion, setEntryVersion] = useState<number | null>(null)
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('workflow')
  const [subcategory, setSubcategory] = useState('')
  const [summary, setSummary] = useState('')
  const [content, setContent] = useState('')
  // Tags stay in English: they are search identifiers shared with seeded entries.
  const [tags, setTags] = useState(DEFAULT_TAGS)
  const [citation, setCitation] = useState('')
  const [originalCitation, setOriginalCitation] = useState('')
  const [entrySource, setEntrySource] = useState<Record<string, unknown>>({})
  const [reviewStatus, setReviewStatus] = useState('unknown')
  const knowledge = useInfiniteQuery({
    queryKey: ['copilot-knowledge', projectId, query, entryTypeFilter], initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => searchCopilotKnowledge(projectId, query, entryTypeFilter || undefined, pageParam),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: Boolean(projectId),
  })
  const items = knowledge.data?.pages.flatMap((page) => page.items) ?? []
  const resetForm = () => {
    setSelectedId('')
    setEntryId('')
    setEntryVersion(null)
    setTitle('')
    setCategory('workflow')
    setSubcategory('')
    setSummary('')
    setContent('')
    setTags(DEFAULT_TAGS)
    setCitation('')
    setOriginalCitation('')
    setEntrySource({})
    setReviewStatus('unknown')
  }
  const loadEntry = (item: CopilotKnowledgeEntry) => {
    setSelectedId(item.knowledge_entry_id)
    setEntryId(item.knowledge_entry_id)
    setEntryVersion(item.version)
    setTitle(item.title)
    setCategory(item.category)
    setSubcategory(item.subcategory ?? '')
    setSummary(item.summary)
    setContent(item.content)
    setTags((item.tags_json ?? []).join(', '))
    setCitation(item.citation ?? '')
    setOriginalCitation(item.citation ?? '')
    setEntrySource(item.source ?? {})
    setReviewStatus(item.review_status ?? 'unknown')
  }
  const payload = () => ({
    knowledge_entry_id: entryId.trim() || undefined,
    title: title.trim(),
    category: category.trim(),
    subcategory: subcategory.trim() || undefined,
    summary: summary.trim(),
    content: content.trim(),
    tags: commaList(tags),
    source: entrySource,
    source_type: selectedId ? undefined : 'manual',
    citation: selectedId && citation === originalCitation ? undefined : citation.trim(),
    confidence: 'unassessed',
    review_status: 'pending_review',
    metadata: { entry_mode: 'manual', source_language: language },
  })
  const save = useMutation({
    mutationFn: () => selectedId && entryVersion !== null
      ? updateCopilotKnowledgeEntry(selectedId, payload(), entryVersion)
      : createCopilotKnowledgeEntry(projectId, payload()),
    onSuccess: (item) => {
      loadEntry(item)
      client.invalidateQueries({ queryKey: ['copilot-knowledge', projectId] })
      client.invalidateQueries({ queryKey: ['research-workspace', projectId] })
    },
  })
  const archive = useMutation({
    mutationFn: () => archiveCopilotKnowledgeEntry(selectedId, entryVersion ?? 0),
    onSuccess: () => {
      resetForm()
      client.invalidateQueries({ queryKey: ['copilot-knowledge', projectId] })
      client.invalidateQueries({ queryKey: ['research-workspace', projectId] })
    },
  })

  return (
    <div className="grid min-h-0 gap-4 lg:h-[calc(100vh-12rem)] lg:grid-cols-[360px_1fr]">
      <Frame className="min-h-[28rem] lg:min-h-0" spacing="sm">
        <FramePanel className="flex min-h-0 flex-col">
          <FrameHeader>
            <FrameTitle className="flex items-center gap-2"><BookOpenTextIcon aria-hidden="true" />{k.title}</FrameTitle>
            <FrameDescription>{activeProject ? k.searchPlaceholderActive : k.searchPlaceholderInactive}</FrameDescription>
          </FrameHeader>
          <div className="mt-3 flex gap-2">
            <Input className="min-w-0 flex-1" maxLength={500} aria-label={language === 'zh' ? '检索项目知识' : 'Search project knowledge'} placeholder={activeProject ? k.searchPlaceholderActive : k.searchPlaceholderInactive} value={query} onChange={(event) => setQuery(event.target.value)} />
            <Button type="button" variant="outline" size="icon-sm" aria-label={k.searchAction} onClick={() => knowledge.refetch()}>
              <MagnifyingGlassIcon aria-hidden="true" />
            </Button>
          </div>
          <Input className="mt-2" maxLength={80} value={entryTypeFilter} onChange={(event) => setEntryTypeFilter(event.target.value)} aria-label={language === 'zh' ? '按知识类型筛选' : 'Filter entry type'} placeholder={language === 'zh' ? '类型筛选，例如 copilot_draft（留空为全部）' : 'Entry type, e.g. copilot_draft (blank for all)'} />
          <p className="mt-2 text-xs text-muted-foreground">{language === 'zh' ? '在整个项目的标题、正文和标签中按字面检索；留空浏览全部。' : 'Literal search across this project’s titles, content and tags. Leave blank to browse all.'}</p>
          <ScrollArea className="mt-3 min-h-0 flex-1">
            <div className="grid gap-2 pr-2">
              {items.map((item) => (
                <Button
                  key={item.knowledge_entry_id}
                  type="button"
                  variant={selectedId === item.knowledge_entry_id ? 'secondary' : 'outline'}
                  className="h-auto w-full justify-start whitespace-normal p-3 text-left"
                  onClick={() => loadEntry(item)}
                >
                  <span className="min-w-0">
                    <strong className="block truncate">{item.title}</strong>
                    <span className="mt-1 line-clamp-2 block text-xs text-muted-foreground">{item.summary}</span>
                    <Badge className="mt-2" variant="info-light" size="xs">{item.category}</Badge>
                    <span className="ml-2 text-xs text-muted-foreground">{item.review_status ?? 'unknown'}</span>
                  </span>
                </Button>
              ))}
              {knowledge.isPending && projectId ? <p role="status" className="text-xs text-muted-foreground">{k.loading}</p> : null}
              {knowledge.isSuccess && !items.length ? <p className="text-xs text-muted-foreground">{k.noResults}</p> : null}
              {knowledge.hasNextPage ? <Button type="button" variant="outline" disabled={knowledge.isFetchingNextPage} onClick={() => knowledge.fetchNextPage()}>{language === 'zh' ? '加载更多知识条目' : 'Load more knowledge'}</Button> : null}
              {knowledge.isError ? <Alert variant="destructive"><AlertDescription>{k.searchFailed}</AlertDescription></Alert> : null}
            </div>
          </ScrollArea>
        </FramePanel>
      </Frame>
      <Frame className="min-h-[32rem] lg:min-h-0" spacing="sm">
        <FramePanel className="flex min-h-0 flex-col">
          <FrameHeader className="flex-row items-center justify-between">
            <FrameTitle>{selectedId ? k.editEntry : k.addEntry}</FrameTitle>
            <Button type="button" variant="outline" size="sm" onClick={resetForm}>{k.newEntry}</Button>
          </FrameHeader>
          <ScrollArea className="mt-3 min-h-0 flex-1">
            {selectedId ? <div className="mb-3 grid gap-2"><p className="text-xs text-muted-foreground">{language === 'zh' ? '已记录的复核状态' : 'Recorded review status'} · {reviewStatus}</p><Disclosure title={language === 'zh' ? '原始来源与引用记录' : 'Original source and citation record'}><pre className="max-h-52 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(entrySource, null, 2)}</pre></Disclosure></div> : null}
            <div className="grid gap-3 pr-2 md:grid-cols-2">
              <div className="grid gap-1"><Label htmlFor="knowledge-entry-id">{k.entryIdLabel}</Label><Input id="knowledge-entry-id" value={entryId} disabled={Boolean(selectedId)} onChange={(event) => setEntryId(event.target.value)} placeholder={k.entryIdPlaceholder} /></div>
              <div className="grid gap-1"><Label htmlFor="knowledge-category">{k.categoryLabel}</Label><Input id="knowledge-category" value={category} onChange={(event) => setCategory(event.target.value)} /></div>
              <div className="grid gap-1 md:col-span-2"><Label htmlFor="knowledge-title">{k.titleLabel}</Label><Input id="knowledge-title" value={title} onChange={(event) => setTitle(event.target.value)} /></div>
              <div className="grid gap-1"><Label htmlFor="knowledge-subcategory">{k.subcategoryLabel}</Label><Input id="knowledge-subcategory" value={subcategory} onChange={(event) => setSubcategory(event.target.value)} /></div>
              <div className="grid gap-1"><Label htmlFor="knowledge-tags">{k.tagsLabel}</Label><Input id="knowledge-tags" value={tags} onChange={(event) => setTags(event.target.value)} /></div>
              <div className="grid gap-1 md:col-span-2"><Label htmlFor="knowledge-summary">{k.summaryLabel}</Label><Textarea id="knowledge-summary" className="min-h-20" value={summary} onChange={(event) => setSummary(event.target.value)} /></div>
              <div className="grid gap-1 md:col-span-2"><Label htmlFor="knowledge-content">{k.contentLabel}</Label><Textarea id="knowledge-content" className="min-h-44" value={content} onChange={(event) => setContent(event.target.value)} /></div>
              <div className="grid gap-1 md:col-span-2"><Label htmlFor="knowledge-citation">{k.citationLabel}</Label><Input id="knowledge-citation" value={citation} onChange={(event) => setCitation(event.target.value)} /></div>
            </div>
          </ScrollArea>
          {!canEdit ? <Alert className="mt-3"><AlertDescription>{k.permissionHint}</AlertDescription></Alert> : null}
          {save.isSuccess ? <Alert className="mt-2" variant="success" role="status"><AlertDescription>{k.savedSuccess}</AlertDescription></Alert> : null}
          {save.isError || archive.isError ? <Alert className="mt-2" variant="destructive" role="alert"><AlertDescription>{(save.error ?? archive.error) instanceof Error ? (save.error ?? archive.error)?.message : k.actionFailed}</AlertDescription></Alert> : null}
          <p className="mt-2 text-xs text-muted-foreground">{language === 'zh' ? '保存后的新增或修改内容进入待复核，不会自动标为已认可；原始来源字段会保留。' : 'New or edited content is saved for review, never automatically marked curated. Original source fields are retained.'}</p>
          <FrameFooter className="mt-4 flex-row flex-wrap">
            <Button type="button" disabled={!canEdit || save.isPending || archive.isPending || !title.trim() || !summary.trim() || !content.trim()} onClick={() => save.mutate()}>
              {save.isPending ? <SpinnerGapIcon className="animate-spin" aria-hidden="true" /> : <FloppyDiskIcon aria-hidden="true" />}{k.save}
            </Button>
            <Button type="button" variant="outline" disabled={!canEdit || !selectedId || save.isPending || archive.isPending} onClick={() => archive.mutate()}>
              <ArchiveIcon aria-hidden="true" />{k.archive}
            </Button>
          </FrameFooter>
        </FramePanel>
      </Frame>
    </div>
  )
}
