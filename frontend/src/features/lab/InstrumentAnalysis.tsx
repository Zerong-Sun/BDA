"use no memo"

import { useMemo, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useI18n } from '../../lib/i18n'
import { uploadArtifact } from '../../lib/api/artifacts'
import { analyseAkta, analyseBli, analyseEnzyme, type AnalysisRecord } from '../../lib/api/wetlab'
import type {
  AktaSummary,
  BliSummary,
  EnzymeSummary,
} from '../../lib/schemas/instrumentAnalysis'
import { getCoreRowModel, useReactTable, type ColumnDef } from '@tanstack/react-table'
import { DataGrid, DataGridContainer } from '../../components/reui/data-grid/data-grid'
import { DataGridColumnHeader } from '../../components/reui/data-grid/data-grid-column-header'
import { DataGridScrollArea } from '../../components/reui/data-grid/data-grid-scroll-area'
import { DataGridTable } from '../../components/reui/data-grid/data-grid-table'
import { Frame, FrameHeader, FrameTitle } from '../../components/reui/frame'
import { Button } from '../../components/ui/Button'
import { Checkbox } from '../../components/ui/checkbox'
import { Input } from '../../components/ui/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'
import { LineChart, type Trace } from './LineChart'

type Instrument = 'bli' | 'akta' | 'enzyme'

type Analysed =
  | { instrument: 'bli'; record: AnalysisRecord; summary: BliSummary }
  | { instrument: 'akta'; record: AnalysisRecord; summary: AktaSummary }
  | { instrument: 'enzyme'; record: AnalysisRecord; summary: EnzymeSummary }

//: What each kernel can read. The picker narrows the file dialog rather than
//: relying on the 422 that a Unicorn zip handed to the BLI parser would produce.
const ACCEPT: Record<Instrument, string> = {
  bli: '.csv,text/csv',
  akta: '.zip',
  enzyme: '.xlsx',
}

function optionalNumber(raw: string): number | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

function formatNumber(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  const magnitude = Math.abs(value)
  if (magnitude !== 0 && (magnitude < 0.001 || magnitude >= 100000)) return value.toExponential(2)
  return String(Math.round(value * 10 ** digits) / 10 ** digits)
}

/**
 * Upload an instrument export, analyse it, and look at what was fitted.
 *
 * The three kernels and their endpoints already existed and the Copilot could
 * already call them; what was missing was the way a person does it. The order
 * here is the platform's upload contract, not a choice: the file goes
 * browser-direct to object storage, and only its artifact id is posted to the
 * analysis endpoint — the API never receives a file body.
 *
 * The plots are drawn from the series the response carries, because the backend
 * has no plotting library on purpose. Numbers that did not converge are shown as
 * such rather than hidden: a KD that four methods agree on means something quite
 * different from one that only a single method produced.
 */
