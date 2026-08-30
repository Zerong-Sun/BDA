import {
  createColumnHelper,
  functionalUpdate,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type Column,
  type OnChangeFn,
  type PaginationState,
  type RowSelectionState,
  type SortingState,
  type VisibilityState,
} from '@tanstack/react-table'
import { useId, useMemo, useState } from 'react'
import { DownloadSimpleIcon } from '@phosphor-icons/react'
import { DataGrid, DataGridContainer, useDataGrid } from '@/components/reui/data-grid/data-grid'
import { DataGridColumnHeader } from '@/components/reui/data-grid/data-grid-column-header'
import { DataGridPagination } from '@/components/reui/data-grid/data-grid-pagination'
import { DataGridScrollArea } from '@/components/reui/data-grid/data-grid-scroll-area'
import { DataGridTable } from '@/components/reui/data-grid/data-grid-table'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/Button'
import { candidateScore, candidateText, type Candidate } from '../../lib/schemas/candidate'
import { StatusPill } from '../../components/ui/StatusPill'
import { statusTone } from '../../components/ui/statusTone'
import { useI18n } from '../../lib/i18n'

const columnHelper = createColumnHelper<Candidate>()

interface CandidateTableProps {
  data: Candidate[]
  selectedId?: string
  selectedIds?: Set<string>
  onSelect: (candidate: Candidate) => void
  onToggleCandidate?: (candidateId: string) => void
  onTogglePage?: (candidateIds: string[]) => void
  onClearSelection?: () => void
  onDownloadPage?: (candidateIds: string[], pageIndex: number) => void
  isDownloading?: boolean
}

function HeaderLabel({ label, help }: { label: string; help?: string }) {
  return (
    <span className="inline-flex items-center gap-1" title={help}>
      {label}
      {help ? <span className="text-[10px] normal-case text-text-secondary">ⓘ</span> : null}
    </span>
  )
}

function GridHelpHeader<TData, TValue>({
  column,
  label,
  help,
}: {
  column: Column<TData, TValue>
  label: string
  help: string
}) {
  return (
    <div title={help}>
      <DataGridColumnHeader column={column} title={label} />
      <span className="sr-only">{help}</span>
    </div>
  )
}

function formatScore(value: number | null | undefined, notScored: string, digits = 1) {
  return typeof value === 'number' ? value.toFixed(digits) : notScored
}

function PageSelectionCheckbox({
  selectedIds,
  onTogglePage,
  selectLabel,
  clearLabel,
}: {
  selectedIds?: Set<string>
  onTogglePage?: (candidateIds: string[]) => void
  selectLabel: string
  clearLabel: string
}) {
  const { table } = useDataGrid()
  const pageIds = table.getRowModel().rows.map((row) => row.id)
  const allPageSelected = pageIds.length > 0 && pageIds.every((candidateId) => selectedIds?.has(candidateId))
  const somePageSelected = pageIds.some((candidateId) => selectedIds?.has(candidateId))

  return (
    <Checkbox
      checked={allPageSelected}
      indeterminate={somePageSelected && !allPageSelected}
      aria-label={allPageSelected ? clearLabel : selectLabel}
      onCheckedChange={() => onTogglePage?.(pageIds)}
      onClick={(event) => event.stopPropagation()}
    />
  )
}

function MetricBar({
  label,
  value,
  notScored,
  max = 100,
  invert = false,
}: {
  label: string
  value: number | null | undefined
  notScored: string
  max?: number
  invert?: boolean
}) {
  const hasValue = typeof value === 'number'
  const clamped = hasValue ? Math.max(0, Math.min(100, (value / max) * 100)) : 0
  const tone = !hasValue
    ? 'bg-border-soft'
    : invert
      ? clamped <= 25 ? 'bg-success' : clamped <= 60 ? 'bg-accent-2' : 'bg-danger'
      : clamped >= 75 ? 'bg-success' : clamped >= 45 ? 'bg-accent-2' : 'bg-danger'

  return (
    <div className="min-w-[9rem]">
      <div className="mb-1 flex items-center justify-between gap-2 text-[11px] text-text-secondary">
        <span>{label}</span>
        <span className="text-text-primary">
          {hasValue ? value.toFixed(label === 'pLDDT' ? 0 : 1) : notScored}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-border-soft">
        <div className={`${tone} h-full rounded-full`} style={{ width: `${hasValue ? clamped : 100}%` }} />
      </div>
    </div>
  )
}

