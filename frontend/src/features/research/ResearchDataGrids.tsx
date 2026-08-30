"use no memo"

import { useMemo, useState, type ReactNode } from 'react'
import {
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { DownloadSimpleIcon, MagnifyingGlassIcon } from '@phosphor-icons/react'
import type {
  ResearchWorkspaceKnowledge,
  ResearchWorkspaceTarget,
} from '../../lib/api/generated/types.gen'
import { workspaceText, type ResearchLanguage } from '../../lib/api/researchWorkspace'
import { resolveStoredText } from '../../lib/i18n/localizedText'
import {
  DataGrid,
  DataGridContainer,
} from '../../components/reui/data-grid/data-grid'
import { DataGridColumnHeader } from '../../components/reui/data-grid/data-grid-column-header'
import { DataGridScrollArea } from '../../components/reui/data-grid/data-grid-scroll-area'
import { DataGridTable } from '../../components/reui/data-grid/data-grid-table'
import {
  Frame,
  FrameHeader,
  FramePanel,
  FrameTitle,
} from '../../components/reui/frame'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../components/ui/accordion'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'

type AskCopilotRenderer = (entityId: string, entityType: string, label: string) => ReactNode
type TargetActionRenderer = (target: ResearchWorkspaceTarget) => ReactNode

export type ResearchGridLabels = {
  targetTableTitle: string
  tableTarget: string
  tableGroup: string
  tableScore: string
  tableEvidence: string
  tableNovelty: string
  tableTractability: string
  tableHuman: string
  tableSpecificity: string
  tableSafety: string
  tableHistorical: string
  tableRecent: string
  datasetSearch: string
  datasetSearchLabel: string
  downloadJson: string
  advancedJson: string
  noRows: string
  noTargets: string
}

type DatasetRow = {
  id: string
  values: Record<string, unknown>
}

function numberValue(value: unknown): string {
  return typeof value === 'number' || typeof value === 'string' ? String(value) : '—'
}

function localizedDatasetCell(value: unknown, language: ResearchLanguage): string {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return resolveStoredText(value, language)
  }
  return numberValue(value)
}

function rowRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : { value }
}

function datasetColumnId(sourceKey: string): string {
  const encoded = Array.from(sourceKey, (character) => (
    character.codePointAt(0)?.toString(16) ?? '0'
  )).join('_')
  return `dataset_${encoded || 'empty'}`
}

