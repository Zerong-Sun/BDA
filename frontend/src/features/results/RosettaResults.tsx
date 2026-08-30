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
import type { Candidate } from '../../lib/schemas/candidate'
import type { Artifact } from '../../lib/schemas/artifact'
import { useI18n } from '../../lib/i18n'

interface RosettaResultsProps {
  candidates: Candidate[]
  artifacts: Artifact[]
  onDownload: (artifact: Artifact) => void
}

const rosettaColumnHelper = createColumnHelper<Candidate>()

function numericScore(candidate: Candidate, key: string): number | null {
  const value = candidate.scores[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function textProperty(candidate: Candidate, key: string): string {
  const value = candidate.properties[key]
  return typeof value === 'string' ? value : '—'
}

function numericProperty(candidate: Candidate, key: string): number | null {
  const value = candidate.properties[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function RosettaResults({ candidates, artifacts, onDownload }: RosettaResultsProps) {
  const { t } = useI18n()
  const copy = t.resultsExt.rosettaResults
  const rows = useMemo(() => candidates
    .filter((candidate) => numericScore(candidate, 'rosetta_score_per_residue') !== null)
    .sort((left, right) => {
      const leftRank = left.rank ?? Number.MAX_SAFE_INTEGER
      const rightRank = right.rank ?? Number.MAX_SAFE_INTEGER
      return leftRank - rightRank || left.name.localeCompare(right.name)
    }), [candidates])
  const routeCounts = rows.reduce<Record<string, number>>((counts, candidate) => {
    const route = textProperty(candidate, 'route')
    counts[route] = (counts[route] ?? 0) + 1
    return counts
  }, {})
  const routeSummary = Object.entries(routeCounts)
    .filter(([route]) => route !== '—')
    .sort(([left], [right]) => left.localeCompare(right))
  const bestScore = rows.length > 0
    ? Math.min(...rows.map((candidate) => numericScore(candidate, 'rosetta_score_per_residue') ?? Infinity))
    : null
  const resultArtifacts = useMemo(() => artifacts
    .filter((artifact) => artifact.lineage.source === 'manual_cluster_import')
    .filter((artifact) => ['Rosetta', 'ProteinMPNN'].includes(String(artifact.lineage.method)))
    .sort((left, right) => left.filename.localeCompare(right.filename)), [artifacts])
  const [sorting, setSorting] = useState<SortingState>([])
  const columns = useMemo(() => [
    rosettaColumnHelper.accessor('rank', {
      header: ({ column }) => <DataGridColumnHeader column={column} title={copy.rank} />,
      cell: ({ getValue }) => getValue() ?? '—',
      size: 80,
    }),
    rosettaColumnHelper.accessor('name', {
      header: ({ column }) => <DataGridColumnHeader column={column} title={copy.candidate} />,
      meta: { cellClassName: 'font-medium text-text-primary' },
      size: 240,
    }),
    rosettaColumnHelper.accessor((candidate) => textProperty(candidate, 'route'), {
      id: 'route',
      header: ({ column }) => <DataGridColumnHeader column={column} title={copy.route} />,
      meta: { cellClassName: 'capitalize' },
      size: 120,
    }),
    rosettaColumnHelper.accessor((candidate) => numericProperty(candidate, 'residue_count'), {
      id: 'residue_count',
      header: ({ column }) => <DataGridColumnHeader column={column} title={copy.residues} />,
      cell: ({ getValue }) => getValue() ?? '—',
      size: 104,
    }),
    rosettaColumnHelper.accessor((candidate) => numericScore(candidate, 'proteinmpnn_score'), {
      id: 'proteinmpnn_score',
      header: ({ column }) => <DataGridColumnHeader column={column} title={copy.proteinMpnn} />,
      cell: ({ getValue }) => getValue()?.toFixed(3) ?? '—',
      size: 144,
    }),
    rosettaColumnHelper.accessor((candidate) => numericScore(candidate, 'rosetta_score'), {
      id: 'rosetta_score',
      header: ({ column }) => <DataGridColumnHeader column={column} title={copy.totalReu} />,
      cell: ({ getValue }) => getValue()?.toFixed(3) ?? '—',
      size: 120,
    }),
    rosettaColumnHelper.accessor(
      (candidate) => numericScore(candidate, 'rosetta_score_per_residue'),
      {
        id: 'rosetta_score_per_residue',
        header: ({ column }) => <DataGridColumnHeader column={column} title={copy.reuPerResidue} />,
        cell: ({ getValue }) => getValue()?.toFixed(3) ?? '—',
        meta: { cellClassName: 'font-medium text-text-primary' },
        size: 152,
      },
    ),
  ], [copy])
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
          <span className="rounded-full border border-border-soft px-2.5 py-1 text-xs text-text-secondary">
            {copy.scoreOnly}
          </span>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-md bg-surface-2 p-3">
            <p className="text-xs text-text-secondary">{copy.total}</p>
            <p className="mt-1 text-xl font-semibold text-text-primary">{rows.length}</p>
          </div>
          {routeSummary.map(([route, count]) => (
            <div key={route} className="rounded-md bg-surface-2 p-3">
              <p className="truncate text-xs capitalize text-text-secondary">{route}</p>
              <p className="mt-1 text-xl font-semibold text-text-primary">{count}</p>
            </div>
          ))}
          <div className="rounded-md bg-surface-2 p-3">
            <p className="text-xs text-text-secondary">{copy.bestNormalized}</p>
            <p className="mt-1 text-xl font-semibold text-text-primary">
              {bestScore == null ? '—' : bestScore.toFixed(3)}
            </p>
          </div>
        </div>
        {resultArtifacts.length > 0 ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {resultArtifacts.map((artifact) => (
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
      <p className="border-t border-border-soft px-4 py-3 text-xs text-text-secondary">
        {copy.lowerIsBetter}
      </p>
    </article>
  )
}
