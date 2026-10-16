import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ChatCircleDotsIcon,
  PlusIcon,
  Network,
  WarningIcon,
  XIcon,
} from '@phosphor-icons/react'
import { Alert, AlertDescription, AlertTitle } from '../../components/reui/alert'
import { Badge } from '../../components/reui/badge'
import { Button } from '../../components/ui/Button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../../components/ui/dialog'
import { Input } from '../../components/ui/Input'
import { Label } from '../../components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'
import { Textarea } from '../../components/ui/textarea'
import { Disclosure } from '../../components/ui/Disclosure'
import { upsertProjectResearchFinding, type ResearchFindingUpsertPayload } from '../../lib/api/projects'
import { type NormalizedResearchWorkspace, workspaceText } from '../../lib/api/researchWorkspace'
import type { ProjectReviewSection } from '../../lib/schemas/research'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { projectText } from '../../lib/i18n/projectText'
import { useAppStore } from '../../lib/store/appStore'
import { findingCitationRecords, findingCitationSources, workspaceCitationRecords } from './findingCitations'
import { text } from './jsonHelpers'
import { ReviewMarkdown } from './ReviewMarkdown'
import { isReviewTrack, REVIEW_SECTION_ORDER, reviewSectionLabel } from './reviewTracks'
import { localizeToken, shouldTruncateReviewStatement } from './researchUi'
import { filterReviewSections, READING_STAGES } from './reviewReading'

interface AddNoteState {
  track: string
  title: string
  statement: string
  sourceRefs: string
  uncertainty: string
}

const emptyNote = (track = ''): AddNoteState => ({
  track,
  title: '',
  statement: '',
  sourceRefs: '',
  uncertainty: '',
})

function sourceTokens(value: string): string[] {
  return value.split(/\n|,/).map((item) => item.trim()).filter(Boolean)
}

function latestUpdated(sections: ProjectReviewSection[]): string {
  return sections
    .flatMap((section) => section.items.map((item) => text(item.updated_at) || text(item.created_at)))
    .filter(Boolean)
    .sort()
    .at(-1) || '—'
}

// Evidence provenance is not a review decision. Only the recorded review_status
// may say that a person or process reviewed this finding.
function evidenceLabel(level: string, fallback: string, zh: boolean): string {
  if (level === 'research_seed') return zh ? '初始研究资料' : 'Research seed'
  if (level === 'curated_review') return zh ? '整理的综述资料' : 'Curated review material'
  return level ? level.replaceAll('_', ' ') : fallback
}

