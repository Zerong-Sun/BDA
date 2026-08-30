"use no memo"

import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getCoreRowModel, useReactTable, type ColumnDef } from '@tanstack/react-table'
import { useI18n } from '../../lib/i18n'
import { createProtein, importFasta, listProteins } from '../../lib/api/wetlab'
import type { ProteinRead } from '../../lib/api/generated/types.gen'
import { DataGrid, DataGridContainer } from '../../components/reui/data-grid/data-grid'
import { DataGridColumnHeader } from '../../components/reui/data-grid/data-grid-column-header'
import { AttachToGoalButton } from '../research/AttachToGoalButton'
import { DataGridScrollArea } from '../../components/reui/data-grid/data-grid-scroll-area'
import { DataGridTable } from '../../components/reui/data-grid/data-grid-table'
import { Frame, FrameHeader, FrameTitle } from '../../components/reui/frame'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../../components/ui/accordion'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/textarea'

/**
 * The bench's protein library.
 *
 * Constructs are listed by fingerprint, never by sequence: the server does not
 * return one. The notice says so out loud, because a scientist who cannot find
 * the sequence column needs to know that is the design and not a failure.
 */
export function ProteinLibrary({ projectId }: { projectId: string }) {
  const { t } = useI18n()
  const copy = t.lab.library
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [name, setName] = useState('')
  const [sequence, setSequence] = useState('')
  const [fasta, setFasta] = useState('')
  const [importOpen, setImportOpen] = useState<string[]>([])

  // Keyed on the project: constructs must never leak between projects through
  // a shared cache entry.
  const proteins = useQuery({
    queryKey: ['proteins', projectId, search],
    queryFn: () => listProteins(projectId, { search }),
    enabled: Boolean(projectId),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['proteins', projectId] })

  const addOne = useMutation({
    mutationFn: () => createProtein(projectId, { name, sequence }),
    onSuccess: () => {
      setName('')
      setSequence('')
      void invalidate()
    },
  })

  const addBatch = useMutation({
    mutationFn: () => importFasta(projectId, fasta),
    onSuccess: () => {
      setFasta('')
      void invalidate()
    },
  })

  const rows = useMemo(() => proteins.data?.items ?? [], [proteins.data])

  const columns = useMemo<ColumnDef<ProteinRead>[]>(
    () => [
      {
        id: 'name',
        accessorKey: 'name',
        header: ({ column }) => <DataGridColumnHeader column={column} title={copy.name} />,
        cell: ({ row }) => row.original.name,
        size: 220,
      },
      {
        id: 'fingerprint',
        accessorKey: 'fingerprint',
        header: ({ column }) => <DataGridColumnHeader column={column} title={copy.fingerprint} />,
        cell: ({ row }) => <span className="font-mono text-xs">{row.original.fingerprint}</span>,
        size: 140,
      },
      {
        id: 'length',
        accessorKey: 'length',
        header: ({ column }) => <DataGridColumnHeader column={column} title={copy.length} />,
        cell: ({ row }) => <span className="tabular-nums">{row.original.length}</span>,
        size: 110,
      },
      {
        id: 'mass',
        accessorKey: 'molecular_weight',
        header: ({ column }) => <DataGridColumnHeader column={column} title={copy.mass} />,
        cell: ({ row }) => (
          <span className="tabular-nums">{row.original.molecular_weight?.toFixed(1) ?? '—'}</span>
        ),
        size: 130,
      },
      {
        id: 'origin',
        accessorKey: 'candidate_id',
        header: ({ column }) => <DataGridColumnHeader column={column} title={copy.origin} />,
        // Which design this construct came from. Without it the bench half of the loop
        // is a list of names: the id is already stored, it was simply never shown, so a
        // measured number had no visible way back to the design that predicted it.
        cell: ({ row }) =>
          row.original.candidate_id ? (
            <Link
              className="text-accent hover:underline"
              to={`/candidates?project=${encodeURIComponent(projectId)}&candidate=${encodeURIComponent(row.original.candidate_id)}`}
            >
              {copy.originDesign}
            </Link>
          ) : (
            <span className="text-text-muted">{copy.originBench}</span>
          ),
        size: 130,
      },
      {
        id: 'goal',
        header: ({ column }) => <DataGridColumnHeader column={column} title={copy.goal} />,
        // The bench half of the loop hangs on the same tree as the dry half; without an
        // attach action here a construct could only be linked through the agent.
        cell: ({ row }) => (
          <AttachToGoalButton
            projectId={projectId}
            resourceType="protein"
            resourceId={row.original.id}
          />
        ),
        size: 120,
      },
      {
        id: 'extinction',
        accessorKey: 'ext_coeff_reduced',
        header: ({ column }) => <DataGridColumnHeader column={column} title={copy.extinction} />,
        cell: ({ row }) => (
          <span className="tabular-nums">{row.original.ext_coeff_reduced?.toFixed(0) ?? '—'}</span>
        ),
        size: 150,
      },
    ],
    [copy, projectId],
  )

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
  })

  const importSummary = addBatch.data

  return (
    <Frame dense>
      <FrameHeader>
        <FrameTitle>{copy.title}</FrameTitle>
        <p className="text-sm text-text-secondary">{copy.sequenceNotice}</p>
      </FrameHeader>

      <div className="space-y-4 p-4">
        <Input
          type="text"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={copy.search}
          aria-label={copy.search}
        />

        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            addOne.mutate()
          }}
        >
          <label className="flex flex-col gap-1 text-sm">
            <span>{copy.name}</span>
            <Input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </label>
          <label className="flex min-w-64 flex-1 flex-col gap-1 text-sm">
            <span>{copy.sequence}</span>
            <Input
              type="text"
              className="font-mono"
              value={sequence}
              onChange={(event) => setSequence(event.target.value)}
              required
            />
          </label>
          <Button type="submit" disabled={addOne.isPending}>
            {copy.add}
          </Button>
        </form>

        {addOne.error ? (
          <p role="alert" className="text-sm text-destructive">
            {(addOne.error as Error).message}
          </p>
        ) : null}

        <Accordion value={importOpen} onValueChange={setImportOpen}>
          <AccordionItem value="fasta">
            <AccordionTrigger>{copy.importFasta}</AccordionTrigger>
            <AccordionContent>
              <form
                className="space-y-2"
                onSubmit={(event) => {
                  event.preventDefault()
                  addBatch.mutate()
                }}
              >
                <Textarea
                  className="h-32 font-mono text-sm"
                  placeholder={copy.importPlaceholder}
                  value={fasta}
                  onChange={(event) => setFasta(event.target.value)}
                  aria-label={copy.importFasta}
                />
                <Button type="submit" disabled={addBatch.isPending}>
                  {copy.importFasta}
                </Button>
              </form>
              {importSummary ? (
                // Per-record outcome, because a batch with one duplicate is the
                // normal case and the good records still landed.
                <p className="mt-2 text-sm text-text-secondary">
                  {importSummary.created} {copy.imported} · {importSummary.duplicates}{' '}
                  {copy.duplicate} · {importSummary.rejected} {copy.rejected}
                </p>
              ) : null}
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        <DataGrid
          table={table}
          recordCount={rows.length}
          emptyMessage={copy.empty}
          tableLayout={{
            dense: true,
            headerBackground: true,
            headerBorder: true,
            rowBorder: true,
            width: 'auto',
          }}
        >
          <DataGridContainer>
            <DataGridScrollArea orientation="horizontal">
              <DataGridTable />
            </DataGridScrollArea>
          </DataGridContainer>
        </DataGrid>
      </div>
    </Frame>
  )
}
