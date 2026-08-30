import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowSquareOutIcon,
  ChatCircleDotsIcon,
  PlusIcon,
  Network,
  WarningIcon,
  XIcon,
} from '@phosphor-icons/react'
import { Alert, AlertDescription, AlertTitle } from '../../components/reui/alert'
import { Badge } from '../../components/reui/badge'
import {
  Frame,
  FrameDescription,
  FrameHeader,
  FramePanel,
  FrameTitle,
} from '../../components/reui/frame'
import {
  Timeline,
  TimelineContent,
  TimelineDate,
  TimelineHeader,
  TimelineIndicator,
  TimelineItem,
  TimelineSeparator,
  TimelineTitle,
} from '../../components/reui/timeline'
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
import { upsertProjectResearchFinding, type ResearchFindingUpsertPayload } from '../../lib/api/projects'
import { type NormalizedResearchWorkspace, workspaceText } from '../../lib/api/researchWorkspace'
import type { ProjectReviewSection } from '../../lib/schemas/research'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { projectText } from '../../lib/i18n/projectText'
import { useAppStore } from '../../lib/store/appStore'
import { findingCitationSources } from './findingCitations'
import { formatCitation } from './formatCitation'
import { text } from './jsonHelpers'
import { firstSentenceForTitle } from './parseReviewFinding'
import { ReviewMarkdown } from './ReviewMarkdown'
import { isReviewTrack, REVIEW_SECTION_ORDER, reviewSectionLabel } from './reviewTracks'
import { localizeToken } from './researchUi'

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

function evidenceLabel(level: string, fallback: string, reviewed: string): string {
  if (!level) return fallback
  if (level === 'curated_review' || level === 'research_seed') return reviewed
  return level.replaceAll('_', ' ')
}

function formatFindingDate(value: string): string {
  return value ? value.replace('T', ' ').replace('Z', ' UTC') : ''
}

function findingTitle(section: ProjectReviewSection, statement: string, rawTitle: string, fallback: string): string {
  if (rawTitle && rawTitle !== section.label && rawTitle !== section.track) return rawTitle
  return firstSentenceForTitle(statement) || fallback
}

function CitationList({ sources, collapsedLabel }: { sources: string[]; collapsedLabel: string }) {
  return (
    <div data-testid="finding-citations" className="mt-3 flex flex-wrap gap-2">
      {sources.map((source) => {
        const citation = formatCitation(source)
        return citation.href ? (
          <a
            key={source}
            className="inline-flex items-center gap-1 rounded border border-border-soft bg-bg-app px-2 py-1 text-xs text-accent hover:border-accent/50"
            href={citation.href}
            title={citation.title}
            target="_blank"
            rel="noopener noreferrer"
          >
            <ArrowSquareOutIcon aria-hidden="true" />{citation.label}
          </a>
        ) : (
          <span key={source} className="rounded border border-border-soft bg-bg-app px-2 py-1 text-xs text-text-secondary" title={citation.title}>
            {citation.label}
          </span>
        )
      })}
      <span className="sr-only">{collapsedLabel}</span>
    </div>
  )
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
      <Frame spacing="lg">
        <FramePanel>
      {showDocument && briefContent ? (
        <div className="mb-5 border-b border-border-soft pb-5">
          <p className="text-xs uppercase tracking-wide text-accent">{r.eyebrow}</p>
          <h3 className="mt-1 text-lg font-semibold">{briefTitle || r.fallbackTitle}</h3>
          <div className="mt-3"><ReviewMarkdown>{briefContent}</ReviewMarkdown></div>
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
              <SelectValue />
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

      {populatedSections.length ? (
        <div className="mt-5 grid gap-4">
          {populatedSections.map((section) => (
            <Frame key={section.track} spacing="sm">
              <FramePanel>
                <FrameHeader className="flex-row items-center justify-between">
                  <FrameTitle>{section.label}</FrameTitle>
                  <FrameDescription>{format(r.itemsCount, { count: section.items.length })}</FrameDescription>
                </FrameHeader>
                <Timeline value={section.items.length}>
                {section.items.map((item, index) => {
                  const itemSources = findingCitationSources(item.evidence)
                  const statement = item.content
                  return (
                    <TimelineItem key={item.id} step={index + 1}>
                      <TimelineHeader>
                        <TimelineDate>{formatFindingDate(text(item.updated_at) || text(item.created_at))}</TimelineDate>
                        <TimelineTitle>{findingTitle(section, statement, item.title, format(r.findingFallbackTitle, { number: index + 1 }))}</TimelineTitle>
                      </TimelineHeader>
                      <TimelineIndicator />
                      {index < section.items.length - 1 ? <TimelineSeparator /> : null}
                      <TimelineContent>
                        <Frame spacing="xs">
                          <FramePanel data-testid="research-finding" data-finding-id={item.id}>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline" size="xs">
                          {evidenceLabel(text(item.evidence.evidence_level), r.evidence, r.reviewedEvidence)}
                        </Badge>
                        {text(item.evidence.review_status) ? <Badge variant="secondary" size="xs">{localizeToken(text(item.evidence.review_status), t.research.enums)}</Badge> : null}
                      </div>
                      <div className="mt-2"><ReviewMarkdown>{statement}</ReviewMarkdown></div>
                      {text(item.evidence.uncertainty) ? (
                        <Alert className="mt-2" variant="warning">
                          <WarningIcon aria-hidden="true" />
                          <AlertTitle>{r.uncertainty}</AlertTitle>
                          <AlertDescription>{text(item.evidence.uncertainty)}</AlertDescription>
                        </Alert>
                      ) : null}
                      {itemSources.length ? <CitationList sources={itemSources} collapsedLabel={format(r.sourcesCollapsed, { count: itemSources.length })} /> : null}
                          </FramePanel>
                        </Frame>
                      </TimelineContent>
                    </TimelineItem>
                  )
                })}
                </Timeline>
              </FramePanel>
            </Frame>
          ))}
        </div>
      ) : <Alert className="mt-5"><AlertDescription>{r.notesEmpty}</AlertDescription></Alert>}
        </FramePanel>
      </Frame>

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
