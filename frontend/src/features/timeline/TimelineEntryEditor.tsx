import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'
import { useI18n } from '../../lib/i18n'
import {
  createTimelineEntry,
  deleteTimelineEntry,
  updateTimelineEntry,
} from '../../lib/api/timeline'
import {
  PROVENANCE_KEYS,
  TIMELINE_ENTRY_TYPES,
  TIMELINE_LANES,
  TIMELINE_OUTCOMES,
  type ProvenanceKey,
  type TimelineEntry,
} from '../../lib/schemas/timeline'
import {
  draftFromEntry,
  draftToBody,
  emptyDraft,
  validateDraft,
  type DraftError,
  type TimelineEntryDraft,
} from './timelineEntryForm'

/**
 * Write a decision record from the UI.
 *
 * Until this existed, every entry in the two research projects arrived through a seeder
 * script in a private overlay - which meant the most valuable part of the record (the
 * criterion, the STOP, the unit mismatch) could only be changed by editing Python. The
 * fields here are the ones that separate a decision record from a diary, so they are
 * structured inputs rather than one prose box: `provenance` offers the eight allowed
 * keys by name, and an alternative cannot be saved without the reason it was rejected.
 *
 * Errors are shown per field before the request goes out (see `timelineEntryForm`), and
 * a 412 is surfaced as "reload and re-apply" rather than being retried - overwriting
 * someone else's edit is the one outcome this form must never produce.
 */

interface Props {
  projectId: string
  /** Absent when recording a new entry. */
  entry?: TimelineEntry
  onClose: () => void
}

function errorFor(errors: DraftError[], field: string): DraftError | undefined {
  return errors.find((error) => error.field === field)
}

function isConflict(error: unknown): boolean {
  const status = (error as { response?: { status?: number }; status?: number } | null)?.response?.status
    ?? (error as { status?: number } | null)?.status
  return status === 412
}