export function InstrumentAnalysis({ projectId }: { projectId: string }) {
  const { t } = useI18n()
  const copy = t.lab.instruments

  const [instrument, setInstrument] = useState<Instrument>('bli')
  const [file, setFile] = useState<File | null>(null)
  const [candidateId, setCandidateId] = useState('')
  const [sampleId, setSampleId] = useState('')
  const [channel, setChannel] = useState('')
  const [tAssoc, setTAssoc] = useState('')
  const [tDissoc, setTDissoc] = useState('')
  const [subtractBackground, setSubtractBackground] = useState(true)
  const [analysed, setAnalysed] = useState<Analysed | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const run = useMutation({
    mutationFn: async (): Promise<Analysed> => {
      if (!file) throw new Error(copy.file)
      const artifact = await uploadArtifact(file, projectId)
      const candidate = candidateId.trim() || null
      if (instrument === 'bli') {
        const result = await analyseBli(projectId, {
          artifact_id: artifact.id,
          sample_id: sampleId.trim() || null,
          t_assoc: optionalNumber(tAssoc),
          t_dissoc: optionalNumber(tDissoc),
          candidate_id: candidate,
        })
        return { instrument: 'bli', record: result, summary: result.summary }
      }
      if (instrument === 'akta') {
        const result = await analyseAkta(projectId, {
          artifact_id: artifact.id,
          channel: channel.trim() || null,
          candidate_id: candidate,
        })
        return { instrument: 'akta', record: result, summary: result.summary }
      }
      const result = await analyseEnzyme(projectId, {
        artifact_id: artifact.id,
        subtract_background: subtractBackground,
        candidate_id: candidate,
      })
      return { instrument: 'enzyme', record: result, summary: result.summary }
    },
    onSuccess: (result) => setAnalysed(result),
  })

  return (
    <Frame dense>
      <FrameHeader>
        <FrameTitle>{copy.title}</FrameTitle>
      </FrameHeader>

      <div className="space-y-5 p-4">
        <p className="max-w-3xl text-sm text-text-secondary">{copy.intro}</p>

        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            run.mutate()
          }}
        >
          <label className="flex flex-col gap-1 text-sm">
            <span>{copy.instrument}</span>
            <Select
              value={instrument}
              onValueChange={(next) => {
                setInstrument((next as Instrument) ?? instrument)
                // The chosen file belongs to the instrument it was picked for;
                // a Unicorn zip handed to the BLI parser only produces a
                // confusing 422.
                setFile(null)
                if (fileInput.current) fileInput.current.value = ''
              }}
            >
              <SelectTrigger aria-label={copy.instrument} className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="bli">{copy.bli}</SelectItem>
                <SelectItem value="akta">{copy.akta}</SelectItem>
                <SelectItem value="enzyme">{copy.enzyme}</SelectItem>
              </SelectContent>
            </Select>
          </label>

          {/* The picker is a hidden native input behind a registry Button, the
              same shape every other upload here uses: the browser's own file
              control cannot be styled or labelled consistently. */}
          <div className="flex flex-col gap-1 text-sm">
            <span>{copy.file}</span>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => fileInput.current?.click()}
              >
                {copy.choose}
              </Button>
              <span className="max-w-48 truncate text-text-secondary">{file?.name ?? '—'}</span>
            </div>
            <input
              ref={fileInput}
              type="file"
              aria-label={copy.file}
              accept={ACCEPT[instrument]}
              className="hidden"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </div>

          {instrument === 'bli' ? (
            <>
              <label className="flex flex-col gap-1 text-sm">
                <span>{copy.sample}</span>
                <Input
                  className="w-32"
                  value={sampleId}
                  onChange={(event) => setSampleId(event.target.value)}
                />
              </label>
              {/* Worth passing whenever the run declares them: without a
                  boundary the kernel reads one off the smoothed curve, which is
                  fine for a look and not what belongs behind a recorded KD. */}
              <label className="flex flex-col gap-1 text-sm">
                <span>{copy.tAssoc}</span>
                <Input
                  type="number"
                  step="any"
                  className="w-32 tabular-nums"
                  value={tAssoc}
                  onChange={(event) => setTAssoc(event.target.value)}
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span>{copy.tDissoc}</span>
                <Input
                  type="number"
                  step="any"
                  className="w-32 tabular-nums"
                  value={tDissoc}
                  onChange={(event) => setTDissoc(event.target.value)}
                />
              </label>
            </>
          ) : null}

          {instrument === 'akta' ? (
            <label className="flex flex-col gap-1 text-sm">
              <span>{copy.channel}</span>
              <Input
                className="w-40"
                value={channel}
                onChange={(event) => setChannel(event.target.value)}
              />
            </label>
          ) : null}

          {instrument === 'enzyme' ? (
            <label className="flex items-center gap-2 pb-2 text-sm">
              <Checkbox
                checked={subtractBackground}
                onCheckedChange={(next) => setSubtractBackground(next === true)}
              />
              {copy.subtractBackground}
            </label>
          ) : null}

          <label className="flex flex-col gap-1 text-sm">
            <span>{copy.candidate}</span>
            <Input
              className="w-72"
              placeholder={copy.candidateHint}
              value={candidateId}
              onChange={(event) => setCandidateId(event.target.value)}
            />
          </label>

          <Button type="submit" disabled={!file || run.isPending}>
            {run.isPending ? copy.analysing : copy.analyse}
          </Button>
        </form>

        {run.error ? (
          <p role="alert" className="text-sm text-destructive">
            {(run.error as Error).message}
          </p>
        ) : null}

        {analysed ? <AnalysisResult analysed={analysed} /> : null}
      </div>
    </Frame>
  )
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

function AnalysisResult({ analysed }: { analysed: Analysed }) {
  const { t } = useI18n()
  const copy = t.lab.instruments

  return (
    <section className="space-y-4" aria-label={copy.recorded}>
      <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <div className="flex gap-2">
          <dt className="text-text-secondary">{copy.recorded}</dt>
          <dd className="font-mono text-xs">{analysed.record.experiment_result_id}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-text-secondary">{copy.analysisVersion}</dt>
          <dd className="font-mono text-xs">{analysed.record.analysis_version}</dd>
        </div>
      </dl>
      {analysed.instrument === 'bli' ? <BliResult summary={analysed.summary} /> : null}
      {analysed.instrument === 'akta' ? <AktaResult summary={analysed.summary} /> : null}
      {analysed.instrument === 'enzyme' ? <EnzymeResult summary={analysed.summary} /> : null}
    </section>
  )
}

function BliResult({ summary }: { summary: BliSummary }) {
  const { t } = useI18n()
  const copy = t.lab.instruments

  const traces = useMemo<Trace[]>(
    () =>
      summary.curves.map((curve) => ({
        label: `${curve.label} · ${formatNumber(curve.conc_nM, 1)} nM`,
        points: curve.points,
      })),
    [summary.curves],
  )

  const methods = [
    ['standard', copy.methodStandard],
    ['split', copy.methodSplit],
    ['joint', copy.methodJoint],
    ['steady', copy.methodSteady],
    ['mixed', copy.methodMixed],
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
  ]

  return (
    <div className="space-y-4">
      <p className="text-sm">
        <span className="text-text-secondary">{copy.kd}</span>{' '}
        <span className="tabular-nums">{formatNumber(summary.kd_nM)} nM</span>
        {' · '}
        <span className="text-text-secondary">{copy.sample}</span> {summary.sample_id}
      </p>
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
