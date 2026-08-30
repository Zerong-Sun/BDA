import { useMemo, useState } from 'react'
import {
  createColumnHelper,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table'
import { DownloadSimpleIcon } from '@phosphor-icons/react'
import { DataGrid, DataGridContainer } from '../../components/reui/data-grid/data-grid'
import { DataGridColumnHeader } from '../../components/reui/data-grid/data-grid-column-header'
import { DataGridScrollArea } from '../../components/reui/data-grid/data-grid-scroll-area'
import { DataGridTable } from '../../components/reui/data-grid/data-grid-table'
import { Button } from '../../components/ui/Button'
import type { Artifact } from '../../lib/schemas/artifact'
import type { Candidate } from '../../lib/schemas/candidate'
import { useI18n } from '../../lib/i18n'

interface AlphaFoldResultsProps {
  candidates: Candidate[]
  artifacts: Artifact[]
  onDownload: (artifact: Artifact) => void
}

const alphaFoldColumnHelper = createColumnHelper<Candidate>()

function numericScore(candidate: Candidate, key: string): number | null {
  const value = candidate.scores[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function textProperty(candidate: Candidate, key: string): string {
  const value = candidate.properties[key]
  return typeof value === 'string' ? value : '—'
}

function confidenceClass(plddt: number): 'veryHigh' | 'confident' | 'low' | 'veryLow' {
  if (plddt >= 90) return 'veryHigh'
  if (plddt >= 70) return 'confident'
  if (plddt >= 50) return 'low'
  return 'veryLow'
}

export function AlphaFoldResults({
  candidates,
  artifacts,
  onDownload,
}: AlphaFoldResultsProps) {
  const { t } = useI18n()
  const copy = t.resultsExt.alphaFoldResults
  const rows = useMemo(() => candidates
    .filter((candidate) => numericScore(candidate, 'plddt') !== null)
    .sort((left, right) => (
      (numericScore(right, 'plddt') ?? -1) - (numericScore(left, 'plddt') ?? -1)
      || left.name.localeCompare(right.name)
    )), [candidates])

  const plddtValues = rows.map((candidate) => numericScore(candidate, 'plddt') ?? 0)
  const meanPlddt = plddtValues.reduce((sum, value) => sum + value, 0) / rows.length
  const confidentCount = plddtValues.filter((value) => value >= 70).length
  const veryHighCount = plddtValues.filter((value) => value >= 90).length
  const lowCount = plddtValues.filter((value) => value < 70).length
  const bestCandidate = rows[0]
  const alphaFoldArtifacts = useMemo(() => artifacts.filter(
    (artifact) => artifact.lineage.method === 'AlphaFold2',
  ), [artifacts])
  const summaryArtifacts = useMemo(() => alphaFoldArtifacts
    .filter((artifact) => !artifact.lineage.candidate_key)
    .sort((left, right) => left.filename.localeCompare(right.filename)), [alphaFoldArtifacts])
  const artifactsById = useMemo(
    () => new Map(alphaFoldArtifacts.map((artifact) => [artifact.id, artifact])),
    [alphaFoldArtifacts],
  )
  const confidenceByCandidate = useMemo(() => new Map(
    alphaFoldArtifacts
      .filter((artifact) => artifact.artifact_type === 'confidence_record')
      .map((artifact) => [String(artifact.lineage.candidate_key), artifact]),
  ), [alphaFoldArtifacts])
  const [sorting, setSorting] = useState<SortingState>([])
  const columns = useMemo(() => [
    alphaFoldColumnHelper.accessor('name', {
      header: ({ column }) => <DataGridColumnHeader column={column} title={copy.candidate} />,
      meta: { cellClassName: 'font-medium text-text-primary' },
      size: 240,
    }),
    alphaFoldColumnHelper.accessor((candidate) => textProperty(candidate, 'route'), {
      id: 'route',
      header: ({ column }) => <DataGridColumnHeader column={column} title={copy.route} />,
      size: 120,
    }),
    alphaFoldColumnHelper.accessor((candidate) => numericScore(candidate, 'plddt') ?? 0, {
      id: 'plddt',
      header: ({ column }) => <DataGridColumnHeader column={column} title="pLDDT" />,
      cell: ({ getValue }) => getValue().toFixed(2),
      size: 96,
    }),
    alphaFoldColumnHelper.accessor((candidate) => numericScore(candidate, 'ptm'), {
      id: 'ptm',
      header: ({ column }) => <DataGridColumnHeader column={column} title="pTM" />,
      cell: ({ getValue }) => getValue()?.toFixed(3) ?? '—',
      size: 96,
    }),
    alphaFoldColumnHelper.accessor((candidate) => numericScore(candidate, 'mean_pae'), {
      id: 'mean_pae',
      header: ({ column }) => <DataGridColumnHeader column={column} title={copy.meanPae} />,
      cell: ({ getValue }) => getValue()?.toFixed(2) ?? '—',
      size: 112,
    }),
    alphaFoldColumnHelper.accessor(
      (candidate) => numericScore(candidate, 'alphafold_summary_rmsd_to_input')
        ?? numericScore(candidate, 'alphafold_rmsd_to_input'),
      {
        id: 'rmsd',
        header: ({ column }) => <DataGridColumnHeader column={column} title={copy.rmsd} />,
        cell: ({ getValue }) => getValue()?.toFixed(2) ?? '—',
        size: 96,
      },
    ),
    alphaFoldColumnHelper.accessor(
      (candidate) => confidenceClass(numericScore(candidate, 'plddt') ?? 0),
      {
        id: 'quality',
        header: ({ column }) => <DataGridColumnHeader column={column} title={copy.quality} />,
        cell: ({ getValue }) => copy.qualityLabels[getValue()],
        size: 140,
      },
    ),
    alphaFoldColumnHelper.display({
      id: 'raw_results',
      header: ({ column }) => <DataGridColumnHeader column={column} title={copy.rawResults} />,
      cell: ({ row }) => {
        const candidate = row.original
        const structure = candidate.structure_artifact_id
          ? artifactsById.get(candidate.structure_artifact_id)
          : undefined
        const confidence = confidenceByCandidate.get(candidate.candidate_key)
        return (
          <div className="flex gap-1.5">
            {structure ? (
              <Button type="button" variant="outline" size="xs" onClick={() => onDownload(structure)}>
                PDB
              </Button>
            ) : null}
            {confidence ? (
              <Button type="button" variant="outline" size="xs" onClick={() => onDownload(confidence)}>
                JSON
              </Button>
            ) : null}
          </div>
        )
      },
      size: 132,
    }),
  ], [artifactsById, confidenceByCandidate, copy, onDownload])
  // TanStack Table intentionally exposes mutable function references.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getRowId: (candidate) => candidate.id,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  if (rows.length === 0) return null

  return (
    <article className="mb-5 overflow-hidden rounded-lg border border-border-soft bg-surface-1">
      <div className="border-b border-border-soft p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-text-primary">{copy.title}</h2>
            <p className="mt-1 text-sm text-text-secondary">{copy.description}</p>
          </div>
          <span className="rounded-full border border-warning/40 bg-warning/10 px-2.5 py-1 text-xs text-text-secondary">
            {(rows.length >= 1000 ? copy.completeCoverage : copy.partialCoverage)
              .replace('{count}', String(rows.length))}
          </span>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-md bg-surface-2 p-3">
            <p className="text-xs text-text-secondary">{copy.predictions}</p>
            <p className="mt-1 text-xl font-semibold text-text-primary">{rows.length}</p>
          </div>
          <div className="rounded-md bg-surface-2 p-3">
            <p className="text-xs text-text-secondary">{copy.meanPlddt}</p>
            <p className="mt-1 text-xl font-semibold text-text-primary">{meanPlddt.toFixed(2)}</p>
          </div>
          <div className="rounded-md bg-surface-2 p-3">
            <p className="text-xs text-text-secondary">{copy.confident}</p>
            <p className="mt-1 text-xl font-semibold text-text-primary">{confidentCount}</p>
          </div>
          <div className="rounded-md bg-surface-2 p-3">
            <p className="text-xs text-text-secondary">{copy.lowConfidence}</p>
            <p className="mt-1 text-xl font-semibold text-text-primary">{lowCount}</p>
          </div>
        </div>

        <div className="mt-4 rounded-md border border-border-soft bg-surface-2 p-3 text-sm text-text-secondary">
          <p>
            {copy.analysis
              .replace('{confident}', String(confidentCount))
              .replace('{total}', String(rows.length))
              .replace('{veryHigh}', String(veryHighCount))}
          </p>
          <p className="mt-1">
            {copy.bestPrediction
              .replace('{candidate}', bestCandidate.name)
              .replace('{plddt}', (numericScore(bestCandidate, 'plddt') ?? 0).toFixed(2))
              .replace('{ptm}', numericScore(bestCandidate, 'ptm')?.toFixed(3) ?? '—')
              .replace('{pae}', numericScore(bestCandidate, 'mean_pae')?.toFixed(2) ?? '—')}
          </p>
          <p className="mt-1">{copy.metricCaveat}</p>
        </div>

        {summaryArtifacts.length > 0 ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {summaryArtifacts.map((artifact) => (
              <Button
                key={artifact.id}
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onDownload(artifact)}
              >
                <DownloadSimpleIcon aria-hidden="true" />
                {artifact.filename}
              </Button>
            ))}
          </div>
        ) : null}
      </div>

      <DataGrid
        table={table}
        recordCount={rows.length}
        tableLayout={{ dense: true, headerBackground: true, headerBorder: true, rowBorder: true }}
      >
        <DataGridContainer>
          <DataGridScrollArea orientation="horizontal">
            <DataGridTable />
          </DataGridScrollArea>
        </DataGridContainer>
      </DataGrid>
    </article>
  )
}