export function TimelineEntryEditor({ projectId, entry, onClose }: Props) {
  const { t, format } = useI18n()
  const tl = t.timeline
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<TimelineEntryDraft>(() =>
    entry ? draftFromEntry(entry) : emptyDraft(),
  )
  const [submitted, setSubmitted] = useState(false)

  const errors = useMemo(() => validateDraft(draft), [draft])
  // Errors appear after the first save attempt, not while someone is still typing the
  // first character of a title.
  const shown = submitted ? errors : []

  const message = (error: DraftError | undefined): string | null => {
    if (!error) return null
    switch (error.code) {
      case 'required':
        return tl.errRequired
      case 'too_long':
        return format(tl.errTooLong, { limit: String(error.limit ?? 0) })
      case 'bad_timestamp':
        return tl.errBadTimestamp
      case 'lane_evidence_missing':
        return tl.errLaneEvidence
      case 'alternative_incomplete':
        return tl.errAlternativeIncomplete
    }
  }

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ['project-timeline', projectId] })
    await queryClient.invalidateQueries({ queryKey: ['research-goals', projectId] })
  }

  const save = useMutation({
    mutationFn: async () => {
      const body = draftToBody(draft)
      return entry
        ? updateTimelineEntry(entry.id, entry.version, body)
        : createTimelineEntry(projectId, body)
    },
    onSuccess: async () => {
      await invalidate()
      onClose()
    },
  })

  const remove = useMutation({
    mutationFn: () => deleteTimelineEntry(entry!.id, entry!.version),
    onSuccess: async () => {
      await invalidate()
      onClose()
    },
  })

  const submit = () => {
    setSubmitted(true)
    if (errors.length) return
    save.mutate()
  }

  const set = (patch: Partial<TimelineEntryDraft>) =>
    setDraft((current) => ({ ...current, ...patch }))

  const setProvenance = (key: ProvenanceKey, value: string) =>
    setDraft((current) => ({ ...current, provenance: { ...current.provenance, [key]: value } }))

  const failure = save.error ?? remove.error
  const busy = save.isPending || remove.isPending

  return (
    <section
      className="mt-3 rounded-md border border-border-soft bg-surface-2 p-4"
      aria-label={entry ? tl.editorHeadingEdit : tl.editorHeadingNew}
    >
      <h3 className="text-sm font-semibold text-text-primary">
        {entry ? tl.editorHeadingEdit : tl.editorHeadingNew}
      </h3>
      <p className="mt-1 text-xs text-text-secondary">{tl.editorIntro}</p>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <label className="grid gap-1 text-xs text-text-secondary">
          {tl.fieldTitle}
          <Input
            value={draft.title}
            onChange={(event) => set({ title: event.target.value })}
            aria-label={tl.fieldTitle}
            aria-invalid={Boolean(errorFor(shown, 'title'))}
          />
          {message(errorFor(shown, 'title')) ? (
            <span className="text-warning">{message(errorFor(shown, 'title'))}</span>
          ) : null}
        </label>

        <label className="grid gap-1 text-xs text-text-secondary">
          {tl.fieldOccurredAt}
          <Input
            type="datetime-local"
            value={draft.occurred_at}
            onChange={(event) => set({ occurred_at: event.target.value })}
            aria-label={tl.fieldOccurredAt}
            aria-invalid={Boolean(errorFor(shown, 'occurred_at'))}
          />
          {message(errorFor(shown, 'occurred_at')) ? (
            <span className="text-warning">{message(errorFor(shown, 'occurred_at'))}</span>
          ) : null}
        </label>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-4">
        <label className="grid gap-1 text-xs text-text-secondary">
          {tl.fieldType}
          <Select
            value={draft.entry_type}
            onValueChange={(value) => set({ entry_type: (value ?? 'decision') as TimelineEntryDraft['entry_type'] })}
          >
            <SelectTrigger aria-label={tl.fieldType}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TIMELINE_ENTRY_TYPES.map((value) => (
                <SelectItem key={value} value={value}>
                  {tl.type[value]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>

        <label className="grid gap-1 text-xs text-text-secondary">
          {tl.fieldOutcome}
          <Select
            value={draft.outcome}
            onValueChange={(value) => set({ outcome: (value ?? 'unspecified') as TimelineEntryDraft['outcome'] })}
          >
            <SelectTrigger aria-label={tl.fieldOutcome}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TIMELINE_OUTCOMES.map((value) => (
                <SelectItem key={value} value={value}>
                  {tl.outcome[value]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>

        <label className="grid gap-1 text-xs text-text-secondary">
          {tl.fieldLane}
          <Select
            value={draft.lane}
            onValueChange={(value) => set({ lane: (value ?? 'unspecified') as TimelineEntryDraft['lane'] })}
          >
            <SelectTrigger aria-label={tl.fieldLane}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TIMELINE_LANES.map((value) => (
                <SelectItem key={value} value={value}>
                  {tl.lane[value]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>

        <label className="grid gap-1 text-xs text-text-secondary">
          {tl.fieldPhase}
          <Input
            value={draft.phase}
            onChange={(event) => set({ phase: event.target.value })}
            aria-label={tl.fieldPhase}
          />
          {message(errorFor(shown, 'phase')) ? (
            <span className="text-warning">{message(errorFor(shown, 'phase'))}</span>
          ) : null}
        </label>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <label className="grid gap-1 text-xs text-text-secondary">
          {tl.fieldDecisionRef}
          <Input
            value={draft.decision_ref}
            onChange={(event) => set({ decision_ref: event.target.value })}
            aria-label={tl.fieldDecisionRef}
          />
          <span className="text-text-muted">{tl.fieldDecisionRefHelp}</span>
          {message(errorFor(shown, 'decision_ref')) ? (
            <span className="text-warning">{message(errorFor(shown, 'decision_ref'))}</span>
          ) : null}
        </label>

        <label className="grid gap-1 text-xs text-text-secondary">
          {tl.fieldTags}
          <Input
            value={draft.tags}
            onChange={(event) => set({ tags: event.target.value })}
            aria-label={tl.fieldTags}
          />
          <span className="text-text-muted">{tl.fieldTagsHelp}</span>
        </label>
      </div>

      <label className="mt-3 grid gap-1 text-xs text-text-secondary">
        {tl.fieldSummary}
        <Textarea
          rows={2}
          value={draft.summary}
          onChange={(event) => set({ summary: event.target.value })}
          aria-label={tl.fieldSummary}
        />
      </label>

      <label className="mt-3 grid gap-1 text-xs text-text-secondary">
        {tl.fieldBody}
        <Textarea
          rows={6}
          value={draft.body}
          onChange={(event) => set({ body: event.target.value })}
          aria-label={tl.fieldBody}
        />
        <span className="text-text-muted">{tl.fieldBodyHelp}</span>
      </label>

      <fieldset className="mt-4 rounded-md border border-border-soft p-3">
        <legend className="px-1 text-xs font-medium text-text-primary">{tl.sectionProvenance}</legend>
        <p className="text-[11px] text-text-muted">{tl.sectionProvenanceHelp}</p>
        <div className="mt-2 grid gap-2 md:grid-cols-2">
          {PROVENANCE_KEYS.map((key) => (
            <label key={key} className="grid gap-1 text-xs text-text-secondary">
              {tl.provenanceKey[key]}
              <Textarea
                rows={2}
                value={draft.provenance[key]}
                onChange={(event) => setProvenance(key, event.target.value)}
                aria-label={tl.provenanceKey[key]}
              />
            </label>
          ))}
        </div>
        {message(errorFor(shown, 'provenance')) ? (
          <p className="mt-2 text-xs text-warning">{message(errorFor(shown, 'provenance'))}</p>
        ) : null}
      </fieldset>

      <fieldset className="mt-4 rounded-md border border-border-soft p-3">
        <legend className="px-1 text-xs font-medium text-text-primary">{tl.sectionAlternatives}</legend>
        <p className="text-[11px] text-text-muted">{tl.sectionAlternativesHelp}</p>
        {draft.alternatives.map((alternative, index) => (
          <div key={index} className="mt-2 grid gap-2 md:grid-cols-[1fr_2fr_auto]">
            <label className="grid gap-1 text-xs text-text-secondary">
              {tl.altOption}
              <Input
                value={alternative.option}
                aria-label={`${tl.altOption} ${index + 1}`}
                onChange={(event) =>
                  set({
                    alternatives: draft.alternatives.map((item, n) =>
                      n === index ? { ...item, option: event.target.value } : item,
                    ),
                  })
                }
              />
              {message(errorFor(shown, `alternatives.${index}.option`)) ? (
                <span className="text-warning">
                  {message(errorFor(shown, `alternatives.${index}.option`))}
                </span>
              ) : null}
            </label>
            <label className="grid gap-1 text-xs text-text-secondary">
              {tl.altRejectedBecause}
              <Textarea
                rows={2}
                value={alternative.rejected_because}
                aria-label={`${tl.altRejectedBecause} ${index + 1}`}
                onChange={(event) =>
                  set({
                    alternatives: draft.alternatives.map((item, n) =>
                      n === index ? { ...item, rejected_because: event.target.value } : item,
                    ),
                  })
                }
              />
              {message(errorFor(shown, `alternatives.${index}.rejected_because`)) ? (
                <span className="text-warning">
                  {message(errorFor(shown, `alternatives.${index}.rejected_because`))}
                </span>
              ) : null}
            </label>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="self-end"
              onClick={() =>
                set({ alternatives: draft.alternatives.filter((_, n) => n !== index) })
              }
            >
              {tl.rowRemove}
            </Button>
          </div>
        ))}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="mt-2 px-0 text-xs"
          onClick={() =>
            set({ alternatives: [...draft.alternatives, { option: '', rejected_because: '' }] })
          }
        >
          {tl.altAdd}
        </Button>
      </fieldset>

      <fieldset className="mt-4 rounded-md border border-border-soft p-3">
        <legend className="px-1 text-xs font-medium text-text-primary">{tl.sectionCodeRefs}</legend>
        {draft.code_refs.map((ref, index) => (
          <div key={index} className="mt-2 grid gap-2 md:grid-cols-[2fr_2fr_auto]">
            <label className="grid gap-1 text-xs text-text-secondary">
              {tl.codeRefPath}
              <Input
                value={ref.path}
                aria-label={`${tl.codeRefPath} ${index + 1}`}
                onChange={(event) =>
                  set({
                    code_refs: draft.code_refs.map((item, n) =>
                      n === index ? { ...item, path: event.target.value } : item,
                    ),
                  })
                }
              />
              {message(errorFor(shown, `code_refs.${index}.path`)) ? (
                <span className="text-warning">
                  {message(errorFor(shown, `code_refs.${index}.path`))}
                </span>
              ) : null}
            </label>
            <label className="grid gap-1 text-xs text-text-secondary">
              {tl.codeRefRole}
              <Input
                value={ref.role}
                aria-label={`${tl.codeRefRole} ${index + 1}`}
                onChange={(event) =>
                  set({
                    code_refs: draft.code_refs.map((item, n) =>
                      n === index ? { ...item, role: event.target.value } : item,
                    ),
                  })
                }
              />
            </label>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="self-end"
              onClick={() => set({ code_refs: draft.code_refs.filter((_, n) => n !== index) })}
            >
              {tl.rowRemove}
            </Button>
          </div>
        ))}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="mt-2 px-0 text-xs"
          onClick={() => set({ code_refs: [...draft.code_refs, { path: '', role: '' }] })}
        >
          {tl.codeRefAdd}
        </Button>
      </fieldset>

      {failure ? (
        <p role="alert" className="mt-3 text-xs text-warning">
          {isConflict(failure) ? tl.editorConflict : tl.editorSaveFailed}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" onClick={submit} disabled={busy}>
          {save.isPending ? tl.editorSaving : tl.editorSave}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onClose} disabled={busy}>
          {tl.editorCancel}
        </Button>
        {entry ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="ml-auto text-warning"
            disabled={busy}
            onClick={() => {
              if (window.confirm(tl.editorDeleteConfirm)) remove.mutate()
            }}
          >
            {tl.editorDelete}
          </Button>
        ) : null}
      </div>
    </section>
  )
}
