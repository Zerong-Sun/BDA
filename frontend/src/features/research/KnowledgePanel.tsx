import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
import { useI18n } from '../../lib/i18n'
import { commaList, currentRole } from './jsonHelpers'
import { projectKnowledgeQuery } from './projectSearch'

const DEFAULT_TAGS = 'manual, curated'

export function KnowledgePanel() {
  const { t, language } = useI18n()
  const k = t.research.knowledge
  const client = useQueryClient()
  const { activeProject, projectId } = useProjectContext()
  const isAdmin = currentRole() === 'admin'
  const canEdit = isAdmin || currentRole() === 'researcher'
  const defaultQuery = useMemo(() => projectKnowledgeQuery(activeProject), [activeProject])
  const [query, setQuery] = useState('')
  const autoQueryRef = useRef('')
  const projectIdRef = useRef('')
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
  const [citation, setCitation] = useState(k.defaultCitation)
  const knowledge = useQuery({
    queryKey: ['copilot-knowledge', projectId, query],
    queryFn: () => searchCopilotKnowledge(projectId, query),
    enabled: Boolean(projectId && query.trim()),
  })
  useEffect(() => {
    const projectChanged = projectIdRef.current !== projectId
    if (projectChanged || !query.trim() || query === autoQueryRef.current) {
      setQuery(defaultQuery)
      autoQueryRef.current = defaultQuery
    }
    projectIdRef.current = projectId
  }, [defaultQuery, projectId, query])
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
    setCitation(k.defaultCitation)
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
  }
  const payload = () => ({
    knowledge_entry_id: entryId.trim() || undefined,
    title: title.trim(),
    category: category.trim(),
    subcategory: subcategory.trim() || undefined,
    summary: summary.trim(),
    content: content.trim(),
    tags: commaList(tags),
    source_type: 'curated',
    citation: citation.trim() || undefined,
    confidence: 'curated',
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
            <Input className="min-w-0 flex-1" placeholder={activeProject ? k.searchPlaceholderActive : k.searchPlaceholderInactive} value={query} onChange={(event) => setQuery(event.target.value)} />
            <Button type="button" variant="outline" size="icon-sm" aria-label={k.searchAction} onClick={() => knowledge.refetch()}>
              <MagnifyingGlassIcon aria-hidden="true" />
            </Button>
          </div>
          <ScrollArea className="mt-3 min-h-0 flex-1">
            <div className="grid gap-2 pr-2">
              {knowledge.data?.items.map((item) => (
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
                  </span>
                </Button>
              ))}
              {knowledge.isPending ? <p role="status" className="text-xs text-muted-foreground">{k.loading}</p> : null}
              {knowledge.isSuccess && !knowledge.data.items.length ? <p className="text-xs text-muted-foreground">{k.noResults}</p> : null}
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
          {save.isError || archive.isError ? <Alert className="mt-2" variant="destructive" role="alert"><AlertDescription>{k.actionFailed}</AlertDescription></Alert> : null}
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
