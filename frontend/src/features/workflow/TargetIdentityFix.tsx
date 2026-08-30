import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { confirmTargetIdentity } from '../../lib/api/projects'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Label } from '../../components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'

interface TargetIdentityFixProps {
  projectId: string
  /** Prefilled from the project so the common case is one click, not one form. */
  defaultName?: string
}

type Kind = 'protein' | 'small_molecule'
type ProteinBy = 'accession' | 'sequence'
type ChemicalBy = 'ccd' | 'inchikey' | 'smiles'

/**
 * Lets a target actually reach `identity_status = 'confirmed'` from the UI.
 *
 * The previous confirm flow only ever submitted a UniProt accession, so two perfectly
 * ordinary targets could never be confirmed and left the Workflow page permanently
 * read-only:
 *
 *  - a de novo / synthetic protein, whose identity IS its sequence (there is no accession);
 *  - a small-molecule target, identified by a chemical identifier and - by design - never
 *    carrying uploaded coordinates, because the model resolves them from its own
 *    component library at run time.
 *
 * Shown at the point where the user actually hits the wall (the readiness blocker on the
 * Workflow page) rather than behind a link into the protein structure flow, which cannot
 * help a ligand target at all.
 */
export function TargetIdentityFix({ projectId, defaultName }: TargetIdentityFixProps) {
  const { t } = useI18n()
  const tf = t.workflowExt.routePlanner.targetIdentityFix
  const client = useQueryClient()
  const showToast = useToastStore((s) => s.show)

  const [name, setName] = useState(defaultName ?? '')
  const [kind, setKind] = useState<Kind>('protein')
  const [proteinBy, setProteinBy] = useState<ProteinBy>('accession')
  const [chemicalBy, setChemicalBy] = useState<ChemicalBy>('ccd')
  const [value, setValue] = useState('')

  const trimmedName = name.trim()
  const trimmedValue = value.trim()
  const canSubmit = Boolean(trimmedName && trimmedValue)

  const confirm = useMutation({
    mutationFn: () =>
      confirmTargetIdentity(projectId, {
        target_name: trimmedName,
        target_kind: kind,
        ...(kind === 'protein'
          ? proteinBy === 'accession'
            ? { uniprot_accession: trimmedValue }
            : { sequence: trimmedValue }
          : { chemical_identity: { [chemicalBy]: trimmedValue } }),
      }),
    onSuccess: (result) => {
      // Readiness is what gates the whole page, so it must be refetched before the user
      // is told anything succeeded.
      client.invalidateQueries({ queryKey: ['target-readiness', projectId] })
      client.invalidateQueries({ queryKey: ['project-overview', projectId] })
      client.invalidateQueries({ queryKey: ['project-target-structure', projectId] })
      const ready = result?.readiness?.ready_for_workflow === true
      showToast(ready ? tf.successReady : tf.successNotReady, ready ? 'success' : 'info')
    },
    onError: (error) => {
      showToast(error instanceof Error ? error.message : tf.failed, 'error')
    },
  })

  const label =
    kind === 'protein'
      ? proteinBy === 'accession'
        ? tf.accessionLabel
        : tf.sequenceLabel
      : tf.chemicalValueLabel

  return (
    <div className="mt-3 space-y-2 rounded-md border border-border-soft bg-bg-app p-3">
      <p className="text-xs text-text-secondary">{tf.intro}</p>

      <div className="grid gap-2 md:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="tif-name" className="text-xs">
            {tf.nameLabel}
          </Label>
          <Input
            id="tif-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={tf.namePlaceholder}
          />
        </div>

        <div className="space-y-1">
          <Label className="text-xs">{tf.kindLabel}</Label>
          <Select
            value={kind}
            onValueChange={(next) => {
              setKind((next as Kind) ?? 'protein')
              setValue('')
            }}
          >
            <SelectTrigger aria-label={tf.kindLabel}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="protein">{tf.kindProtein}</SelectItem>
              <SelectItem value="small_molecule">{tf.kindSmallMolecule}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-xs">{tf.identifiedByLabel}</Label>
          {kind === 'protein' ? (
            <Select
              value={proteinBy}
              onValueChange={(next) => {
                setProteinBy((next as ProteinBy) ?? 'accession')
                setValue('')
              }}
            >
              <SelectTrigger aria-label={tf.identifiedByLabel}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="accession">{tf.byAccession}</SelectItem>
                <SelectItem value="sequence">{tf.bySequence}</SelectItem>
              </SelectContent>
            </Select>
          ) : (
            <Select
              value={chemicalBy}
              onValueChange={(next) => {
                setChemicalBy((next as ChemicalBy) ?? 'ccd')
                setValue('')
              }}
            >
              <SelectTrigger aria-label={tf.identifiedByLabel}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ccd">{tf.byCcd}</SelectItem>
                <SelectItem value="inchikey">{tf.byInchikey}</SelectItem>
                <SelectItem value="smiles">{tf.bySmiles}</SelectItem>
              </SelectContent>
            </Select>
          )}
        </div>

        <div className="space-y-1">
          <Label htmlFor="tif-value" className="text-xs">
            {label}
          </Label>
          <Input
            id="tif-value"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder={kind === 'small_molecule' && chemicalBy === 'ccd' ? tf.ccdPlaceholder : ''}
          />
        </div>
      </div>

      {kind === 'small_molecule' ? (
        <p className="text-[11px] text-text-muted">{tf.smallMoleculeNote}</p>
      ) : null}

      <Button
        type="button"
        size="sm"
        disabled={!canSubmit || confirm.isPending}
        onClick={() => confirm.mutate()}
      >
        {confirm.isPending ? tf.submitting : tf.submit}
      </Button>
    </div>
  )
}
