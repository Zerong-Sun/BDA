"use no memo"
import { useMemo } from 'react'
import { getCoreRowModel, useReactTable, type ColumnDef } from '@tanstack/react-table'
import { DataGrid, DataGridContainer } from '../../components/reui/data-grid/data-grid'
import { DataGridColumnHeader } from '../../components/reui/data-grid/data-grid-column-header'
import { DataGridScrollArea } from '../../components/reui/data-grid/data-grid-scroll-area'
import { DataGridTable } from '../../components/reui/data-grid/data-grid-table'
import { useI18n } from '../../lib/i18n'
import { type AnalysisRecord } from '../../lib/api/wetlab'
import type { InstrumentAnalysisData, BliSummary, AktaSummary, EnzymeSummary } from '../../lib/schemas/instrumentAnalysis'
import { LineChart, type Trace } from './LineChart'
import { InstrumentQuality } from './InstrumentQuality'
import { Disclosure } from '../../components/ui/Disclosure'
import { AnalysisProvenance } from './AnalysisProvenance'

function formatNumber(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  const magnitude = Math.abs(value)
  if (magnitude !== 0 && (magnitude < 0.001 || magnitude >= 100000)) return value.toExponential(2)
  return String(Math.round(value * 10 ** digits) / 10 ** digits)
}

/**
 * A read-only result table on the registry's DataGrid.
 *
 * These three tables are all the same thing — labelled rows of numbers, no
 * sorting, no selection — so they share one wrapper rather than each spelling
 * out the grid's plumbing. The audit requires the registry table; repeating its
 * boilerplate three times would only invite the three to drift apart.
 */
function ResultTable<Row extends object>({
  rows,
  columns,
  rowId,
}: {
  rows: Row[]
  columns: ColumnDef<Row>[]
  rowId: (row: Row) => string
}) {
  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => rowId(row),
  })
  return (
    <DataGrid
      table={table}
      recordCount={rows.length}
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
  )
}

function numberColumn<Row extends object>(
  id: string,
  title: string,
  read: (row: Row) => string,
  size = 130,
): ColumnDef<Row> {
  return {
    id,
    header: ({ column }) => <DataGridColumnHeader column={column} title={title} />,
    cell: ({ row }) => <span className="tabular-nums">{read(row.original)}</span>,
    size,
  }
}

export function AnalysisResult({ analysed, projectId, onReviewed }: { analysed: InstrumentAnalysisData; projectId: string; onReviewed: (record: AnalysisRecord) => void }) {
  const { t, language } = useI18n()
  const copy = t.lab.instruments

  return (
    <section className="space-y-4" aria-label={copy.recorded}>
      <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <div className="flex gap-2">
          <dt className="text-text-secondary">{copy.recorded}</dt>
          <dd className="font-mono text-xs">{analysed.record.experiment_result_id || (language === 'zh' ? '未保存预览' : 'Unsaved preview')}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-text-secondary">{copy.analysisVersion}</dt>
          <dd className="font-mono text-xs">{analysed.record.analysis_version}</dd>
        </div>
      </dl>
      <AnalysisProvenance record={analysed.record} summary={analysed.summary} />
      <InstrumentQuality key={analysed.record.experiment_result_id || 'preview'} quality={analysed.summary.quality_control} record={analysed.record} projectId={projectId} onReviewed={onReviewed} />
      {analysed.instrument === 'bli' ? <BliResult summary={analysed.summary} /> : null}
      {analysed.instrument === 'akta' ? <AktaResult summary={analysed.summary} /> : null}
      {analysed.instrument === 'enzyme' ? <EnzymeResult summary={analysed.summary} /> : null}
    </section>
  )
}