function findingHeading(section: ProjectReviewSection, statement: string, rawTitle: string): string {
  const title = rawTitle.trim()
  if (!title || title === section.label || title === section.track) return ''
  // Keep source prose intact. Suppress only a presentation title already present
  // as the opening paragraph or Markdown heading, never remove evidence text.
  const opening = statement.trim().replace(/^#{1,6}[ \t]+/, '')
  return opening === title || (opening.startsWith(title) && /^[\s.!?。！？]/.test(opening.slice(title.length))) ? '' : title
}

export function ProjectReviewPanel({
  workspace,
  showDocument = true,
  readOnly = false,
}: {
  workspace: NormalizedResearchWorkspace
  showDocument?: boolean
  readOnly?: boolean
}) {
  const { t, format, language } = useI18n()
  const r = t.research.projectReview
  const client = useQueryClient()
  const navigate = useNavigate()
  const { projectId, activeProject } = useProjectContext()
  const setCopilotOpen = useAppStore((state) => state.setCopilotOpen)
  const setCopilotDraft = useAppStore((state) => state.setCopilotDraft)
  const setWorkflowSeed = useAppStore((state) => state.setWorkflowSeed)
  const [selectedTrack, setSelectedTrack] = useState('')
  const [note, setNote] = useState<AddNoteState>(emptyNote())
  const [readingStage, setReadingStage] = useState('all')
  const [readingQuery, setReadingQuery] = useState('')

  const brief = workspace.review_document
  const briefTitle = brief ? workspaceText(brief.title, language) : ''
  const briefContent = brief ? workspaceText(brief.content, language) : ''
  const sections = useMemo(() => {
    const grouped = new Map(workspace.review_sections.map((section) => [section.track, section]))
    const tracks = [
      ...REVIEW_SECTION_ORDER,
      ...workspace.review_sections.map((section) => section.track).filter((track) => !isReviewTrack(track)),
    ]
    return tracks.map((track): ProjectReviewSection => ({
      track,
      label: isReviewTrack(track) ? reviewSectionLabel(track, language) : track.replaceAll('_', ' '),
      status: 'active',
      items: (grouped.get(track)?.items ?? []).map((item) => ({
        id: item.id,
        project_id: projectId,
        brief_id: brief?.id ?? null,
        finding_type: item.finding_type,
        title: workspaceText(item.title, language),
        content: workspaceText(item.content, language),
        evidence: item.evidence ?? {},
        version: item.version,
        created_at: item.created_at,
        updated_at: item.updated_at,
        // Workspace review items carry no resolution of their own; claiming one here
        // would put an outcome on the record that nobody stated.
        outcome: 'unspecified',
        supersedes_id: null,
        provenance: {},
      })),
    }))
  }, [brief?.id, language, projectId, workspace.review_sections])
  const populatedSections = sections.filter((section) => section.items.length > 0)
  const visibleSections = filterReviewSections(sections, readingStage, readingQuery)
  const zh = language === 'zh'
  const actionTrack = selectedTrack || populatedSections[0]?.track || sections[0]?.track || ''
  const actionSection = sections.find((section) => section.track === actionTrack)
  const sources = new Set(
    populatedSections.flatMap((section) => section.items.flatMap((item) => (
      findingCitationSources(item.evidence)
    ))),
  )

  const saveNote = useMutation({
    mutationFn: () => {
      const payload: ResearchFindingUpsertPayload = {
        finding_type: note.track,
        title: note.title.trim(),
        content: note.statement.trim(),
        brief_id: brief?.id ?? null,
        evidence: {
          evidence_level: 'user_note',
          source_refs: sourceTokens(note.sourceRefs),
          uncertainty: note.uncertainty.trim() || null,
          review_status: 'pending_review',
          source_language: language,
          localized_content: {
            title: { [language]: note.title.trim() },
            content: { [language]: note.statement.trim() },
          },
        },
      }
      return upsertProjectResearchFinding(projectId, payload)
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['project-research-summary', projectId] })
      client.invalidateQueries({ queryKey: ['research-workspace', projectId] })
      setNote(emptyNote())
    },
  })

  const askCopilot = () => {
    if (!actionSection) return
    const projectName = activeProject ? projectText(activeProject, 'name', language) : projectId
    const prompt = [
      format(r.copilotPromptIntro, { project: projectName, section: actionSection.label }),
      r.copilotPromptEvidence,
      r.copilotPromptFormat,
      actionSection.track === 'references_reading' ? r.copilotPromptReferences : r.copilotPromptSynthesis,
      r.copilotPromptOutput,
    ].join('\n')
    setCopilotDraft(prompt)
    setCopilotOpen(true)
  }

  const convertToWorkflow = () => {
    const keyFindings = (actionSection?.items ?? populatedSections.flatMap((section) => section.items))
      .slice(0, 6)
      .map((item) => `- ${item.title}: ${item.content.split('\n')[0]}`)
      .join('\n')
    const goal = [
      briefContent || (activeProject ? projectText(activeProject, 'summary', language) : '') || r.fallbackObjective,
      actionSection ? `${r.workflowSeedSection}: ${actionSection.label}` : r.workflowSeedAll,
      keyFindings ? `${r.workflowSeedFindings}\n${keyFindings}` : '',
    ].filter(Boolean).join('\n\n')
    setWorkflowSeed({ projectId, goal, source: 'research_review' })
    navigate(`/workflow?project=${encodeURIComponent(projectId)}`)
  }

  if (!projectId) return null

  return (
    <Dialog
      open={Boolean(note.track)}
      onOpenChange={(open) => {
        if (!open) setNote(emptyNote())
      }}
    >
      <section className="min-w-0">
      <section className="mb-5 border-b border-border-soft pb-5" aria-label={zh ? '研究阅读导览' : 'Research reading guide'}>
        <p className="text-xs uppercase tracking-wide text-accent">{zh ? '理解研究，再作判断' : 'From question to decision'}</p>
        <h3 className="mt-1 text-lg font-semibold">{zh ? '这项研究为什么做，下一步凭什么继续？' : 'Why this research, and what would justify the next step?'}</h3>
        <p className="mt-2 text-sm text-text-secondary">{zh ? '按问题、机制、路线和验证阅读。记录数量表示文档覆盖，不代表科学结论已经成立。' : 'Read the question, mechanism, route and validation together. Record counts describe documentation, not scientific validation.'}</p>
        <div className="mt-4 grid grid-cols-2 gap-2 lg:grid-cols-3 xl:grid-cols-6" role="group" aria-label={zh ? '按研究环节筛选' : 'Filter by research stage'}>
          {READING_STAGES.map((stage, index) => {
            const count = sections.filter((section) => (stage.tracks as readonly string[]).includes(section.track)).reduce((sum, section) => sum + section.items.length, 0)
            return <Button key={stage.id} type="button" variant="outline" aria-pressed={readingStage === stage.id} onClick={() => { setReadingStage(stage.id); setSelectedTrack(stage.tracks[0]) }} className={`h-auto flex-col items-start gap-0 rounded-lg p-3 text-left whitespace-normal ${readingStage === stage.id ? 'border-accent bg-accent/10' : 'border-border-soft hover:bg-bg-app'}`}>
              <span className="font-mono text-xs text-text-muted">0{index + 1}</span>
              <span className="mt-1 block text-sm font-medium text-text-primary">{stage[language]}</span>
              <span className="mt-1 block text-xs text-text-secondary">{count ? `${count} ${zh ? '条记录' : 'records'}` : (zh ? '暂无记录' : 'No records yet')}</span>
            </Button>
          })}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" variant="outline" aria-pressed={readingStage === 'all'} onClick={() => { setReadingStage('all'); setReadingQuery('') }}>{zh ? '全部记录' : 'All records'}</Button>
          <Input className="min-w-0 flex-1 sm:min-w-60" value={readingQuery} onChange={(event) => setReadingQuery(event.target.value)} aria-label={zh ? '搜索研究记录' : 'Search research records'} placeholder={zh ? '搜索结论、疑点或来源…' : 'Search conclusions, uncertainties or sources…'} />
        </div>
      </section>
      {showDocument && briefContent ? (
        <div className="mb-5 border-b border-border-soft pb-5">
          <p className="text-xs uppercase tracking-wide text-accent">{r.eyebrow}</p>
          <h3 className="mt-1 text-lg font-semibold">{briefTitle || r.fallbackTitle}</h3>
          <div className="mt-3"><ReviewMarkdown citations={workspaceCitationRecords(workspace.references, language)}>{briefContent}</ReviewMarkdown></div>
        </div>
      ) : null}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="font-semibold text-text-primary">{r.notesTitle}</h3>
          <p className="mt-1 text-xs text-text-muted">
            {format(r.documentMeta, {
              sources: sources.size,
              completed: populatedSections.length,
              total: sections.length,
              updated: latestUpdated(populatedSections),
            })}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2" aria-label={r.sectionActionsLabel}>
          <Select
            value={actionTrack}
            onValueChange={(value) => setSelectedTrack(value ?? '')}
          >
            <SelectTrigger aria-label={r.chooseSection}>
              <SelectValue>{actionSection?.label}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {sections.map((section) => <SelectItem key={section.track} value={section.track}>{section.label}</SelectItem>)}
            </SelectContent>
          </Select>
          <DialogTrigger
            render={<Button type="button" variant="outline" size="sm" disabled={readOnly} onClick={() => setNote(emptyNote(actionTrack))} />}
          >
            <PlusIcon aria-hidden="true" />{r.addFinding}
          </DialogTrigger>
          <Button type="button" variant="outline" size="sm" onClick={askCopilot}>
            <ChatCircleDotsIcon aria-hidden="true" />{r.askSelectedSection}
          </Button>
          <Button type="button" size="sm" disabled={readOnly} onClick={convertToWorkflow}>
            <Network aria-hidden="true" />{r.convertSection}
          </Button>
        </div>
      </div>

      {visibleSections.length ? (
        <div className="mt-6 space-y-7">
          {visibleSections.map((section) => (
            <section key={section.track} aria-label={section.label}>
              <header className="mb-1 flex items-baseline justify-between gap-3 border-b border-border-soft pb-2">
                <h3 className="font-semibold text-text-primary">{section.label}</h3>
                <span className="text-xs text-text-muted">{format(r.itemsCount, { count: section.items.length })}</span>
              </header>
              <div className="divide-y divide-border-soft">
                {section.items.map((item, index) => {
                  const statement = item.content
                  const title = findingHeading(section, statement, item.title)
                  const long = shouldTruncateReviewStatement(statement)
                  const reviewStatus = text(item.evidence.review_status)
                  return (
                    <article key={item.id} className="min-w-0 py-4" data-testid="research-finding" data-finding-id={item.id}>
                      {title || long ? <h4 className="mb-2 text-sm font-semibold text-text-primary">{title || format(r.findingFallbackTitle, { number: index + 1 })}</h4> : null}
                      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                        <Badge variant="secondary" size="xs">{reviewStatus ? localizeToken(reviewStatus, t.research.enums) : (zh ? '审阅状态未记录' : 'Review status not recorded')}</Badge>
                        <span className="text-text-muted">{evidenceLabel(text(item.evidence.evidence_level), r.evidence, zh)}</span>
                      </div>
                      {long ? (
                        <Disclosure title={format(r.longStatement, { count: Array.from(statement).length })}>
                          <ReviewMarkdown compactCitations citations={findingCitationRecords(item.evidence)} projectId={projectId}>{statement}</ReviewMarkdown>
                        </Disclosure>
                      ) : (
                        <ReviewMarkdown compactCitations citations={findingCitationRecords(item.evidence)} projectId={projectId}>{statement}</ReviewMarkdown>
                      )}
                      {text(item.evidence.uncertainty) ? (
                        <Alert className="mt-3" variant="warning">
                          <WarningIcon aria-hidden="true" />
                          <AlertTitle>{r.uncertainty}</AlertTitle>
                          <AlertDescription>{text(item.evidence.uncertainty)}</AlertDescription>
                        </Alert>
                      ) : null}
                      <Disclosure className="mt-2 text-xs text-text-muted" title={zh ? '记录信息' : 'Record information'}>
                        <p>{zh ? '记录 ID：' : 'Record ID: '}{item.id}</p>
                        <p>{zh ? '记录更新时间：' : 'Record updated: '}{text(item.updated_at) || text(item.created_at) || '—'}</p>
                      </Disclosure>
                    </article>
                  )
                })}
              </div>
            </section>
          ))}
        </div>
      ) : <Alert className="mt-5"><AlertDescription>{readingQuery || readingStage !== 'all' ? (zh ? '当前筛选下没有记录。可清除筛选，或为所选环节补充依据；缺少记录不等于研究失败。' : 'No records match this view. Clear the filters or add evidence for this stage; missing documentation is not a failed study.') : r.notesEmpty}</AlertDescription></Alert>}
      </section>

      {note.track ? (
        <DialogContent showCloseButton={false} className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{r.addingTo} {sections.find((section) => section.track === note.track)?.label ?? note.track}</DialogTitle>
            <DialogDescription>{r.usageAdd}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="grid gap-1">
              <Label htmlFor="review-note-title">{r.noteTitle}</Label>
              <Input id="review-note-title" autoFocus value={note.title} onChange={(event) => setNote({ ...note, title: event.target.value })} />
            </div>
            <div className="grid gap-1">
              <Label htmlFor="review-note-sources">{r.noteSources}</Label>
              <Input id="review-note-sources" value={note.sourceRefs} onChange={(event) => setNote({ ...note, sourceRefs: event.target.value })} placeholder={r.noteSourcesPlaceholder} />
            </div>
            <div className="grid gap-1 lg:col-span-2">
              <Label htmlFor="review-note-statement">{r.noteStatement}</Label>
              <Textarea id="review-note-statement" className="min-h-28" value={note.statement} onChange={(event) => setNote({ ...note, statement: event.target.value })} />
            </div>
            <div className="grid gap-1 lg:col-span-2">
              <Label htmlFor="review-note-uncertainty">{r.noteUncertainty}</Label>
              <Input id="review-note-uncertainty" value={note.uncertainty} onChange={(event) => setNote({ ...note, uncertainty: event.target.value })} />
            </div>
          </div>
          {saveNote.isError ? <Alert variant="destructive"><AlertDescription>{r.saveFailed}</AlertDescription></Alert> : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setNote(emptyNote())}>
              <XIcon aria-hidden="true" />{r.close}
            </Button>
            <Button type="button" disabled={!note.title.trim() || !note.statement.trim() || saveNote.isPending} onClick={() => saveNote.mutate()}>
              {r.saveNote}
            </Button>
          </DialogFooter>
        </DialogContent>
      ) : null}
    </Dialog>
  )
}
