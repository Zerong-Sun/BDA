import { useMemo, useState } from 'react'
import {
  createColumnHelper,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table'
import { DataGrid, DataGridContainer } from '@/components/reui/data-grid/data-grid'
import { DataGridColumnHeader } from '@/components/reui/data-grid/data-grid-column-header'
import { DataGridScrollArea } from '@/components/reui/data-grid/data-grid-scroll-area'
import { DataGridTable } from '@/components/reui/data-grid/data-grid-table'
import { Button } from '@/components/ui/Button'
import { AppFrame } from '../../components/ui/AppFrame'
import type { ExperimentResult } from '../../lib/schemas/candidate'
import { AttachToGoalButton } from '../research/AttachToGoalButton'
import { ApiState } from '../../components/ui/ApiState'
import { useI18n } from '../../lib/i18n'

interface ValidationTableProps {
  results?: ExperimentResult[]
  loading?: boolean
  isError?: boolean
  error?: unknown
  candidateId?: string | null
  onClearCandidate?: () => void
  onRetry?: () => void
}

const validationColumnHelper = createColumnHelper<ExperimentResult>()

export function ValidationTable({ results, loading, isError, error, candidateId, onClearCandidate, onRetry }: ValidationTableProps) {
  const { t, format } = useI18n()
  const v = t.resultsExt.validationTable
  const [sorting, setSorting] = useState<SortingState>([])
  const visibleResults = candidateId
    ? (results ?? []).filter((result) => result.candidate_id === candidateId)
    : (results ?? [])
  const columns = useMemo(() => [
    validationColumnHelper.accessor('experiment_type', {
      header: ({ column }) => <DataGridColumnHeader column={column} title={v.step} />,
    }),
    validationColumnHelper.accessor('pass_status', {
      header: ({ column }) => <DataGridColumnHeader column={column} title={v.pass} />,
    }),
    validationColumnHelper.accessor((result) => result.conclusion ?? result.value ?? '—', {
      id: 'signal',
      header: ({ column }) => <DataGridColumnHeader column={column} title={v.signal} />,
      meta: { cellClassName: 'max-w-xs break-words' },
    }),
    validationColumnHelper.accessor((result) => result.failure_reason ?? '—', {
      id: 'implication',
      header: ({ column }) => <DataGridColumnHeader column={column} title={v.implication} />,
      meta: { cellClassName: 'max-w-xs break-words' },
    }),
    validationColumnHelper.display({
      id: 'goal',
      header: ({ column }) => <DataGridColumnHeader column={column} title={v.goal} />,
      // A measured result is the answer to a question; this is where it gets filed
      // under one. Every other attach point in the app leads back to the same tree.
      cell: ({ row }) => (
        <AttachToGoalButton
          projectId={row.original.project_id}
          resourceType="experiment_result"
          resourceId={row.original.id}
        />
      ),
    }),
  ], [v])

  // TanStack Table intentionally exposes mutable function references.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: visibleResults,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getRowId: (result) => result.id,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <AppFrame
      className="h-full min-h-[24rem] xl:min-h-0"
      panelClassName="flex min-h-0 flex-col overflow-hidden p-4"
      heading={v.title}
      actions={candidateId ? (
        <div className="flex max-w-full items-center gap-2">
          <span className="truncate text-xs text-primary">{format(v.filteredTo, { candidateId })}</span>
          {onClearCandidate ? (
            <Button type="button" variant="outline" size="sm" onClick={onClearCandidate}>
              {v.clear}
            </Button>
          ) : null}
        </div>
      ) : null}
    >
      <ApiState
        isLoading={false}
        isError={isError}
        error={error}
        onRetry={onRetry}
      >
        <DataGrid
          table={table}
          recordCount={visibleResults.length}
          isLoading={loading}
          emptyMessage={candidateId ? format(v.noMatch, { candidateId }) : v.empty}
          tableLayout={{ dense: true, headerSticky: true, columnsResizable: true }}
        >
          <DataGridContainer className="h-full min-h-0 flex-1 [&>div]:h-full [&>div]:min-h-0">
            <DataGridScrollArea className="h-full min-h-0">
              <DataGridTable />
            </DataGridScrollArea>
          </DataGridContainer>
        </DataGrid>
      </ApiState>
    </AppFrame>
  )
}
