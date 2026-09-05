import {
  PROVENANCE_KEYS,
  TIMELINE_ENTRY_TYPES,
  TIMELINE_LANES,
  TIMELINE_OUTCOMES,
  WET_PROVENANCE_KEYS,
  type ProvenanceKey,
  type TimelineEntry,
} from '../../lib/schemas/timeline'

/**
 * The form model behind the timeline entry editor, and the rules it enforces.
 *
 * Pure on purpose. The rules here mirror `backend_v2/app/timeline/schemas.py`, and a
 * mirror that nobody can test drifts from its original within one release - so the
 * mirroring lives in functions a unit test can call, not inside a component where
 * checking it means rendering a dialog.
 *
 * Mirroring rather than trusting the 422 is itself a decision. The server is still the
 * authority and still rejects a bad body; what the client adds is that a researcher
 * typing a *wet* decision finds out that it needs bench evidence while the form is in
 * front of them, instead of after pressing save on twenty minutes of prose.
 */

export interface DraftAlternative {
  option: string
  rejected_because: string
}

export interface DraftCodeRef {
  path: string
  role: string
}

export interface TimelineEntryDraft {
  /** `datetime-local` value, read and written as UTC. The rest of the app renders
   *  `occurred_at` by slicing the ISO string rather than converting to local time, and
   *  an editor that silently shifted the value would make round-tripping lossy. */
  occurred_at: string
  entry_type: (typeof TIMELINE_ENTRY_TYPES)[number]
  decision_ref: string
  lane: (typeof TIMELINE_LANES)[number]
  phase: string
  title: string
  summary: string
  body: string
  outcome: (typeof TIMELINE_OUTCOMES)[number]
  /** One textarea per allowed key; ids one per line. Free-text keys are impossible by
   *  construction, which is the restriction the backend exists to keep. */
  provenance: Record<ProvenanceKey, string>
  alternatives: DraftAlternative[]
  code_refs: DraftCodeRef[]
  /** Comma or whitespace separated. */
  tags: string
}

/** Field length caps, from the backend column definitions and Pydantic constraints. */
export const LIMITS = {
  title: 300,
  decision_ref: 40,
  phase: 80,
  option: 300,
  rejected_because: 2000,
  code_ref_path: 400,
  code_ref_role: 200,
} as const

export type DraftErrorCode =
  | 'required'
  | 'too_long'
  | 'bad_timestamp'
  | 'lane_evidence_missing'
  | 'alternative_incomplete'

export interface DraftError {
  /** Dotted path: `title`, `alternatives.0.rejected_because`, `provenance`. */
  field: string
  code: DraftErrorCode
  /** Present on `too_long`, so the message can say by how much. */
  limit?: number
}

function emptyProvenance(): Record<ProvenanceKey, string> {
  return Object.fromEntries(PROVENANCE_KEYS.map((key) => [key, ''])) as Record<ProvenanceKey, string>
}

/** A blank draft. `occurred_at` defaults to now (UTC, minute precision) because an entry
 *  written today about work done today is the common case; back-dating is one edit. */
export function emptyDraft(now: Date = new Date()): TimelineEntryDraft {
  return {
    occurred_at: now.toISOString().slice(0, 16),
    entry_type: 'decision',
    decision_ref: '',
    lane: 'unspecified',
    phase: '',
    title: '',
    summary: '',
    body: '',
    outcome: 'unspecified',
    provenance: emptyProvenance(),
    alternatives: [],
    code_refs: [],
    tags: '',
  }
}

/** Load an existing entry into the form. Unknown provenance keys are dropped rather than
 *  carried through a round trip the backend would refuse anyway. */
export function draftFromEntry(entry: TimelineEntry): TimelineEntryDraft {
  const provenance = emptyProvenance()
  for (const key of PROVENANCE_KEYS) {
    const value = entry.provenance[key]
    if (Array.isArray(value)) {
      provenance[key] = value.filter((item): item is string => typeof item === 'string').join('\n')
    }
  }
  return {
    occurred_at: entry.occurred_at.slice(0, 16),
    entry_type: entry.entry_type,
    decision_ref: entry.decision_ref ?? '',
    lane: entry.lane,
    phase: entry.phase,
    title: entry.title,
    summary: entry.summary,
    body: entry.body,
    outcome: entry.outcome,
    provenance,
    alternatives: entry.alternatives.map((item) => ({ ...item })),
    code_refs: entry.code_refs.map((item) => ({ path: item.path, role: item.role ?? '' })),
    tags: entry.tags.join(', '),
  }
}

function idList(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function packProvenance(draft: TimelineEntryDraft): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const key of PROVENANCE_KEYS) {
    const ids = idList(draft.provenance[key] ?? '')
    if (ids.length) out[key] = ids
  }
  return out
}

/** Rows where *both* halves are blank are treated as never having been filled in and are
 *  dropped silently; a row with one half filled is an error, not a row to discard. That
 *  split matters: "add row, change your mind" must not block saving, while "named an
 *  option and forgot why it was rejected" must. */
function meaningfulAlternatives(draft: TimelineEntryDraft): Array<{ index: number; value: DraftAlternative }> {
  return draft.alternatives
    .map((value, index) => ({ index, value }))
    .filter(({ value }) => value.option.trim() !== '' || value.rejected_because.trim() !== '')
}