export function DatasetDataGrid({
  dataset,
  labels,
  language,
  renderAskCopilot,
}: {
  dataset: ResearchWorkspaceKnowledge
  labels: ResearchGridLabels
  language: ResearchLanguage
  renderAskCopilot: AskCopilotRenderer
}) {
  const [filter, setFilter] = useState('')
  const [sorting, setSorting] = useState<SortingState>([])
  const [advancedOpen, setAdvancedOpen] = useState<string[]>([])
  const sourceRows = useMemo(
    () => Array.isArray(dataset.display_data)
      ? dataset.display_data
      : Array.isArray(dataset.data)
        ? dataset.data
        : [],
    [dataset.data, dataset.display_data],
  )
  const rows = useMemo<DatasetRow[]>(
    () => sourceRows.map((value, index) => ({
      id: `${dataset.id}:${index}`,
      values: rowRecord(value),
    })),
    [dataset.id, sourceRows],
  )
  const columnKeys = useMemo(
    () => Array.from(new Set(rows.flatMap((row) => Object.keys(row.values)))),
    [rows],
  )
  const columns = useMemo<ColumnDef<DatasetRow>[]>(
    () => columnKeys.map((key) => ({
      id: datasetColumnId(key),
      accessorFn: (row) => row.values[key],
      header: ({ column }) => <DataGridColumnHeader column={column} title={key} />,
      cell: ({ getValue }) => localizedDatasetCell(getValue(), language),
      minSize: 120,
      size: 180,
    })),
    [columnKeys, language],
  )
  const normalizedFilter = filter.trim().toLowerCase()
  const visibleRows = useMemo(
    () => normalizedFilter
      ? rows.filter((row) => JSON.stringify(row.values).toLowerCase().includes(normalizedFilter))
      : rows,
    [normalizedFilter, rows],
  )
  // TanStack Table intentionally exposes stateful closures; the grid owns this boundary.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: visibleRows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getRowId: (row) => row.id,
  })
  const title = workspaceText(dataset.title, language)

  const download = () => {
    const blob = new Blob([JSON.stringify(dataset.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${dataset.key || 'research-data'}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Frame dense>
      <FramePanel className="min-w-0 p-0">
        <FrameHeader className="flex-row flex-wrap items-center justify-between gap-3 border-b">
          <div className="flex min-w-0 items-center gap-2">
            <FrameTitle className="truncate">{title}</FrameTitle>
            {renderAskCopilot(dataset.id, 'dataset', title)}
          </div>
          <div className="flex min-w-0 flex-1 flex-wrap justify-end gap-2">
            <label className="relative min-w-52 flex-1 sm:max-w-72">
              <MagnifyingGlassIcon
                aria-hidden="true"
                className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground"
              />
              <Input
                aria-label={labels.datasetSearchLabel}
                className="pl-8"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder={labels.datasetSearch}
              />
            </label>
            <Button type="button" variant="outline" size="sm" onClick={download}>
              <DownloadSimpleIcon aria-hidden="true" />
              {labels.downloadJson}
            </Button>
          </div>
        </FrameHeader>
        <div className="min-h-0 min-w-0">
          <DataGrid
            table={table}
            recordCount={visibleRows.length}
            emptyMessage={labels.noRows}
            tableLayout={{
              dense: true,
              headerBackground: true,
              headerBorder: true,
              rowBorder: true,
              width: 'auto',
              columnsResizable: true,
            }}
          >
            <DataGridContainer>
              <DataGridScrollArea orientation="horizontal">
                <DataGridTable />
              </DataGridScrollArea>
            </DataGridContainer>
          </DataGrid>
        </div>
        <Accordion
          value={advancedOpen}
          onValueChange={setAdvancedOpen}
          className="border-t px-4"
        >
          <AccordionItem value="json" className="border-0">
            <AccordionTrigger className="py-3 text-primary">
              {labels.advancedJson}
            </AccordionTrigger>
            <AccordionContent>
              <pre className="overflow-x-auto bg-muted p-3 text-xs">
                {JSON.stringify(dataset.data, null, 2)}
              </pre>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </FramePanel>
    </Frame>
  )
}

export function ResearchTargetDataGrid({
  targets,
  labels,
  language,
  renderAskCopilot,
  renderTargetAction,
}: {
  targets: ResearchWorkspaceTarget[]
  labels: ResearchGridLabels
  language: ResearchLanguage
  renderAskCopilot: AskCopilotRenderer
  renderTargetAction?: TargetActionRenderer
}) {
  const [sorting, setSorting] = useState<SortingState>([])
  const columns = useMemo<ColumnDef<ResearchWorkspaceTarget>[]>(() => {
    const metric = (
      id: string,
      title: string,
      accessorFn: (row: ResearchWorkspaceTarget) => unknown,
    ): ColumnDef<ResearchWorkspaceTarget> => ({
      id,
      accessorFn,
      header: ({ column }) => <DataGridColumnHeader column={column} title={title} />,
      cell: ({ getValue }) => numberValue(getValue()),
      size: 112,
    })
    return [
      {
        id: 'target',
        accessorFn: (target) => `${target.candidate_key} ${workspaceText(target.name, language)}`,
        header: ({ column }) => <DataGridColumnHeader column={column} title={labels.tableTarget} />,
        cell: ({ row }) => {
          const target = row.original
          const name = workspaceText(target.name, language)
          return (
            <div className="grid min-w-56 gap-1 font-medium">
              <div className="flex items-center gap-2">
                <span>{target.candidate_key} · {name}</span>
                {renderAskCopilot(target.id, 'research target', name)}
              </div>
              {renderTargetAction?.(target)}
            </div>
          )
        },
        size: 280,
      },
      {
        id: 'group',
        accessorFn: (target) => workspaceText(target.pain_group, language),
        header: ({ column }) => <DataGridColumnHeader column={column} title={labels.tableGroup} />,
        cell: ({ getValue }) => String(getValue() || '—'),
        size: 160,
      },
      metric('score', labels.tableScore, (target) => target.score),
      metric('evidence', labels.tableEvidence, (target) => target.scores?.evidence),
      metric('novelty', labels.tableNovelty, (target) => target.scores?.novelty),
      metric('tractability', labels.tableTractability, (target) => target.scores?.tractability),
      metric('human', labels.tableHuman, (target) => target.scores?.human),
      metric('specificity', labels.tableSpecificity, (target) => target.scores?.specificity),
      metric('safety', labels.tableSafety, (target) => target.scores?.safety),
      metric(
        'historical',
        labels.tableHistorical,
        (target) => (target.properties?.bibliometrics as Record<string, unknown> | undefined)?.historical_count,
      ),
      metric(
        'recent',
        labels.tableRecent,
        (target) => (target.properties?.bibliometrics as Record<string, unknown> | undefined)?.recent_5y_count,
      ),
    ]
  }, [labels, language, renderAskCopilot, renderTargetAction])
  // TanStack Table intentionally exposes stateful closures; the grid owns this boundary.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: targets,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getRowId: (row) => row.id,
  })

  return (
    <Frame dense>
      <FramePanel className="min-w-0 p-0">
        <FrameHeader className="border-b">
          <FrameTitle>{labels.targetTableTitle}</FrameTitle>
        </FrameHeader>
        <div className="min-h-0 min-w-0">
          <DataGrid
            table={table}
            recordCount={targets.length}
            emptyMessage={labels.noTargets}
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
      </FramePanel>
    </Frame>
  )
}
