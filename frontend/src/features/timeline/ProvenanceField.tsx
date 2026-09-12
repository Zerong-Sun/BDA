import { useQuery } from '@tanstack/react-query'
import { Checkbox } from '../../components/ui/checkbox'
import { Label } from '../../components/ui/label'
import { Textarea } from '../../components/ui/textarea'
import { useI18n } from '../../lib/i18n'
import type { ProvenanceKey } from '../../lib/schemas/timeline'
import { PROVENANCE_SOURCES, unresolvableIds } from './provenanceSources'

/**
 * One provenance key's editor: a chooser when the platform can list the thing, a checked
 * text field when it cannot, and a plain one for the key that names things the platform
 * does not own.
 *
 * The point is the absence of a text box, not the presence of a list. A free-text field is
 * answered with whatever the writer has to hand - which is how 49 LSF job numbers ended up
 * in `external_refs` as strings nothing can resolve, while `artifact_ids` stayed empty.
 * Offering the real rows makes the addressable answer the easy one; removing the box makes
 * it the only one.
 *
 * Selected ids that are not in the loaded list are still rendered, as ids. An entry may
 * cite a row that has since been filtered out or deleted, and silently dropping it on the
 * next save would quietly rewrite the record.
 */

interface ProvenanceFieldProps {
  fieldKey: ProvenanceKey
  projectId: string | null
  /** Newline/comma separated, as the draft stores it. */
  value: string
  onChange: (next: string) => void
}

function idsOf(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

export function ProvenanceField({ fieldKey, projectId, value, onChange }: ProvenanceFieldProps) {
  const { t, format } = useI18n()
  const tl = t.timeline
  const source = PROVENANCE_SOURCES[fieldKey]
  const label = tl.provenanceKey[fieldKey]
  const selected = idsOf(value)

  const options = useQuery({
    queryKey: ['provenance-options', fieldKey, projectId],
    queryFn: () => source.load!(projectId as string),
    enabled: source.kind === 'pick' && Boolean(projectId),
    staleTime: 60_000,
  })

  if (source.kind !== 'pick') {
    const stray = source.kind === 'id' ? unresolvableIds(value) : []
    return (
      <label className="grid gap-1 text-xs text-text-secondary">
        {label}
        <Textarea
          rows={2}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-label={label}
        />
        <span className="text-[11px] text-text-muted">
          {source.kind === 'free' ? tl.provenanceFreeHelp : tl.provenanceIdHelp}
        </span>
        {stray.length ? (
          <span className="text-[11px] text-warning">
            {format(tl.provenanceNotAddressable, { items: stray.join(', ') })}
          </span>
        ) : null}
      </label>
    )
  }

  const loaded = options.data ?? []
  const known = new Set(loaded.map((option) => option.id))
  const orphans = selected.filter((id) => !known.has(id))

  const toggle = (id: string, on: boolean) => {
    const next = on ? [...selected, id] : selected.filter((item) => item !== id)
    onChange(next.join('\n'))
  }

  return (
    <fieldset className="grid gap-1 text-xs text-text-secondary">
      <legend className="text-xs text-text-secondary">{label}</legend>
      {options.isLoading ? <span className="text-text-muted">{tl.loading}</span> : null}
      {options.isError ? <span className="text-warning">{tl.provenanceLoadFailed}</span> : null}
      {!options.isLoading && !options.isError && loaded.length === 0 ? (
        <span className="text-[11px] text-text-muted">{tl.provenanceNothingToCite}</span>
      ) : null}
      <div className="max-h-40 overflow-y-auto">
        {loaded.map((option) => (
          <div key={option.id} className="flex items-start gap-1.5 py-0.5">
            <Checkbox
              id={`prov-${fieldKey}-${option.id}`}
              checked={selected.includes(option.id)}
              onCheckedChange={(checked) => toggle(option.id, checked === true)}
            />
            <Label
              htmlFor={`prov-${fieldKey}-${option.id}`}
              className="text-[11px] font-normal leading-tight"
            >
              {option.label}
              {option.detail ? (
                <span className="ml-1 text-text-muted">· {option.detail}</span>
              ) : null}
            </Label>
          </div>
        ))}
      </div>
      {orphans.length ? (
        // Kept, not dropped: an entry may cite a row that has since been filtered out or
        // deleted, and losing it on the next save would rewrite the record silently.
        <span className="font-mono text-[11px] text-text-muted">
          {format(tl.provenanceUnlisted, { items: orphans.join(', ') })}
        </span>
      ) : null}
    </fieldset>
  )
}