function meaningfulCodeRefs(draft: TimelineEntryDraft): Array<{ index: number; value: DraftCodeRef }> {
  return draft.code_refs
    .map((value, index) => ({ index, value }))
    .filter(({ value }) => value.path.trim() !== '' || value.role.trim() !== '')
}

/** `YYYY-MM-DDTHH:mm`, then a real calendar date.
 *
 *  The shape check is not redundant with `Date.parse`: V8 falls back to a lenient parser
 *  that reads `"not-a-date:00Z"` as 2000-01-01 rather than returning NaN, so parsing
 *  alone would let a pasted or scripted value through as a silently wrong timestamp. */
function isDatetimeLocal(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return false
  const parsed = Date.parse(`${value}:00Z`)
  if (Number.isNaN(parsed)) return false
  // Round-trip so an out-of-range day (2026-02-31) is rejected rather than rolled over.
  return new Date(parsed).toISOString().slice(0, 16) === value
}

/**
 * Everything the server would reject, found before the request goes out.
 *
 * The lane rule is the one worth stating twice: a *settled* `wet` or `both` decision has
 * to name bench evidence. It is checked on the merged row, exactly as the backend's
 * `check_lane_evidence` does, and it deliberately does not apply to an open decision -
 * writing down a question before answering it must stay possible.
 */
export function validateDraft(draft: TimelineEntryDraft): DraftError[] {
  const errors: DraftError[] = []

  if (!draft.title.trim()) errors.push({ field: 'title', code: 'required' })
  else if (draft.title.trim().length > LIMITS.title)
    errors.push({ field: 'title', code: 'too_long', limit: LIMITS.title })

  if (draft.decision_ref.trim().length > LIMITS.decision_ref)
    errors.push({ field: 'decision_ref', code: 'too_long', limit: LIMITS.decision_ref })

  if (draft.phase.trim().length > LIMITS.phase)
    errors.push({ field: 'phase', code: 'too_long', limit: LIMITS.phase })

  if (!isDatetimeLocal(draft.occurred_at)) errors.push({ field: 'occurred_at', code: 'bad_timestamp' })

  for (const { index, value } of meaningfulAlternatives(draft)) {
    if (!value.option.trim())
      errors.push({ field: `alternatives.${index}.option`, code: 'alternative_incomplete' })
    else if (value.option.trim().length > LIMITS.option)
      errors.push({ field: `alternatives.${index}.option`, code: 'too_long', limit: LIMITS.option })
    if (!value.rejected_because.trim())
      errors.push({ field: `alternatives.${index}.rejected_because`, code: 'alternative_incomplete' })
    else if (value.rejected_because.trim().length > LIMITS.rejected_because)
      errors.push({
        field: `alternatives.${index}.rejected_because`,
        code: 'too_long',
        limit: LIMITS.rejected_because,
      })
  }

  for (const { index, value } of meaningfulCodeRefs(draft)) {
    if (!value.path.trim()) errors.push({ field: `code_refs.${index}.path`, code: 'required' })
    else if (value.path.trim().length > LIMITS.code_ref_path)
      errors.push({ field: `code_refs.${index}.path`, code: 'too_long', limit: LIMITS.code_ref_path })
    if (value.role.trim().length > LIMITS.code_ref_role)
      errors.push({ field: `code_refs.${index}.role`, code: 'too_long', limit: LIMITS.code_ref_role })
  }

  if (
    draft.entry_type === 'decision' &&
    (draft.lane === 'wet' || draft.lane === 'both') &&
    draft.outcome !== 'unspecified'
  ) {
    const provenance = packProvenance(draft)
    const hasBench = WET_PROVENANCE_KEYS.some((key) => (provenance[key] ?? []).length > 0)
    if (!hasBench) errors.push({ field: 'provenance', code: 'lane_evidence_missing' })
  }

  return errors
}

interface EntryBody {
  occurred_at: string
  entry_type: string
  decision_ref: string | null
  lane: string
  phase: string
  title: string
  summary: string
  body: string
  outcome: string
  provenance: Record<string, string[]>
  alternatives: DraftAlternative[]
  code_refs: DraftCodeRef[]
  tags: string[]
}

/** The wire body. `decision_ref` collapses blank to `null` for the same reason the
 *  backend's validator does: two entries holding `""` would collide on the unique
 *  constraint, and NULL is the real "no number". */
export function draftToBody(draft: TimelineEntryDraft): EntryBody {
  return {
    occurred_at: `${draft.occurred_at}:00Z`,
    entry_type: draft.entry_type,
    decision_ref: draft.decision_ref.trim() || null,
    lane: draft.lane,
    phase: draft.phase.trim(),
    title: draft.title.trim(),
    summary: draft.summary.trim(),
    body: draft.body,
    outcome: draft.outcome,
    provenance: packProvenance(draft),
    alternatives: meaningfulAlternatives(draft).map(({ value }) => ({
      option: value.option.trim(),
      rejected_because: value.rejected_because.trim(),
    })),
    code_refs: meaningfulCodeRefs(draft).map(({ value }) => ({
      path: value.path.trim(),
      role: value.role.trim(),
    })),
    tags: draft.tags
      .split(/[,\s]+/)
      .map((tag) => tag.trim())
      .filter(Boolean),
  }
}