function BliResult({ summary }: { summary: BliSummary }) {
  const { t, language } = useI18n()
  const copy = t.lab.instruments

  const traces = useMemo<Trace[]>(
    () =>
      summary.curves.flatMap((curve, index) => {
        const label = `${curve.label} · ${formatNumber(curve.conc_nM, 1)} nM${curve.excluded ? ' · excluded from fit' : ''}`
        return [
          { label: `${label} · raw`, points: curve.points, colorIndex: index, opacity: curve.processed_points?.length ? 0.45 : 1, kind: curve.evidence_kind === 'simulated' ? 'simulated' as const : 'measured' as const },
          ...(curve.processed_points?.length ? [{ label: `${label} · reference-subtracted`, points: curve.processed_points, colorIndex: index, kind: 'measured' as const }] : []),
          ...(curve.analysis_fit_points?.length ? [{ label: `${label} · analysis`, points: curve.analysis_fit_points, colorIndex: index, kind: 'fitted' as const }] : []),
          ...(curve.instrument_fit_points?.length ? [{ label: `${label} · instrument`, points: curve.instrument_fit_points, colorIndex: index, kind: 'instrument-fit' as const }] : []),
        ]
      }),
    [summary.curves],
  )

  const methods = [
    ['standard', copy.methodStandard],
    ['split', copy.methodSplit],
    ['joint', summary.source_format === 'kinetic_triplets'
      ? (language === 'zh' ? '全局动力学（共享 kon/koff；各传感器独立 Rmax）' : 'Global kinetics (shared kon/koff; per-sensor Rmax)')
      : copy.methodJoint],
    ['steady', copy.methodSteady],
    ['mixed', copy.methodMixed],
    ...(summary.methods.instrument_kobs ? [['instrument_kobs', 'Instrument Kobs regression'] as const] : []),
  ] as const

  // Every method, including the ones that returned nothing. A KD four methods
  // agree on means something different from one a single method produced, and
  // dropping the empty rows would erase that distinction.
  const methodRows = methods.map(([key, label]) => {
    const fit = summary.methods[key]
    return {
      key,
      label,
      kd: fit ? formatNumber(fit.kd) : copy.notConverged,
      r2: fit ? formatNumber(fit.r2, 4) : '—',
      diagnostics: fit?.diagnostics && typeof fit.diagnostics === 'object' ? fit.diagnostics as Record<string, unknown> : {},
    }
  })
  const methodColumns: ColumnDef<(typeof methodRows)[number]>[] = [
    {
      id: 'method',
      header: ({ column }) => <DataGridColumnHeader column={column} title={copy.method} />,
      cell: ({ row }) => row.original.label,
      size: 160,
    },
    numberColumn('kd', `${copy.kd} (nM)`, (row) => row.kd),
    numberColumn('r2', copy.r2, (row) => row.r2, 100),
    numberColumn('residual', 'Residual RMSE', (row) => typeof row.diagnostics.residual_rmse === 'number' ? formatNumber(row.diagnostics.residual_rmse, 5) : '—'),
    numberColumn('bounds', 'Active bounds', (row) => Array.isArray(row.diagnostics.active_bounds) ? row.diagnostics.active_bounds.join(', ') || '—' : '—'),
  ]

  return (
    <div className="space-y-4">
      <p className="text-sm">
        <span className="text-text-secondary">{copy.kd}</span>{' '}
        <span className="tabular-nums">{formatNumber(summary.kd_nM)} nM</span>
        {' · '}
        <span className="text-text-secondary">{copy.sample}</span> {summary.sample_id}
      </p>
      <Disclosure title="Fit parameters and diagnostics"><pre className="max-h-64 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(summary.methods, null, 2)}</pre></Disclosure>
      <ResultTable rows={methodRows} columns={methodColumns} rowId={(row) => row.key} />
      {traces.length > 0 ? (
        <div>
          <h4 className="mb-1 text-sm font-medium">{copy.sensorgrams}</h4>
          <LineChart
            traces={traces}
            xLabel={copy.time}
            yLabel={copy.response}
            ariaLabel={copy.sensorgrams}
            bands={
              summary.phase?.t_assoc != null && summary.phase?.t_dissoc != null
                ? [{ start: summary.phase.t_assoc, end: summary.phase.t_dissoc }]
                : []
            }
          />
        </div>
      ) : null}
    </div>
  )
}