export function CandidateTable({
  data,
  selectedId,
  selectedIds,
  onSelect,
  onToggleCandidate,
  onTogglePage,
  onClearSelection,
  onDownloadPage,
  isDownloading = false,
}: CandidateTableProps) {
  const { t, format } = useI18n()
  const tableDescriptionId = useId()
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'interface_score', desc: true },
  ])
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const [expertColumns, setExpertColumns] = useState(false)
  const rowSelection = useMemo<RowSelectionState>(
    () => Object.fromEntries([...selectedIds ?? []].map((candidateId) => [candidateId, true])),
    [selectedIds],
  )

  const columns = useMemo(
    () => {
      const baseColumns = [
      columnHelper.display({
        id: 'select',
        header: () => (
          <PageSelectionCheckbox
            selectedIds={selectedIds}
            onTogglePage={onTogglePage}
            selectLabel={t.candidatesExt.table.selectPageAria}
            clearLabel={t.candidatesExt.table.clearPageAria}
          />
        ),
        cell: (info) => (
          <Checkbox
            checked={selectedIds?.has(info.row.original.id) ?? false}
            aria-label={format(t.candidatesExt.table.selectCandidateAria, {
              candidateId: info.row.original.id,
            })}
            onCheckedChange={() => onToggleCandidate?.(info.row.original.id)}
            onClick={(event) => event.stopPropagation()}
          />
        ),
        enableSorting: false,
      }),
      columnHelper.accessor('id', {
        id: 'id',
        header: ({ column }) => <DataGridColumnHeader column={column} title={t.candidatesExt.table.candidate} />,
        cell: (info) => (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-current={selectedId === info.row.original.id ? 'true' : undefined}
            aria-label={format(t.candidatesExt.table.viewDetailsAria, {
              candidateId: info.row.original.id,
            })}
            className="justify-start gap-2 px-1 aria-[current=true]:text-primary"
            onClick={(event) => {
              event.stopPropagation()
              onSelect(info.row.original)
            }}
          >
            {info.getValue()}
            {candidateText(info.row.original, 'decision') === 'Anchor' ? (
              <span className="rounded border border-primary/40 bg-primary/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-primary">
                {t.candidatesExt.table.anchor}
              </span>
            ) : null}
          </Button>
        ),
      }),
      columnHelper.accessor('name', {
        id: 'family',
        header: ({ column }) => <DataGridColumnHeader column={column} title={t.candidatesExt.table.family} />,
      }),
      columnHelper.display({
        id: 'score_summary',
        header: () => (
          <HeaderLabel label={t.candidatesExt.table.scoreSummary} help={t.candidatesExt.table.scoreSummaryHelp} />
        ),
        cell: (info) => (
          <div className="grid gap-2">
            <MetricBar
              label={t.candidatesExt.table.interface}
              value={candidateScore(info.row.original, 'interface_score') ?? info.row.original.score}
              notScored={t.candidatesExt.table.notScored}
            />
            <MetricBar
              label={t.candidatesExt.table.plddt}
              value={candidateScore(info.row.original, 'plddt')}
              notScored={t.candidatesExt.table.notScored}
            />
            <MetricBar
              label="PAE"
              value={candidateScore(info.row.original, 'interface_pae')}
              notScored={t.candidatesExt.table.notScored}
              max={30}
              invert
            />
          </div>
        ),
        enableSorting: false,
      }),
      columnHelper.accessor((candidate) => candidateScore(candidate, 'interface_score') ?? candidate.score, {
        id: 'interface_score',
        header: ({ column }) => (
          <GridHelpHeader
            column={column}
            label={t.candidatesExt.table.modelInterfaceScore}
            help={t.candidatesExt.table.modelInterfaceScoreHelp}
          />
        ),
        cell: (info) => formatScore(info.getValue(), t.candidatesExt.table.notScored),
      }),
      columnHelper.accessor((candidate) => candidateText(candidate, 'pred_kd'), {
        id: 'pred_kd',
        header: ({ column }) => (
          <GridHelpHeader column={column} label={t.candidatesExt.table.predKd} help={t.candidatesExt.table.predKdHelp} />
        ),
        cell: (info) => info.getValue() ?? t.candidatesExt.table.notScored,
      }),
      columnHelper.accessor((candidate) => candidateScore(candidate, 'plddt'), {
        id: 'plddt',
        header: ({ column }) => (
          <GridHelpHeader column={column} label={t.candidatesExt.table.plddt} help={t.candidatesExt.table.plddtHelp} />
        ),
        cell: (info) => formatScore(info.getValue(), t.candidatesExt.table.notScored, 0),
      }),
      columnHelper.accessor((candidate) => candidateScore(candidate, 'solubility_score'), {
        id: 'solubility_score',
        header: ({ column }) => (
          <GridHelpHeader
            column={column}
            label={t.candidatesExt.table.solubilityScore}
            help={t.candidatesExt.table.solubilityHelp}
          />
        ),
        cell: (info) => formatScore(info.getValue(), t.candidatesExt.table.notScored, 0),
      }),
      columnHelper.accessor((candidate) => candidateScore(candidate, 'interface_pae'), {
        id: 'interface_pae',
        header: ({ column }) => (
          <GridHelpHeader
            column={column}
            label={t.candidatesExt.table.interfacePae}
            help={t.candidatesExt.table.interfacePaeHelp}
          />
        ),
        cell: (info) => (info.getValue() != null ? `${info.getValue()} Å` : t.candidatesExt.table.notScored),
      }),
      columnHelper.accessor((candidate) => candidateScore(candidate, 'rosetta_score'), {
        id: 'rosetta_score',
        header: ({ column }) => (
          <GridHelpHeader
            column={column}
            label={t.candidatesExt.table.rosettaEnergy}
            help={t.candidatesExt.table.rosettaHelp}
          />
        ),
        cell: (info) => info.getValue() ?? t.candidatesExt.table.notScored,
      }),
      columnHelper.accessor((candidate) => candidateScore(candidate, 'clash_count'), {
        id: 'clash_count',
        header: ({ column }) => (
          <GridHelpHeader column={column} label={t.candidatesExt.table.clashes} help={t.candidatesExt.table.clashesHelp} />
        ),
        cell: (info) => info.getValue() ?? t.candidatesExt.table.notScored,
      }),
      columnHelper.accessor((candidate) => candidateScore(candidate, 'buried_sasa'), {
        id: 'buried_sasa',
        header: ({ column }) => (
          <GridHelpHeader
            column={column}
            label={t.candidatesExt.table.buriedSasa}
            help={t.candidatesExt.table.buriedSasaHelp}
          />
        ),
        cell: (info) => (info.getValue() != null ? `${info.getValue()} Å²` : t.candidatesExt.table.notScored),
      }),
      columnHelper.accessor((candidate) => candidateText(candidate, 'expression_risk'), {
        id: 'expression_risk',
        header: ({ column }) => <DataGridColumnHeader column={column} title={t.candidatesExt.table.expression} />,
      }),
      columnHelper.accessor('status', {
        header: ({ column }) => <DataGridColumnHeader column={column} title={t.candidatesExt.table.status} />,
        cell: (info) => <StatusPill label={info.getValue()} tone={statusTone(info.getValue())} />,
      }),
      columnHelper.accessor((candidate) => candidateText(candidate, 'decision'), {
        id: 'decision',
        header: ({ column }) => <DataGridColumnHeader column={column} title={t.candidatesExt.table.decision} />,
        cell: (info) => (
          <StatusPill label={info.getValue() ?? '—'} tone={statusTone(info.getValue() ?? '')} />
        ),
      }),
      ]
      return baseColumns
    },
    [format, onSelect, onToggleCandidate, onTogglePage, selectedId, selectedIds, t],
  )
  const columnVisibility = useMemo<VisibilityState>(
    () => ({
      interface_score: expertColumns,
      plddt: expertColumns,
      solubility_score: expertColumns,
      interface_pae: expertColumns,
      rosetta_score: expertColumns,
      clash_count: expertColumns,
      buried_sasa: expertColumns,
      expression_risk: expertColumns,
    }),
    [expertColumns],
  )

  const handleSortingChange: OnChangeFn<SortingState> = (updater) => {
    setSorting((current) => functionalUpdate(updater, current))
    setPagination((current) => ({ ...current, pageIndex: 0 }))
  }

  // TanStack Table intentionally exposes mutable function references.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data,
    columns,
    state: { pagination, sorting, rowSelection, columnVisibility },
    onPaginationChange: setPagination,
    onSortingChange: handleSortingChange,
    enableSorting: true,
    enableRowSelection: true,
    getRowId: (candidate) => candidate.id,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })
  const pageIds = table.getRowModel().rows.map((row) => row.id)
  const allPageSelected = pageIds.length > 0 && pageIds.every((candidateId) => selectedIds?.has(candidateId))
  const selectedCount = selectedIds?.size ?? 0

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border px-3 py-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-accent">{t.candidatesExt.table.rankedScreen}</p>
          <p className="text-xs text-text-secondary">{t.candidatesExt.table.rankedScreenHint}</p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <span className="text-xs text-text-secondary">
            {format(t.candidatesExt.pagination.selected, { count: selectedCount })}
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!pageIds.length}
            onClick={() => onTogglePage?.(pageIds)}
          >
            {allPageSelected ? t.candidatesExt.table.clearPage : t.candidatesExt.table.selectPage}
          </Button>
          {onClearSelection ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!selectedCount}
              onClick={onClearSelection}
            >
              {t.candidatesExt.pagination.clearAll}
            </Button>
          ) : null}
          {onDownloadPage ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!pageIds.length || isDownloading}
              onClick={() => onDownloadPage(pageIds, pagination.pageIndex)}
            >
              <DownloadSimpleIcon aria-hidden="true" />
              {t.candidatesExt.pagination.downloadPage}
            </Button>
          ) : null}
          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-pressed={expertColumns}
            onClick={() => setExpertColumns((value) => !value)}
          >
            {expertColumns ? t.candidatesExt.table.beginnerColumns : t.candidatesExt.table.expertColumns}
          </Button>
        </div>
      </div>
      <p className="px-3 pt-2 text-xs text-text-secondary sm:hidden" aria-hidden="true">
        {t.candidatesExt.table.swipeHint}
      </p>
      <div
        className="flex min-h-0 flex-1 flex-col"
        role="region"
        aria-label={t.candidatesExt.table.tableAriaLabel}
        aria-describedby={tableDescriptionId}
        tabIndex={0}
      >
        <span id={tableDescriptionId} className="sr-only">
          {t.candidatesExt.table.tableCaption}
        </span>
        <DataGrid
          table={table}
          recordCount={data.length}
          emptyMessage={t.candidatesExt.table.noMatches}
          onRowClick={onSelect}
          tableLayout={{ dense: true, headerSticky: true, columnsResizable: true }}
          className="flex min-h-0 flex-1 flex-col"
        >
          <div className="flex min-h-0 flex-1 flex-col">
            <DataGridContainer className="h-full min-h-0 flex-1 [&>div]:h-full [&>div]:min-h-0">
              <DataGridScrollArea className="h-full min-h-0">
                <DataGridTable />
              </DataGridScrollArea>
            </DataGridContainer>
          </div>
          <div className="shrink-0 border-t border-border px-3" data-testid="candidate-pagination">
            <DataGridPagination
              sizes={[10, 25, 50]}
              rowsPerPageLabel={t.candidatesExt.pagination.rowsPerPage}
              info={t.candidatesExt.pagination.paginationInfo}
              previousPageLabel={t.candidatesExt.pagination.previousPage}
              nextPageLabel={t.candidatesExt.pagination.nextPage}
            />
          </div>
        </DataGrid>
      </div>
    </div>
  )
}
