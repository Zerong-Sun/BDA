import { Badge } from '@/components/reui/badge'
import { Frame, FramePanel } from '@/components/reui/frame'
import type { StructureSource } from './types'
import { useI18n } from '../../lib/i18n'

interface StructureMetadataPanelProps {
  source: StructureSource
  className?: string
}

export function StructureMetadataPanel({ source, className }: StructureMetadataPanelProps) {
  const { t } = useI18n()
  const v = t.viewer

  const hasMeta =
    source.proteinName ||
    source.pdbId ||
    source.alphafoldId ||
    source.atomCount != null ||
    source.chains?.length ||
    source.confidenceScore != null ||
    source.designScore != null ||
    source.ligands?.length

  if (!hasMeta) return null

  return (
    <Frame className={`mb-2 ${className ?? ''}`} spacing="xs">
      <FramePanel className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      {source.proteinName ? (
        <span className="font-medium text-text-primary">{source.proteinName}</span>
      ) : null}
      {source.pdbId ? (
        <Badge variant="outline" size="sm">{source.pdbId.toUpperCase()}</Badge>
      ) : null}
      {source.alphafoldId ? (
        <Badge variant="info-light" size="sm">{source.alphafoldId}</Badge>
      ) : null}
      {source.atomCount != null ? (
        <span>
          {v.atoms} {source.atomCount}
        </span>
      ) : null}
      {source.chains?.length ? (
        <span>
          {v.chains} {source.chains.join(', ')}
        </span>
      ) : null}
      {source.ligands?.length ? (
        <span>
          {v.ligands} {source.ligands.map((ligand) => ligand.name ?? ligand.id).join(', ')}
        </span>
      ) : null}
      {source.confidenceScore != null ? (
        <span>
          {v.confidenceScore} {source.confidenceScore.toFixed(1)}
        </span>
      ) : null}
      {source.designScore != null ? (
        <span>
          {v.designScore} {source.designScore.toFixed(1)}
        </span>
      ) : null}
      </FramePanel>
    </Frame>
  )
}