function AktaResult({ summary }: { summary: AktaSummary }) {
  const { t } = useI18n()
  const copy = t.lab.instruments

  const peakColumns: ColumnDef<(typeof summary.peaks)[number]>[] = [
    numberColumn('apex', copy.peakApex, (peak) => formatNumber(peak.apex_vol)),
    numberColumn('height', copy.peakHeight, (peak) => formatNumber(peak.height)),
    numberColumn('area', copy.peakArea, (peak) => formatNumber(peak.area, 4)),
    numberColumn('width', copy.peakWidth, (peak) => formatNumber(peak.half_width)),
  ]

  return (
    <div className="space-y-4">
      <div>
        <h4 className="mb-1 text-sm font-medium">
          {copy.chromatogram} · {summary.channel}
        </h4>
        {summary.trace.length > 0 ? (
          <LineChart
            traces={[{ label: summary.channel, points: summary.trace }]}
            xLabel={copy.volume}
            yLabel={summary.unit ?? ''}
            ariaLabel={copy.chromatogram}
            bands={summary.fractions}
            markers={summary.peaks.map((peak) => ({ at: peak.apex_vol }))}
          />
        ) : null}
      </div>
      <div>
        <h4 className="mb-1 text-sm font-medium">{copy.peaks}</h4>
        {summary.peaks.length === 0 ? (
          <p className="text-sm text-text-secondary">{copy.noPeaks}</p>
        ) : (
          <ResultTable
            rows={summary.peaks}
            columns={peakColumns}
            rowId={(peak) => String(peak.apex_vol)}
          />
        )}
      </div>
    </div>
  )
}

function EnzymeResult({ summary }: { summary: EnzymeSummary }) {
  const { t } = useI18n()
  const copy = t.lab.instruments

  // Fastest first: a plate is read for which wells moved, and a 96-row table in
  // well order buries that.
  const ranked = useMemo(
    () =>
      Object.entries(summary.fits).sort(
        ([, left], [, right]) => (right.slope ?? -Infinity) - (left.slope ?? -Infinity),
      ),
    [summary.fits],
  )
  const traces = useMemo<Trace[]>(
    () =>
      summary.wells
        .filter((well) => ranked.slice(0, 8).some(([name]) => name === well.well))
        .map((well) => ({ label: well.well, points: well.points })),
    [summary.wells, ranked],
  )

  const wellRows = ranked.map(([well, fit]) => ({
    well,
    rate: formatNumber(fit.slope, 5),
    r2: formatNumber(fit.r2, 4),
    interval: Array.isArray(fit.diagnostics?.slope_interval_95_dOD_min) ? fit.diagnostics.slope_interval_95_dOD_min.map((v) => typeof v === 'number' ? formatNumber(v, 5) : '—').join(' – ') : '—',
  }))
  const wellColumns: ColumnDef<(typeof wellRows)[number]>[] = [
    {
      id: 'well',
      header: ({ column }) => <DataGridColumnHeader column={column} title={copy.well} />,
      cell: ({ row }) => <span className="font-mono text-xs">{row.original.well}</span>,
      size: 100,
    },
    numberColumn('rate', copy.rate, (row) => row.rate),
    numberColumn('r2', copy.r2, (row) => row.r2, 100),
    numberColumn('interval', 'Conditional 95% slope interval (dOD/min)', (row) => row.interval, 220),
  ]

  return (
    <div className="space-y-4">
      <p className="text-sm text-text-secondary">
        {summary.well_count} {copy.wellCount}
      </p>
      {traces.length > 0 ? (
        <div>
          <h4 className="mb-1 text-sm font-medium">{copy.kinetics}</h4>
          <LineChart
            traces={traces}
            xLabel={copy.minutes}
            yLabel={copy.absorbance}
            ariaLabel={copy.kinetics}
          />
        </div>
      ) : null}
      <ResultTable rows={wellRows} columns={wellColumns} rowId={(row) => row.well} />
    </div>
  )
}
